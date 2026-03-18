import { toast } from 'sonner'
import { useState, useEffect, useCallback, Fragment } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  FolderTree, Plus, Edit, Trash2, RefreshCw, ChevronRight, ChevronDown,
  Archive, Inbox, Building2, Target, UserPlus, Search, User,
  Download, ChevronUp, Brain, FileText, Link, X, Check, ChevronsUpDown, Ban, CheckCircle, Eye, Calendar
} from 'lucide-react'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import { LocationBadge } from '@/components/ui/location-badge'
import { Checkbox } from '@/components/ui/checkbox'
import { ScoreBadge } from '@/components/ui/score-badge'

const API = import.meta.env.VITE_API_URL || ""
const H = () => ({ 'Authorization': `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' })

interface Pool { id: number; name: string; icon: string; pool_type: string; is_system: number; keywords: string|null; description: string|null }
interface SysPool { id: number; name: string; icon: string; is_system: boolean; candidate_count: number }
interface Position { id: number; name: string; icon: string; keywords: string|null; description: string|null; candidate_count: number }
interface Dept { id: number; name: string; icon: string; candidate_count: number; positions: Position[]; total_position_candidates: number }
interface TreeData { system_pools: SysPool[]; departments: Dept[]; total_candidates?: number }
interface Candidate { id: number; ad_soyad: string; email: string|null; telefon: string|null; mevcut_pozisyon: string|null; toplam_deneyim_yil: number|null; lokasyon: string|null; location_status?: { status: "green" | "yellow" | "red" | "gray"; candidate_location: string; position_location: string; match_type: string }; match_score?: number; match_reason?: string; remaining_days?: number; assignment_type?: string; status?: string; is_blacklisted?: number; durum?: string; intelligence?: { career_path?: string; level?: string; experience_years?: number; sectors?: string[]; suitable_positions?: string[]; key_skills?: string[]; education_level?: string; education_field?: string; analyzed_at?: string } }

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  beklemede: { label: 'Beklemede', color: 'bg-amber-100 text-amber-800' },
  degerlendirilecek: { label: 'Değerlendirilecek', color: 'bg-blue-100 text-blue-800' },
  genel_havuz: { label: 'Genel Havuz', color: 'bg-slate-100 text-slate-800' },
  arsiv: { label: 'Arşiv', color: 'bg-gray-100 text-gray-800' },
  kara_liste: { label: 'Kara Liste', color: 'bg-gray-900 text-white' },
  ise_alindi: { label: 'İşe Alındı', color: 'bg-emerald-100 text-emerald-800' },
}

// Level Badge Komponenti
const LevelBadge = ({ level }: { level?: string }) => {
  if (!level) return <span className="text-gray-400 text-xs">-</span>
  const colors: Record<string, string> = {
    junior: 'bg-blue-100 text-blue-700',
    mid: 'bg-green-100 text-green-700',
    senior: 'bg-orange-100 text-orange-700',
    lead: 'bg-purple-100 text-purple-700'
  }
  const labels: Record<string, string> = { junior: 'Junior', mid: 'Mid', senior: 'Senior', lead: 'Lead' }
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[level] || 'bg-gray-100 text-gray-700'}`}>{labels[level] || level}</span>
}

export default function Havuzlar() {
  const navigate = useNavigate()
  const [tree, setTree] = useState<TreeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPoolId, setSelectedPoolId] = useState<number | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [poolInfo, setPoolInfo] = useState<Pool | null>(null)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [expandedDepts, setExpandedDepts] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [pulling, setPulling] = useState(false)

  // Filters
  const [filterScore, setFilterScore] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [sortBy, setSortBy] = useState('default')

  // Detail expansion
  const [expandedCandidate, setExpandedCandidate] = useState<number | null>(null)
  const [candidateDetail, setCandidateDetail] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Dialogs
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [assignDialogOpen, setAssignDialogOpen] = useState(false)

  // Kara Liste Dialog
  const [blacklistDialogOpen, setBlacklistDialogOpen] = useState(false)
  const [blacklistReason, setBlacklistReason] = useState('')
  const [blacklistCandidateId, setBlacklistCandidateId] = useState<number | null>(null)
  const [blacklistLoading, setBlacklistLoading] = useState(false)

  // Kara Liste Bilgi + Çıkarma
  const [blacklistInfo, setBlacklistInfo] = useState<{reason: string; blacklisted_at: string; blacklisted_by_name: string} | null>(null)
  const [removeBlacklistDialogOpen, setRemoveBlacklistDialogOpen] = useState(false)
  const [removeBlacklistReason, setRemoveBlacklistReason] = useState('')
  const [removeBlacklistLoading, setRemoveBlacklistLoading] = useState(false)

  // Aday Detay Modalı
  const [candidateDetailModalOpen, setCandidateDetailModalOpen] = useState(false)
  const [selectedCandidateDetail, setSelectedCandidateDetail] = useState<any>(null)

  // Forms
  const [poolForm, setPoolForm] = useState({ name: '', pool_type: 'department', parent_id: '', icon: '', keywords: '', description: '', gerekli_deneyim_yil: '0', gerekli_egitim: '', lokasyon: '' })
  const [assignCandidateId, setAssignCandidateId] = useState('')
  const [candidateSearchOpen, setCandidateSearchOpen] = useState(false)
  const [candidateList, setCandidateList] = useState<{id: number, ad_soyad: string, mevcut_pozisyon?: string}[]>([])
  const [selectedCandidate, setSelectedCandidate] = useState<{id: number, ad_soyad: string} | null>(null)

  // Position Add with URL/Manual
  const [urlInput, setUrlInput] = useState('')
  const [parseLoading, setParseLoading] = useState(false)
  const [parsedData, setParsedData] = useState<Record<string, unknown> | null>(null)
  const [positionForm, setPositionForm] = useState({
    pozisyon_adi: '', lokasyon: '', deneyim_yil: '0', egitim_seviyesi: '',
    keywords: '', aranan_nitelikler: '', is_tanimi: ''
  })
  const [savingPosition, setSavingPosition] = useState(false)

  // Keyword Management
  const [newKeyword, setNewKeyword] = useState('')
  const [editKeywords, setEditKeywords] = useState<string[]>([])
  const [keywordLoading, setKeywordLoading] = useState(false)

  // Akıllı Havuz - Title Mappings
  const [approvedTitles, setApprovedTitles] = useState<Record<string, Array<{id: number; related_title: string; match_level: string; source: string}>> | null>(null)
  const [pendingTitles, setPendingTitles] = useState<Record<string, Array<{id: number; related_title: string; match_level: string; source: string}>> | null>(null)
  const [selectedPending, setSelectedPending] = useState<Set<number>>(new Set())
  const [titlesLoading, setTitlesLoading] = useState(false)
  const [approving, setApproving] = useState(false)
  const [titlesExpanded, setTitlesExpanded] = useState(true)

  // AI Evaluation V3
  const [evaluating, setEvaluating] = useState(false)
  const [rescoring, setRescoring] = useState(false)
  const [v3Evaluation, setV3Evaluation] = useState<Record<number, {
    total_score: number
    eligible: boolean
    gemini_score: number
    hermes_score: number
    openai_score?: number
    evaluation_method?: string
    models_used?: string[]
    claude_used?: boolean
    layer_scores: {
      technical_skills?: { score: number; reason: string }
      position_match?: { score: number; reason: string }
      experience_quality?: { score: number; reason: string }
      education?: { score: number; reason: string }
      other?: { score: number; reason: string }
    }
    strengths: string[]
    weaknesses: string[]
  }>>({})
  const [v3Loading, setV3Loading] = useState<Record<number, boolean>>({})

  // CV Intelligence
  const [intelligenceData, setIntelligenceData] = useState<Record<number, Candidate['intelligence']>>({})
  const [analyzingIntelligence, setAnalyzingIntelligence] = useState(false)

  // Job Description Upload (B5)
  const [jdUploadOpen, setJdUploadOpen] = useState(false)
  const [jdUploading, setJdUploading] = useState(false)
  const [jdResult, setJdResult] = useState<{
    success: boolean
    gorev_sayisi?: number
    keyword_sayisi?: number
    title_sayisi?: number
    rescore_sayisi?: number
  } | null>(null)

  const loadTree = useCallback(() => {
    setLoading(true)
    fetch(`${API}/api/pools/hierarchical`, { headers: H() })
      .then(r => r.json()).then(res => {
        if (res.success) { setTree(res.data); const ids = new Set<number>(); res.data.departments?.forEach((d: Dept) => ids.add(d.id)); setExpandedDepts(ids) }
      }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const loadCandidates = useCallback((poolId: number) => {
    setCandidatesLoading(true); setExpandedCandidate(null); setCandidateDetail(null)
    fetch(`${API}/api/pools/${poolId}/candidates`, { headers: H() })
      .then(r => r.json()).then(res => {
        if (res.success) {
          setCandidates(res.data)
          setPoolInfo(res.pool)
          // V3 skorları varsa v3Evaluation state'ini güncelle
          const v3Data: Record<number, {
            total_score: number
            eligible: boolean
            gemini_score: number
            hermes_score: number
            openai_score?: number
            evaluation_method?: string
            models_used?: string[]
            claude_used?: boolean
            layer_scores: Record<string, { score: number; reason: string }>
            strengths: string[]
            weaknesses: string[]
          }> = {}
          res.data.forEach((c: { id: number; v3_score?: number; gemini_score?: number; hermes_score?: number; openai_score?: number; score_version?: string }) => {
            if (c.score_version === 'v3_weighted' || c.score_version === 'v3') {
              v3Data[c.id] = {
                total_score: c.v3_score || 0,
                eligible: (c.v3_score || 0) >= 40,
                gemini_score: c.gemini_score || 0,
                hermes_score: c.hermes_score || 0,
                openai_score: c.openai_score || 0,
                layer_scores: {},
                strengths: [],
                weaknesses: []
              }
            }
          })
          if (Object.keys(v3Data).length > 0) {
            setV3Evaluation(prev => ({ ...prev, ...v3Data }))
          }
        }
      })
      .catch(console.error).finally(() => setCandidatesLoading(false))
  }, [])

  // CV Intelligence API fonksiyonları
  const fetchIntelligence = useCallback(async (candidateId: number) => {
    try {
      const res = await fetch(`${API}/api/ai-evaluation/intelligence/${candidateId}`, { headers: H() })
      if (res.ok) { const data = await res.json(); return data.data }
      return null
    } catch { return null }
  }, [])

  const handleAnalyzeIntelligence = useCallback(async (candidateId: number) => {
    setAnalyzingIntelligence(true)
    try {
      const res = await fetch(`${API}/api/ai-evaluation/intelligence/analyze`, {
        method: 'POST', headers: H(), body: JSON.stringify({ candidate_id: candidateId })
      })
      if (res.ok) {
        const data = await res.json()
        if (data.success) {
          toast.success('CV profil analizi tamamlandı')
          const intel = await fetchIntelligence(candidateId)
          if (intel) {
            setIntelligenceData(prev => ({ ...prev, [candidateId]: intel }))
            setCandidates(prev => prev.map(c => c.id === candidateId ? { ...c, intelligence: intel } : c))
          }
          return data
        }
      }
      toast.error('Profil analizi başarısız')
      return null
    } catch {
      toast.error('Profil analizi hatası')
      return null
    } finally {
      setAnalyzingIntelligence(false)
    }
  }, [fetchIntelligence])

  useEffect(() => { loadTree() }, [loadTree])
  useEffect(() => { if (selectedPoolId) loadCandidates(selectedPoolId) }, [selectedPoolId, loadCandidates])

  // Aday Ata - Combobox için aday listesi
  const fetchCandidatesForAssign = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/candidates`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        const assignable = (data.data.candidates || []).filter((c: {durum?: string}) => c.durum !== 'ise_alindi')
        setCandidateList(assignable)
      }
    } catch (error) {
      console.error('Aday listesi alınamadı:', error)
      toast.error('Aday listesi yüklenemedi')
    }
  }, [])

  useEffect(() => {
    if (assignDialogOpen) {
      fetchCandidatesForAssign()
      setSelectedCandidate(null)
      setCandidateSearchOpen(false)
    }
  }, [assignDialogOpen, fetchCandidatesForAssign])

  const toggleDept = (id: number) => setExpandedDepts(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })

  // Candidate Detail
  const loadDetail = async (candidateId: number) => {
    if (expandedCandidate === candidateId) { setExpandedCandidate(null); setCandidateDetail(null); setBlacklistInfo(null); return }
    setExpandedCandidate(candidateId); setDetailLoading(true); setCandidateDetail(null); setBlacklistInfo(null)
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/detail`, { headers: H() })
      .then(r => r.json()).then(res => {
        if (res.success) {
          setCandidateDetail(res)
          // FAZ 13.6: ai_evaluation + scoring_info verilerini state'e aktar
          if (res.ai_evaluation) {
            setV3Evaluation(prev => ({
              ...prev,
              [candidateId]: {
                ...prev[candidateId],
                total_score: res.ai_evaluation.total_score || prev[candidateId]?.total_score || 0,
                eligible: (res.ai_evaluation.total_score || prev[candidateId]?.total_score || 0) >= 40,
                gemini_score: res.ai_evaluation.gemini_score || 0,
                hermes_score: res.ai_evaluation.hermes_score || 0,
                openai_score: res.ai_evaluation.openai_score || 0,
                strengths: res.ai_evaluation.strengths || [],
                weaknesses: res.ai_evaluation.weaknesses || [],
                layer_scores: res.ai_evaluation.layer_scores || res.ai_evaluation.scores || prev[candidateId]?.layer_scores || {},
                evaluation_method: res.ai_evaluation.consensus_method || ""
              }
            }))
          }
        }
      })
      .catch(console.error).finally(() => setDetailLoading(false))
    // Blacklist bilgisi çek
    fetch(`${API}/api/candidates/${candidateId}/blacklist`, { headers: H() })
      .then(r => r.json()).then(res => { if (res.success && res.is_blacklisted) setBlacklistInfo(res.data) })
      .catch(() => {})
    // CV Intelligence verisi çek
    const intel = await fetchIntelligence(candidateId)
    if (intel) {
      setIntelligenceData(prev => ({ ...prev, [candidateId]: intel }))
      setCandidates(prev => prev.map(c => c.id === candidateId ? { ...c, intelligence: intel } : c))
    }
  }

  // CRUD handlers
  const resetPoolForm = () => setPoolForm({ name: '', pool_type: 'department', parent_id: '', icon: '', keywords: '', description: '', gerekli_deneyim_yil: '0', gerekli_egitim: '', lokasyon: '' })
  const openCreate = (type: string, parentId?: number) => { resetPoolForm(); setPoolForm(p => ({ ...p, pool_type: type, parent_id: parentId ? String(parentId) : '' })); setCreateDialogOpen(true) }

  const openEdit = () => {
    if (!poolInfo) return
    setPoolForm({ name: poolInfo.name || '', pool_type: poolInfo.pool_type || 'department', parent_id: '', icon: '', keywords: poolInfo.keywords || '', description: poolInfo.description || '', gerekli_deneyim_yil: '0', gerekli_egitim: '', lokasyon: '' })
    // Keywords'u parse et
    const kwStr = poolInfo.keywords || ''
    let kwArr: string[] = []
    try {
      const parsed = JSON.parse(kwStr)
      if (Array.isArray(parsed)) kwArr = parsed.map(k => String(k).trim()).filter(Boolean)
    } catch {
      kwArr = kwStr.split(',').map(k => k.trim()).filter(Boolean)
    }
    setEditKeywords(kwArr)
    setNewKeyword('')
    setEditDialogOpen(true)
  }

  const handleCreatePool = () => {
    if (!poolForm.name) return
    const payload: Record<string, unknown> = { name: poolForm.name, pool_type: poolForm.pool_type, icon: poolForm.pool_type === 'position' ? '\uD83C\uDFAF' : '\uD83D\uDCC1', keywords: poolForm.keywords ? poolForm.keywords.split(',').map(k => k.trim()).filter(Boolean) : [], description: poolForm.description, gerekli_deneyim_yil: Number(poolForm.gerekli_deneyim_yil) || 0, gerekli_egitim: poolForm.gerekli_egitim, lokasyon: poolForm.lokasyon }
    if (poolForm.parent_id) payload.parent_id = Number(poolForm.parent_id)
    fetch(`${API}/api/pools`, { method: 'POST', headers: H(), body: JSON.stringify(payload) })
      .then(r => r.json()).then(res => { if (res.success) { setCreateDialogOpen(false); resetPoolForm(); loadTree() } else toast.error(res.detail || 'Hata') })
  }

  const handleUpdatePool = () => {
    if (!selectedPoolId || !poolForm.name) return
    fetch(`${API}/api/pools/${selectedPoolId}`, { method: 'PUT', headers: H(), body: JSON.stringify({ name: poolForm.name, keywords: editKeywords, description: poolForm.description }) })
      .then(r => r.json()).then(res => { if (res.success) { setEditDialogOpen(false); loadTree(); loadCandidates(selectedPoolId) } else toast.error(res.detail || 'Hata') })
  }

  const handleDeletePool = () => {
    if (!deleteConfirm) return
    fetch(`${API}/api/pools/${deleteConfirm}`, { method: 'DELETE', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { setDeleteConfirm(null); if (selectedPoolId === deleteConfirm) { setSelectedPoolId(null); setCandidates([]); setPoolInfo(null) }; loadTree() } else toast.error(res.detail || 'Hata') })
  }

  const handleAssignCandidate = () => {
    if (!selectedPoolId || !assignCandidateId) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates`, { method: 'POST', headers: H(), body: JSON.stringify({ candidate_id: Number(assignCandidateId), reason: 'Manuel atama' }) })
      .then(r => r.json()).then(res => { if (res.success) { setAssignDialogOpen(false); setAssignCandidateId(''); loadCandidates(selectedPoolId); loadTree() } else toast.error(res.detail || 'Hata') })
  }

  const handleRemoveCandidate = async (cid: number) => {
    if (!selectedPoolId) return
    const res = await fetch(`${API}/api/pools/${selectedPoolId}/candidates/${cid}`, { method: 'DELETE', headers: H() })
    const data = await res.json()
    if (res.status === 400) {
      toast.error(data.detail || 'Bu havuzdan aday silinemez.')
      return
    }
    if (data.success) {
      loadCandidates(selectedPoolId)
      loadTree()
    }
  }

  const handleSyncAll = () => {
    setSyncing(true)
    fetch(`${API}/api/pools/sync-all`, { method: 'POST', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { toast.success('Senkronizasyon Tamamlandı', { description: `${res.data.positions_scanned} pozisyon tarandı, ${res.data.total_transferred} aday aktarıldı` }); loadTree(); if (selectedPoolId) loadCandidates(selectedPoolId) } else toast.error(res.detail || 'Hata') })
      .catch(console.error).finally(() => setSyncing(false))
  }

  const handlePullCandidates = () => {
    if (!selectedPoolId) return; setPulling(true)
    fetch(`${API}/api/pools/${selectedPoolId}/pull-candidates`, { method: 'POST', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { const desc = res.data.matched > 0 ? `${res.data.total_scanned} aday tarandı, ${res.data.matched} eşleşti, ${res.data.transferred} aktarıldı` : `${res.data.total_scanned} aday tarandı. Mevcut adaylarla eşleşme bulunamadı.`; toast.success('Eşleştirme Tamamlandı', { description: desc }); loadCandidates(selectedPoolId); loadTree() } else toast.error(res.detail || 'Hata') })
      .catch(console.error).finally(() => setPulling(false))
  }

  const handleExport = () => {
    if (!selectedPoolId) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/export`, { headers: H() })
      .then(r => r.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `${poolInfo?.name || 'havuz'}_adaylar.csv`
        document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
      }).catch(console.error)
  }

  // URL ile Pozisyon Parse
  const handleParseUrl = () => {
    if (!urlInput) return
    setParseLoading(true); setParsedData(null)
    fetch(`${API}/api/pools/position/from-url`, { method: 'POST', headers: H(), body: JSON.stringify({ url: urlInput }) })
      .then(r => r.json()).then(res => {
        if (res.success && res.data) {
          const d = res.data
          setParsedData(d)
          setPositionForm({
            pozisyon_adi: d.pozisyon_adi || '',
            lokasyon: d.lokasyon || '',
            deneyim_yil: String(d.deneyim_yil || 0),
            egitim_seviyesi: d.egitim_seviyesi || '',
            keywords: Array.isArray(d.keywords) ? d.keywords.join(', ') : (d.keywords || ''),
            aranan_nitelikler: d.aranan_nitelikler || '',
            is_tanimi: d.is_tanimi || ''
          })
        } else { toast.error(res.detail || res.hata || 'Parse hatası') }
      }).catch(e => toast.error('Hata: ' + e)).finally(() => setParseLoading(false))
  }

  // Parse Sonucu veya Manuel Kaydet
  const handleSaveParsed = () => {
    if (!positionForm.pozisyon_adi) { toast.error("Pozisyon adı gerekli"); return }
    if (!poolForm.parent_id) { toast.error("Departman seçilmedi"); return }
    setSavingPosition(true)
    const payload = {
      parent_id: Number(poolForm.parent_id),
      pozisyon_adi: positionForm.pozisyon_adi,
      lokasyon: positionForm.lokasyon,
      deneyim_yil: Number(positionForm.deneyim_yil) || 0,
      egitim_seviyesi: positionForm.egitim_seviyesi,
      keywords: (typeof positionForm.keywords === 'string' ? positionForm.keywords : '').split(',').map(k => k.trim()).filter(Boolean),
      aranan_nitelikler: positionForm.aranan_nitelikler,
      is_tanimi: positionForm.is_tanimi
    }
    fetch(`${API}/api/pools/position/save-parsed`, { method: 'POST', headers: H(), body: JSON.stringify(payload) })
      .then(r => r.json()).then(res => {
        if (res.success) {
          setCreateDialogOpen(false); resetPoolForm(); setUrlInput(''); setParsedData(null)
          setPositionForm({ pozisyon_adi: '', lokasyon: '', deneyim_yil: '0', egitim_seviyesi: '', keywords: '', aranan_nitelikler: '', is_tanimi: '' })
          loadTree()
          // FAZ 6.4: Synonym sonucu göster
          const synRes = res.synonym_result
          if (synRes?.success && synRes?.inserted > 0) {
            toast.success('Pozisyon oluşturuldu', {
              description: `${res.transferred} aday eşleştirildi. ${synRes.inserted} synonym üretildi (onay bekliyor).`
            })
          } else {
            toast.success('Pozisyon başarıyla eklendi', {
              description: `${res.transferred} aday eşleştirildi`
            })
          }
        } else { toast.error(res.detail || 'Kayıt hatası') }
      }).catch(e => toast.error('Hata: ' + e)).finally(() => setSavingPosition(false))
  }

  // Keyword Ekle
  const handleAddKeyword = () => {
    if (!selectedPoolId || !newKeyword.trim()) return
    setKeywordLoading(true)
    fetch(`${API}/api/pools/${selectedPoolId}/keywords`, { method: 'PUT', headers: H(), body: JSON.stringify({ action: 'add', keyword: newKeyword.trim() }) })
      .then(r => r.json()).then(res => {
        if (res.success) {
          setEditKeywords(res.keywords || [])
          setNewKeyword('')
          loadCandidates(selectedPoolId)
        } else { toast.error(res.detail || 'Hata') }
      }).catch(console.error).finally(() => setKeywordLoading(false))
  }

  // Keyword Sil
  const handleRemoveKeyword = (kw: string) => {
    if (!selectedPoolId) return
    setKeywordLoading(true)
    fetch(`${API}/api/pools/${selectedPoolId}/keywords`, { method: 'PUT', headers: H(), body: JSON.stringify({ action: 'remove', keyword: kw }) })
      .then(r => r.json()).then(res => {
        if (res.success) {
          setEditKeywords(res.keywords || [])
          loadCandidates(selectedPoolId)
        } else { toast.error(res.detail || 'Hata') }
      }).catch(console.error).finally(() => setKeywordLoading(false))
  }

  // Akıllı Havuz - Title Mappings yükle
  const loadTitles = useCallback((poolId: number) => {
    setTitlesLoading(true)
    setApprovedTitles(null)
    setPendingTitles(null)
    setSelectedPending(new Set())

    Promise.all([
      fetch(`${API}/api/pools/${poolId}/approved-titles`, { headers: H() }).then(r => r.json()),
      fetch(`${API}/api/pools/${poolId}/pending-titles`, { headers: H() }).then(r => r.json())
    ]).then(([approvedRes, pendingRes]) => {
      if (approvedRes.success) setApprovedTitles(approvedRes.data)
      if (pendingRes.success) {
        setPendingTitles(pendingRes.data)
        // exact olanları varsayılan seçili yap
        const exactIds = new Set<number>()
        if (pendingRes.data?.exact) {
          pendingRes.data.exact.forEach((t: {id: number}) => exactIds.add(t.id))
        }
        setSelectedPending(exactIds)
      }
    }).catch(console.error).finally(() => setTitlesLoading(false))
  }, [])

  // Load titles when position pool is selected
  useEffect(() => {
    if (selectedPoolId && poolInfo?.pool_type === 'position') {
      loadTitles(selectedPoolId)
    } else {
      setApprovedTitles(null)
      setPendingTitles(null)
      setSelectedPending(new Set())
    }
  }, [selectedPoolId, poolInfo?.pool_type, loadTitles])

  // Başlıkları onayla
  const handleApproveTitles = () => {
    if (!selectedPoolId || selectedPending.size === 0) return
    setApproving(true)
    fetch(`${API}/api/pools/${selectedPoolId}/approve-titles`, {
      method: 'POST',
      headers: H(),
      body: JSON.stringify({ approved_ids: Array.from(selectedPending), rejected_ids: [] })
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          const desc = res.transferred > 0
            ? `${res.approved} başlık onaylandı, ${res.transferred} aday eşleştirildi`
            : `${res.approved} başlık onaylandı. Mevcut adaylarla eşleşme bulunamadı.`
          toast.success('Onay Tamamlandı', { description: desc })
          loadTitles(selectedPoolId)
          loadCandidates(selectedPoolId)
        } else { toast.error(res.detail || 'Hata') }
      })
      .catch(console.error)
      .finally(() => setApproving(false))
  }

  // Toggle pending title selection
  const togglePendingTitle = (id: number) => {
    setSelectedPending(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  // AI Değerlendirme V3
  const handleEvaluate = async (candidateId: number) => {
    if (!selectedPoolId) return
    setEvaluating(true)
    setV3Loading(prev => ({ ...prev, [candidateId]: true }))
    try {
      const res = await fetch(`${API}/api/ai-evaluation/evaluate`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ candidate_id: candidateId, position_id: selectedPoolId })
      })
      const data = await res.json()
      if (data.success && data.data) {
        setV3Evaluation(prev => ({ ...prev, [candidateId]: data.data }))
        toast.success(`AI Değerlendirme tamamlandı: ${data.data.total_score} puan`)
        loadDetail(candidateId)
      } else {
        toast.error(data.detail || 'Değerlendirme hatası')
      }
    } catch (e) {
      toast.error('Değerlendirme hatası: ' + e)
    } finally {
      setEvaluating(false)
      setV3Loading(prev => ({ ...prev, [candidateId]: false }))
    }
  }


  // Yeniden Hesapla
  const handleRescore = (candidateId: number) => {
    if (!selectedPoolId) return
    setRescoring(true)
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/rescore`, { method: 'POST', headers: H() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          toast.success(`Skor güncellendi: ${res.old_score} → ${res.new_score}`)
          loadDetail(candidateId)
          loadCandidates(selectedPoolId)
        } else { toast.error(res.detail || 'Hata') }
      })
      .catch(e => toast.error('Hata: ' + e))
      .finally(() => setRescoring(false))
  }
  // Rapor İndir
  const handleDownloadReport = (candidateId: number) => {
    if (!selectedPoolId) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/report`, { headers: H() })
      .then(r => {
        if (!r.ok) throw new Error('Rapor alınamadı')
        return r.text()
      })
      .then(html => {
        const blob = new Blob([html], { type: 'text/html' })
        const url = URL.createObjectURL(blob)
        window.open(url, '_blank')
      })
      .catch(e => toast.error('Hata: ' + e))
  }

  const handleViewCV = async (candidateId: number) => {
    if (!selectedPoolId) return
    try {
      const r = await fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/cv`, { headers: H() })
      if (!r.ok) {
        const errorData = await r.json().catch(() => ({ detail: 'Bilinmeyen hata' }))
        throw new Error(errorData.detail || 'CV yüklenemedi')
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'CV dosyası açılamadı')
    }
  }

  // Filtering & Sorting
  const filteredCandidates = candidates.filter(c => {
    if (searchQuery) {
      const q = searchQuery.toLocaleLowerCase('tr-TR')
      if (!(c.ad_soyad || '').toLocaleLowerCase('tr-TR').includes(q) && !(c.email || '').toLocaleLowerCase('tr-TR').includes(q) && !(c.mevcut_pozisyon || '').toLocaleLowerCase('tr-TR').includes(q)) return false
    }
    if (filterScore !== 'all') {
      const s = c.match_score || 0
      if (filterScore === 'high' && s < 80) return false
      if (filterScore === 'medium' && (s < 50 || s >= 80)) return false
      if (filterScore === 'low' && s >= 50) return false
    }
    if (filterStatus !== 'all' && c.status !== filterStatus) return false
    return true
  }).sort((a, b) => {
    if (sortBy === 'score_desc') return (b.match_score || 0) - (a.match_score || 0)
    if (sortBy === 'score_asc') return (a.match_score || 0) - (b.match_score || 0)
    if (sortBy === 'exp') return (b.toplam_deneyim_yil || 0) - (a.toplam_deneyim_yil || 0)
    if (sortBy === 'name') return (a.ad_soyad || '').localeCompare(b.ad_soyad || '')
    return 0
  })

  const totalCandidates = tree?.total_candidates || 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Havuzlar</h2>
          <p className="text-muted-foreground text-sm">Departman ve pozisyon havuzlarını yönetin</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { loadTree(); if (selectedPoolId) loadCandidates(selectedPoolId) }} disabled={loading}><RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />Yenile</Button>
          <Button size="sm" variant="outline" onClick={handleSyncAll} disabled={syncing}>{syncing ? <RefreshCw className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}Eşleştir</Button>
          <Button size="sm" onClick={() => openCreate('department')}><Plus className="h-4 w-4 mr-1" />Departman</Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold">{totalCandidates}</div><div className="text-xs text-muted-foreground">Toplam Aday</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-blue-600">{tree?.system_pools?.find(s => s.name === 'Genel Havuz')?.candidate_count || 0}</div><div className="text-xs text-muted-foreground">Genel Havuz</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-orange-600">{tree?.system_pools?.find(s => s.name === 'Arşiv')?.candidate_count || 0}</div><div className="text-xs text-muted-foreground">Arşiv</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-green-600">{tree?.departments?.length || 0}</div><div className="text-xs text-muted-foreground">Departman</div></CardContent></Card>
      </div>

      {/* Main Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: Tree */}
        <div className="col-span-4">
          <Card><CardContent className="p-3 space-y-1">
            <div className="text-sm font-medium text-muted-foreground mb-2">Havuz Ağacı</div>
            {tree?.system_pools?.map(sp => (
              <div key={sp.id} className={`flex items-center justify-between p-2 rounded cursor-pointer hover:bg-muted ${selectedPoolId === sp.id ? 'bg-muted border border-primary' : ''}`} onClick={() => setSelectedPoolId(sp.id)}>
                <div className="flex items-center gap-2">{sp.name === 'Arşiv' ? <Archive className="h-4 w-4 text-orange-500" /> : <Inbox className="h-4 w-4 text-blue-500" />}<span className="text-sm font-medium">{sp.name}</span></div>
                <Badge variant="secondary" className="text-xs">{sp.candidate_count}</Badge>
              </div>
            ))}
            {tree?.system_pools && tree.system_pools.length > 0 && <div className="border-t my-2" />}
            {tree?.departments?.map(dept => (
              <div key={dept.id}>
                <div className={`flex items-center justify-between p-2 rounded cursor-pointer hover:bg-muted ${selectedPoolId === dept.id ? "bg-muted border border-primary" : ""}`}>
                  <div className="flex items-center gap-2 flex-1" onClick={() => { toggleDept(dept.id); setSelectedPoolId(dept.id) }}>
                    {expandedDepts.has(dept.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    <Building2 className="h-4 w-4 text-indigo-500" /><span className="text-sm font-medium">{dept.name}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant="secondary" className="text-xs">{dept.total_position_candidates}</Badge>
                    <button onClick={(e) => { e.stopPropagation(); openCreate('position', dept.id) }} className="p-0.5 hover:bg-muted-foreground/10 rounded" title="Pozisyon Ekle"><Plus className="h-3.5 w-3.5 text-muted-foreground" /></button>
                  </div>
                </div>
                {expandedDepts.has(dept.id) && dept.positions.map(pos => (
                  <div key={pos.id} className={`flex items-center justify-between p-2 pl-9 rounded cursor-pointer hover:bg-muted ${selectedPoolId === pos.id ? 'bg-muted border border-primary' : ''}`} onClick={() => setSelectedPoolId(pos.id)}>
                    <div className="flex items-center gap-2"><Target className="h-3.5 w-3.5 text-emerald-500" /><span className="text-sm">{pos.name}</span></div>
                    <Badge variant="secondary" className="text-xs">{pos.candidate_count}</Badge>
                  </div>
                ))}
              </div>
            ))}
          </CardContent></Card>
        </div>

        {/* Right: Candidates */}
        <div className="col-span-8">
          {!selectedPoolId ? (
            <Card><CardContent className="p-12 text-center text-muted-foreground"><FolderTree className="h-12 w-12 mx-auto mb-3 opacity-30" /><p>Aday listesini görmek için soldaki ağaçtan bir havuz secin</p></CardContent></Card>
          ) : (
            <Card><CardContent className="p-4 space-y-3">
              {/* Pool Header */}
              <div className="space-y-3">
                {/* Başlık */}
                <h3 className="text-lg font-semibold">{poolInfo?.name}</h3>

                {/* Butonlar */}
                <div className="flex flex-wrap gap-1.5">
                  {poolInfo && !poolInfo.is_system && (<><Button variant="outline" size="sm" onClick={openEdit}><Edit className="h-3.5 w-3.5 mr-1" />İlan Detayı</Button><Button variant="outline" size="sm" className="text-red-500" onClick={() => setDeleteConfirm(selectedPoolId)}><Trash2 className="h-3.5 w-3.5 mr-1" />Sil</Button></>)}
                  {poolInfo && poolInfo.pool_type === 'position' && !poolInfo.is_system && (
                    <>
                      <Button variant="default" size="sm" onClick={handlePullCandidates} disabled={pulling}>{pulling ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Search className="h-3.5 w-3.5 mr-1" />}CV Çek</Button>
                      <Button variant="outline" size="sm" onClick={() => { setJdResult(null); setJdUploadOpen(true) }}><FileText className="h-3.5 w-3.5 mr-1" />Görev Tanımı</Button>
                    </>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setAssignDialogOpen(true)}><UserPlus className="h-3.5 w-3.5 mr-1" />Aday Ata</Button>
                </div>

                {/* Açıklama kaldırıldı */}
              </div>

              {/* Toolbar: Search + Filters */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="h-4 w-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input placeholder="Aday ara..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="pl-8 h-8 text-sm" />
                </div>
                <Select value={filterScore} onValueChange={setFilterScore}>
                  <SelectTrigger className="w-[130px] h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tüm Skorlar</SelectItem>
                    <SelectItem value="high">80+ Tam Uyum</SelectItem>
                    <SelectItem value="medium">50-79 Kısmi</SelectItem>
                    <SelectItem value="low">0-49 Uyumsuz</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Değerlendirme Durumu</SelectItem>
                    {Object.entries(STATUS_MAP).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Select value={sortBy} onValueChange={setSortBy}>
                  <SelectTrigger className="w-[130px] h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Varsayılan</SelectItem>
                    <SelectItem value="score_desc">Skor (Yüksek)</SelectItem>
                    <SelectItem value="score_asc">Skor (Düşük)</SelectItem>
                    <SelectItem value="exp">Deneyim</SelectItem>
                    <SelectItem value="name">İsim (A-Z)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Action Bar */}
              <div className="flex items-center gap-2">
                <div className="flex-1" />
                <Button size="sm" variant="ghost" onClick={handleExport}><Download className="h-3.5 w-3.5 mr-1" />CSV</Button>
                <Badge variant="outline">{filteredCandidates.length} aday</Badge>
              </div>

              {/* Candidates Table */}
              {candidatesLoading ? (
                <div className="text-center py-8 text-muted-foreground"><RefreshCw className="h-5 w-5 animate-spin inline mr-2" />Yükleniyor...</div>
              ) : filteredCandidates.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">Bu havuzda aday bulunmuyor</div>
              ) : (
                <div className="border rounded-md overflow-auto max-h-[600px]">
                  <Table className="table-fixed w-full">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[220px]">Ad Soyad</TableHead>
                        <TableHead className="w-[180px]">CV'de Belirtilen Unvan</TableHead>
                        <TableHead className="w-[80px]">Deneyim</TableHead>
                        <TableHead className="w-[120px]">Lokasyon</TableHead>
                        <TableHead className="w-[100px]">Uyum Skoru</TableHead>
                        <TableHead className="w-[80px] text-center">Kara Liste</TableHead>
                        <TableHead className="w-20"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredCandidates.map(c => {
                        return (
                          <Fragment key={c.id}>
                            <TableRow className={`cursor-pointer ${c.is_blacklisted === 1 || c.durum === 'blacklist' ? 'bg-red-50' : ''}`} onClick={() => loadDetail(c.id)}>
                              <TableCell>
                                <div className="font-medium text-sm flex items-center gap-1">{expandedCandidate === c.id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}{c.ad_soyad}</div>
                                {c.email && <div className="text-xs text-muted-foreground ml-4">{c.email}</div>}
                              </TableCell>
                              <TableCell className="text-sm truncate">{c.mevcut_pozisyon || '-'}</TableCell>
                              <TableCell className="text-sm">{c.toplam_deneyim_yil ? `${c.toplam_deneyim_yil} yıl` : '-'}</TableCell>
                              <TableCell className="text-sm max-w-[200px] overflow-hidden"><LocationBadge status={c.location_status?.status || 'gray'} candidateLocation={c.location_status?.candidate_location || c.lokasyon || '-'} positionLocation={c.location_status?.position_location || '-'} matchType={c.location_status?.match_type || 'Veri yok'} /></TableCell>
                              <TableCell>
                                {v3Evaluation[c.id] ? (
                                  <ScoreBadge score={c.match_score || 0} size="sm" />
                                ) : (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-6 text-[10px] px-2"
                                    onClick={(e) => { e.stopPropagation(); handleEvaluate(c.id) }}
                                    disabled={evaluating || v3Loading[c.id]}
                                  >
                                    {(evaluating || v3Loading[c.id]) ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Brain className="h-3 w-3 mr-1" />}
                                    Değerlendir
                                  </Button>
                                )}
                              </TableCell>
                              <TableCell className="text-center">
                                {c.is_blacklisted === 1 || c.durum === 'blacklist' ? (
                                  <Badge className="bg-gray-900 text-white text-[10px]">Kara Listede</Badge>
                                ) : (
                                  <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 h-7 w-7 p-0" onClick={(e) => { e.stopPropagation(); setBlacklistCandidateId(c.id); setBlacklistDialogOpen(true); }} title="Kara Listeye Al">
                                    <Ban className="h-4 w-4" />
                                  </Button>
                                )}
                              </TableCell>
                              <TableCell onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-1">
                                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => { setSelectedCandidateDetail(c); setCandidateDetailModalOpen(true); }} title="Detaylı Görüntüle"><Eye className="h-3.5 w-3.5 text-green-600" /></Button>
                                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleRescore(c.id)} disabled={rescoring} title="Skoru Yeniden Hesapla"><RefreshCw className="h-3.5 w-3.5 text-blue-500" /></Button>
                                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleEvaluate(c.id)} disabled={evaluating} title="AI Değerlendir"><Brain className="h-3.5 w-3.5 text-purple-500" /></Button>
                                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 h-7 w-7 p-0" onClick={() => handleRemoveCandidate(c.id)} title="Çıkar"><Trash2 className="h-3.5 w-3.5" /></Button>
                                </div>
                              </TableCell>
                            </TableRow>
                            {/* Expanded Detail Row */}
                            {expandedCandidate === c.id && (
                              <TableRow key={`detail-${c.id}`}>
                                <TableCell colSpan={7} className="bg-muted/30 p-4 max-w-0 overflow-hidden">
                                  {detailLoading ? <div className="text-center py-4"><RefreshCw className="h-4 w-4 animate-spin inline mr-2" />Yükleniyor...</div> : candidateDetail ? (() => { const cd = candidateDetail.candidate as any; const aie = (candidateDetail as any).ai_evaluation; return (
                                    <div className="w-full max-w-6xl space-y-3 overflow-hidden">
                                      {/* Kisisel Bilgiler */}
                                      <div className="grid grid-cols-3 gap-x-4 gap-y-2 text-xs">
                                        <div className="min-w-0 truncate"><span className="font-medium">Email:</span> {String(cd?.email || '-')}</div>
                                        <div><span className="font-medium">Telefon:</span> {String(cd?.telefon || '-')}</div>
                                        <div className="min-w-0 truncate"><span className="font-medium">Lokasyon:</span> {String(cd?.lokasyon || '-')}</div>
                                        <div className="min-w-0 truncate"><span className="font-medium">Şirket:</span> {String(cd?.mevcut_sirket || '-')}</div>
                                        <div className="min-w-0 truncate col-span-2"><span className="font-medium">Eğitim:</span> {String(cd?.egitim || '-')} {cd?.universite ? `/ ${cd?.universite as string}` : ''}</div>
                                        <div><span className="font-medium">Deneyim:</span> {String(cd?.toplam_deneyim_yil || '-')} yıl</div>
                                      </div>
                                      {/* Teknik Beceriler */}
                                      {cd?.teknik_beceriler && (
                                        <div className="w-full"><span className="text-xs font-medium">Teknik Beceriler:</span>
                                          <div className="flex flex-wrap gap-1 mt-1">
                                            {String(cd?.teknik_beceriler).split(',').map((s, i) => <Badge key={i} variant="secondary" className="text-[10px]">{s.trim()}</Badge>)}
                                          </div>
                                        </div>
                                      )}
{/* Diller */}
                                      {cd?.diller && (
                                        <div className="w-full mb-1 whitespace-normal break-words"><span className="text-xs font-medium">Diller:</span> <span className="text-xs">{String(cd.diller)}</span></div>
                                      )}
                                      {/* Sertifikalar */}
                                      {cd?.sertifikalar && (
                                        <div className="w-full mb-1 whitespace-normal break-words"><span className="text-xs font-medium">Sertifikalar:</span> <span className="text-xs">{String(cd.sertifikalar)}</span></div>
                                      )}
                                      {/* Bölüm */}
                                      {cd?.bolum && (
                                        <div className="w-full mb-1 whitespace-normal break-words"><span className="text-xs font-medium">Bölüm:</span> <span className="text-xs">{String(cd.bolum)}</span></div>
                                      )}
                                      {/* Görev Açıklamaları */}
                                      {cd?.deneyim_aciklama && (
                                        <div className="w-full mb-1 whitespace-normal break-words"><span className="text-xs font-medium">Görev Açıklamaları:</span> <span className="text-xs text-muted-foreground">{String(cd.deneyim_aciklama).length > 300 ? String(cd.deneyim_aciklama).substring(0, 300) + "..." : String(cd.deneyim_aciklama)}</span></div>
                                      )}
                                      {/* Deneyim Detay */}
                                      {cd?.deneyim_detay && (
                                        <div className="w-full text-xs whitespace-normal break-words"><span className="font-medium">Deneyim:</span> {String(cd?.deneyim_detay)}</div>
                                      )}
                                      {/* Blacklist Info */}
                                      {blacklistInfo && (
                                        <div className="border border-red-200 rounded p-3 bg-red-50">
                                          <div className="flex items-center justify-between mb-2">
                                            <div className="text-xs font-medium flex items-center gap-1 text-red-800"><Ban className="h-3 w-3" />Kara Liste Bilgisi</div>
                                            <Button size="sm" variant="outline" onClick={() => setRemoveBlacklistDialogOpen(true)} className="h-6 text-[10px] px-2 border-green-500 text-green-700 hover:bg-green-50">
                                              <CheckCircle className="h-3 w-3 mr-1" />Kara Listeden Çıkar
                                            </Button>
                                          </div>
                                          <div className="text-xs text-red-700 space-y-1">
                                            <div><span className="font-medium">Neden:</span> {blacklistInfo.reason}</div>
                                            <div><span className="font-medium">Ekleyen:</span> {blacklistInfo.blacklisted_by_name}</div>
                                            <div><span className="font-medium">Tarih:</span> {new Date(blacklistInfo.blacklisted_at).toLocaleDateString('tr-TR')}</div>
                                          </div>
                                        </div>
                                      )}
                                      {/* CV Intelligence */}
                                      <div className="border rounded p-3 bg-white">
                                        <div className="flex items-center justify-between mb-2">
                                          <div className="text-xs font-medium flex items-center gap-1"><User className="h-3 w-3" />CV Profil Analizi</div>
                                          <Button size="sm" variant="outline" onClick={() => handleAnalyzeIntelligence(cd.id)} disabled={analyzingIntelligence} className="h-6 text-[10px] px-2">
                                            {analyzingIntelligence ? <RefreshCw className="h-3 w-3 animate-spin mr-1" /> : <Brain className="h-3 w-3 mr-1" />}
                                            {(c.intelligence || intelligenceData[cd.id]) ? 'Yeniden Analiz' : 'Profil Analizi'}
                                          </Button>
                                        </div>
                                        {(c.intelligence || intelligenceData[cd.id]) ? (() => {
                                          const intel = c.intelligence || intelligenceData[cd.id]
                                          return (
                                            <div className="space-y-2 text-xs">
                                              <div className="flex items-center gap-2">
                                                <span className="font-medium">Kariyer Yolu:</span>
                                                <span>{intel?.career_path || '-'}</span>
                                              </div>
                                              <div className="flex items-center gap-2">
                                                <span className="font-medium">Seviye:</span>
                                                <LevelBadge level={intel?.level} />
                                                {intel?.experience_years && <span className="text-muted-foreground">({intel.experience_years} yıl)</span>}
                                              </div>
                                              {intel?.sectors && intel.sectors.length > 0 && (
                                                <div>
                                                  <span className="font-medium">Sektörler:</span>
                                                  <div className="flex flex-wrap gap-1 mt-1">
                                                    {intel.sectors.map((s, i) => <Badge key={i} variant="outline" className="text-[10px]">{s}</Badge>)}
                                                  </div>
                                                </div>
                                              )}
                                              {intel?.suitable_positions && intel.suitable_positions.length > 0 && (
                                                <div>
                                                  <span className="font-medium">Uygun Pozisyonlar:</span>
                                                  <div className="flex flex-wrap gap-1 mt-1">
                                                    {intel.suitable_positions.map((p, i) => <Badge key={i} variant="secondary" className="text-[10px]">{p}</Badge>)}
                                                  </div>
                                                </div>
                                              )}
                                              {intel?.key_skills && intel.key_skills.length > 0 && (
                                                <div>
                                                  <span className="font-medium">Öne Çıkan Beceriler:</span>
                                                  <div className="flex flex-wrap gap-1 mt-1">
                                                    {intel.key_skills.map((sk: any, i: number) => <Badge key={i} variant="outline" className="text-[10px] border-blue-200 bg-blue-50">{typeof sk === 'string' ? sk : sk.skill}</Badge>)}
                                                  </div>
                                                </div>
                                              )}
                                              {intel?.analyzed_at && (
                                                <div className="text-[10px] text-muted-foreground mt-1">
                                                  Son analiz: {new Date(intel.analyzed_at).toLocaleDateString('tr-TR')}
                                                </div>
                                              )}
                                            </div>
                                          )
                                        })() : (
                                          <div className="text-xs text-muted-foreground italic">Henüz profil analizi yapılmamış</div>
                                        )}
                                      </div>
                                      {/* Uyum Değerlendirmesi */}
                                      <div className="border rounded p-3 bg-white">
                                        <div className="flex items-center justify-between mb-2">
                                          <div className="text-xs font-medium flex items-center gap-2">
                                            <Brain className="h-3 w-3" />
                                            <span>Uyum Değerlendirmesi</span>
                                            {v3Evaluation[cd.id] && (
                                              <ScoreBadge score={cd.match_score || 0} size="md" />
                                            )}
                                          </div>
                                          <div className="flex gap-1">
                                            <Button size="sm" variant="outline" onClick={() => handleViewCV(cd.id)} disabled={!cd?.cv_dosya_adi} className="h-6 text-[10px] px-2" title={cd?.cv_dosya_adi ? 'CV Görüntüle' : 'CV yok'}>
                                              <FileText className="h-3 w-3 mr-1" />CV
                                            </Button>
                                            <Button size="sm" variant="outline" onClick={() => handleEvaluate(cd.id)} disabled={evaluating || v3Loading[cd.id]} className="h-6 text-[10px] px-2">
                                              {(evaluating || v3Loading[cd.id]) ? <RefreshCw className="h-3 w-3 animate-spin mr-1" /> : <Brain className="h-3 w-3 mr-1" />}
                                              {v3Evaluation[cd.id] ? 'Yeniden Değerlendir' : 'Değerlendir'}
                                            </Button>
                                            <Button size="sm" variant="outline" onClick={() => handleDownloadReport(cd.id)} disabled={!aie} className="h-6 text-[10px] px-2">
                                              <FileText className="h-3 w-3 mr-1" />Rapor
                                            </Button>
                                          </div>
                                        </div>
                                        {v3Evaluation[cd.id] ? (() => {
                                          const v3 = v3Evaluation[cd.id]
                                          const layers = [
                                            { key: 'technical_skills', label: 'Teknik Beceriler', max: 25 },
                                            { key: 'position_match', label: 'Pozisyon Uyumu', max: 25 },
                                            { key: 'experience_quality', label: 'Deneyim Kalitesi', max: 25 },
                                            { key: 'education', label: 'Eğitim', max: 15 },
                                            { key: 'other', label: 'Diğer', max: 10 }
                                          ]
                                          return (
                                            <div className="space-y-3">
                                              {/* Uygunluk Badge */}
                                              <div className="flex items-center gap-2">
                                                <Badge className={v3.eligible ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                                                  {v3.eligible ? '✓ Uygun' : '✗ Uygun Değil'}
                                                </Badge>
                                              </div>
                                              {/* AI Model Puanları */}
                                              <div className="p-2 bg-slate-50 rounded border text-xs">
                                                <div className="font-medium mb-2 flex items-center gap-1">
                                                  <span>🤖</span> AI Model Puanları
                                                </div>
                                                <div className="grid grid-cols-3 gap-2 text-center">
                                                  <div className="bg-white rounded p-1.5 border">
                                                    <div className="text-[10px] text-muted-foreground">Gemini</div>
                                                    <div className="font-bold text-blue-600">{v3.gemini_score}</div>
                                                  </div>
                                                  <div className="bg-white rounded p-1.5 border">
                                                    <div className="text-[10px] text-muted-foreground">Hermes</div>
                                                    <div className="font-bold text-purple-600">{v3.hermes_score}</div>
                                                  </div>
                                                  <div className="bg-white rounded p-1.5 border">
                                                    <div className="text-[10px] text-muted-foreground">OpenAI</div>
                                                    <div className="font-bold text-green-600">{v3.openai_score || '-'}</div>
                                                  </div>
                                                </div>
                                                <div className="mt-2 text-[10px] text-muted-foreground">
                                                  Method: <span className="font-medium">{v3.evaluation_method}</span>
                                                  {v3.claude_used && <span className="ml-2 text-orange-600">⚖️ Claude Hakem</span>}
                                                </div>
                                              </div>
                                              {/* FAZ 13.6: Skor Detayı (V2/V3 Ağırlıkları) */}
                                              {(candidateDetail as any)?.scoring_info && (
                                                <div className="p-2 bg-blue-50 rounded border text-xs">
                                                  <div className="font-medium mb-2 flex items-center gap-1">
                                                    <span>📊</span> Skor Detayı
                                                  </div>
                                                  <div className="grid grid-cols-4 gap-2 text-center">
                                                    <div className="bg-white rounded p-1.5 border">
                                                      <div className="text-[10px] text-muted-foreground">V2 (Keyword)</div>
                                                      <div className="font-bold text-blue-600">{(candidateDetail as any).scoring_info.v2_score}</div>
                                                      <div className="text-[9px] text-gray-400">x{(candidateDetail as any).scoring_info.v2_weight}</div>
                                                    </div>
                                                    <div className="bg-white rounded p-1.5 border">
                                                      <div className="text-[10px] text-muted-foreground">V3 (AI)</div>
                                                      <div className="font-bold text-purple-600">{(candidateDetail as any).scoring_info.v3_score}</div>
                                                      <div className="text-[9px] text-gray-400">x{(candidateDetail as any).scoring_info.v3_weight}</div>
                                                    </div>
                                                    <div className="bg-white rounded p-1.5 border border-green-300">
                                                      <div className="text-[10px] text-muted-foreground">=</div>
                                                      <div className="text-lg font-bold text-green-600">{(candidateDetail as any).scoring_info.match_score}</div>
                                                      <div className="text-[9px] text-gray-400">Final</div>
                                                    </div>
                                                  </div>
                                                  <div className="mt-1.5 text-[9px] text-gray-400 text-center">
                                                    {(candidateDetail as any).scoring_info.formula}
                                                  </div>
                                                </div>
                                              )}
                                              {/* Layer Scores */}
                                              <div className="space-y-2">
                                                {layers.map(layer => {
                                                  const data = v3.layer_scores[layer.key as keyof typeof v3.layer_scores]
                                                  if (!data) return null
                                                  const pct = Math.round((data.score / layer.max) * 100)
                                                  return (
                                                    <div key={layer.key} className="text-xs">
                                                      <div className="flex justify-between mb-1">
                                                        <span className="font-medium">{layer.label}</span>
                                                        <span>{data.score}/{layer.max}</span>
                                                      </div>
                                                      <div className="w-full bg-gray-200 rounded-full h-1.5">
                                                        <div className={`h-1.5 rounded-full ${pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${pct}%` }}></div>
                                                      </div>
                                                      <div className="text-[10px] text-gray-500 mt-0.5 break-words whitespace-normal leading-relaxed" title={data.reason}>{data.reason?.split('|')[0]?.trim()}</div>
                                                    </div>
                                                  )
                                                })}
                                              </div>
                                              {/* Güçlü ve Zayıf Yönler */}
                                              <div className="grid grid-cols-2 gap-3 text-xs">
                                                {v3.strengths && v3.strengths.length > 0 && (
                                                  <div>
                                                    <div className="font-medium text-green-700 mb-1">💪 Güçlü Yönler</div>
                                                    <ul className="list-disc list-inside space-y-0.5 text-[10px]">
                                                      {v3.strengths.slice(0, 3).map((s, i) => <li key={i} className="line-clamp-1">{s}</li>)}
                                                    </ul>
                                                  </div>
                                                )}
                                                {v3.weaknesses && v3.weaknesses.length > 0 && (
                                                  <div>
                                                    <div className="font-medium text-orange-700 mb-1">⚠️ Gelişim Alanları</div>
                                                    <ul className="list-disc list-inside space-y-0.5 text-[10px]">
                                                      {v3.weaknesses.slice(0, 3).map((w, i) => <li key={i} className="line-clamp-1">{w}</li>)}
                                                    </ul>
                                                  </div>
                                                )}
                                              </div>
                                            </div>
                                          )
                                        })() : (
                                          <div className="text-xs text-muted-foreground italic">Henüz AI değerlendirme yapılmamış. Değerlendirmek için butona tıklayın.</div>
                                        )}
                                      </div>
                                    </div>
                                  ); })() : <div className="text-center text-muted-foreground text-xs">Detay yüklenemedi</div>}
                                </TableCell>
                              </TableRow>
                            )}
                          </Fragment>

                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Akıllı Havuz - Title Mappings Panel */}
              {poolInfo?.pool_type === 'position' && (
                <div className="border rounded-md p-4 mt-4 bg-muted/30">
                  <div className="flex items-center justify-between mb-3 cursor-pointer" onClick={() => setTitlesExpanded(!titlesExpanded)}>
                    <h4 className="font-medium text-sm flex items-center gap-2">
                      <Brain className="h-4 w-4" />
                      Akıllı Havuz Başlıkları
                    </h4>
                    {titlesExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </div>

                  {titlesExpanded && (
                    <div className="space-y-4">
                      {titlesLoading ? (
                        <div className="text-center py-4 text-muted-foreground text-sm"><RefreshCw className="h-4 w-4 animate-spin inline mr-2" />Yükleniyor...</div>
                      ) : (
                        <>
                          {/* Onaylı Başlıklar */}
                          <div className="space-y-2">
                            <div className="text-xs font-medium text-muted-foreground">Onaylı Başlıklar</div>
                            {approvedTitles && (approvedTitles.exact?.length > 0 || approvedTitles.similar?.length > 0 || approvedTitles.related?.length > 0) ? (
                              <div className="space-y-1">
                                {approvedTitles.exact?.length > 0 && (
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-xs">🎯 Tam:</span>
                                    {approvedTitles.exact.map(t => <Badge key={t.id} variant="secondary" className="text-[10px]">{t.related_title}</Badge>)}
                                  </div>
                                )}
                                {approvedTitles.similar?.length > 0 && (
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-xs">🔄 Benzer:</span>
                                    {approvedTitles.similar.map(t => <Badge key={t.id} variant="secondary" className="text-[10px]">{t.related_title}</Badge>)}
                                  </div>
                                )}
                                {approvedTitles.related?.length > 0 && (
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-xs">🔗 İlişkili:</span>
                                    {approvedTitles.related.map(t => <Badge key={t.id} variant="secondary" className="text-[10px]">{t.related_title}</Badge>)}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="text-xs text-muted-foreground">Henüz onaylı başlık yok</div>
                            )}
                          </div>

                          {/* Onay Bekleyen */}
                          <div className="space-y-2 border-t pt-3">
                            <div className="text-xs font-medium text-muted-foreground">Onay Bekleyen</div>
                            {pendingTitles && (pendingTitles.exact?.length > 0 || pendingTitles.similar?.length > 0 || pendingTitles.related?.length > 0) ? (
                              <div className="space-y-2">
                                {[...pendingTitles.exact || [], ...pendingTitles.similar || [], ...pendingTitles.related || []].map(t => (
                                  <div key={t.id} className="flex items-center gap-2">
                                    <Checkbox
                                      checked={selectedPending.has(t.id)}
                                      onCheckedChange={() => togglePendingTitle(t.id)}
                                    />
                                    <span className="text-xs">
                                      {t.match_level === 'exact' ? '🎯' : t.match_level === 'similar' ? '🔄' : '🔗'}
                                    </span>
                                    <span className="text-sm">{t.related_title}</span>
                                    <Badge variant="outline" className="text-[9px]">{t.match_level}</Badge>
                                  </div>
                                ))}
                                <Button
                                  size="sm"
                                  onClick={handleApproveTitles}
                                  disabled={approving || selectedPending.size === 0}
                                  className="mt-2"
                                >
                                  {approving ? <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
                                  Seçilenleri Onayla ({selectedPending.size})
                                </Button>
                              </div>
                            ) : (
                              <div className="text-xs text-muted-foreground">Onay bekleyen başlık yok</div>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent></Card>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <Dialog open={createDialogOpen} onOpenChange={(o) => { setCreateDialogOpen(o); if (!o) { setUrlInput(''); setParsedData(null); setPositionForm({ pozisyon_adi: '', lokasyon: '', deneyim_yil: '0', egitim_seviyesi: '', keywords: '', aranan_nitelikler: '', is_tanimi: '' }) } }}>
        <DialogContent className={poolForm.pool_type === 'position' ? 'max-w-2xl max-h-[85vh] overflow-y-auto' : 'max-w-md'}>
          <DialogHeader><DialogTitle>{poolForm.pool_type === 'position' ? 'Yeni Pozisyon' : 'Yeni Departman'}</DialogTitle></DialogHeader>

          {poolForm.pool_type === 'position' ? (
            <Tabs defaultValue="url" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="url"><Link className="h-3.5 w-3.5 mr-1" />URL ile Ekle</TabsTrigger>
                <TabsTrigger value="document"><FileText className="h-3.5 w-3.5 mr-1" />Dokümandan Ekle</TabsTrigger>
              </TabsList>

              {/* TAB 1: URL ile Ekle */}
              <TabsContent value="url" className="space-y-3 mt-3">
                <div>
                  <Label className="text-sm">Kariyer.net İlan URL</Label>
                  <div className="flex gap-2 mt-1">
                    <Input value={urlInput} onChange={e => setUrlInput(e.target.value)} placeholder="https://www.kariyer.net/is-ilani/..." className="flex-1" />
                    <Button onClick={handleParseUrl} disabled={parseLoading || !urlInput}>
                      {parseLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      <span className="ml-1">{parsedData ? 'Yeniden Analiz Et' : 'Analiz'}</span>
                    </Button>
                  </div>
                </div>

                {parsedData && (
                  <div className="space-y-3 border-t pt-3">
                    <div className="text-sm font-medium text-green-600">Analiz başarılı! Aşağıdaki bilgileri düzenleyebilirsiniz:</div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Pozisyon Adı *</Label><Input value={positionForm.pozisyon_adi} onChange={e => setPositionForm({...positionForm, pozisyon_adi: e.target.value})} /></div>
                      <div><Label className="text-sm">Lokasyon</Label><Input value={positionForm.lokasyon} onChange={e => setPositionForm({...positionForm, lokasyon: e.target.value})} /></div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Deneyim (yıl)</Label><Input type="number" value={positionForm.deneyim_yil} onChange={e => setPositionForm({...positionForm, deneyim_yil: e.target.value})} /></div>
                      <div>
                        <Label className="text-sm">Eğitim Seviyesi</Label>
                        <Select value={positionForm.egitim_seviyesi || "none"} onValueChange={v => setPositionForm({...positionForm, egitim_seviyesi: v === "none" ? "" : v})}>
                          <SelectTrigger><SelectValue placeholder="Seçin..." /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">-</SelectItem>
                            <SelectItem value="Lise">Lise</SelectItem>
                            <SelectItem value="Ön Lisans">Ön Lisans</SelectItem>
                            <SelectItem value="Lisans">Lisans</SelectItem>
                            <SelectItem value="Yüksek Lisans">Yüksek Lisans</SelectItem>
                            <SelectItem value="Doktora">Doktora</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div><Label className="text-sm">Anahtar Kelimeler (virgül ile)</Label><Input value={positionForm.keywords} onChange={e => setPositionForm({...positionForm, keywords: e.target.value})} /></div>
                    <div><Label className="text-sm">Aranan Nitelikler</Label><Textarea value={positionForm.aranan_nitelikler} onChange={e => setPositionForm({...positionForm, aranan_nitelikler: e.target.value})} rows={3} /></div>
                    <div><Label className="text-sm">İş Tanımı</Label><Textarea value={positionForm.is_tanimi} onChange={e => setPositionForm({...positionForm, is_tanimi: e.target.value})} rows={3} /></div>
                    <Button onClick={handleSaveParsed} disabled={savingPosition || !positionForm.pozisyon_adi} className="w-full">
                      {savingPosition ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}Kaydet
                    </Button>
                  </div>
                )}
              </TabsContent>

              {/* TAB 2: Dokümandan Ekle */}
              <TabsContent value="document" className="space-y-3 mt-3">
                <div>
                  <Label className="text-sm">İlan Dokümanı (PDF, Word, JPEG)</Label>
                  <Input
                    type="file"
                    accept=".pdf,.docx,.doc,.jpg,.jpeg,.png"
                    onChange={e => {
                      const file = e.target.files?.[0]
                      if (file) {
                        setParseLoading(true)
                        setParsedData(null)
                        const formData = new FormData()
                        formData.append('file', file)
                        fetch(API + '/api/pools/position/from-document', {
                          method: 'POST',
                          headers: { 'Authorization': H()['Authorization'] },
                          body: formData
                        })
                          .then(r => r.json())
                          .then(res => {
                            if (res.success && res.data) {
                              setParsedData(res.data)
                              setPositionForm({
                                pozisyon_adi: res.data.pozisyon_adi || '',
                                lokasyon: res.data.lokasyon || '',
                                deneyim_yil: String(res.data.deneyim_yil || 0),
                                egitim_seviyesi: res.data.egitim_seviyesi || '',
                                keywords: Array.isArray(res.data.keywords) ? res.data.keywords.join(', ') : (res.data.keywords || ''),
                                aranan_nitelikler: res.data.aranan_nitelikler || '',
                                is_tanimi: res.data.is_tanimi || ''
                              })
                            } else {
                              toast.error(res.detail || res.message || 'Parse hatası')
                            }
                          })
                          .catch(err => toast.error('Hata: ' + err.message))
                          .finally(() => setParseLoading(false))
                      }
                    }}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, DOC, JPG, JPEG, PNG desteklenir</p>
                </div>

                {parseLoading && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin" /> Doküman analiz ediliyor...
                  </div>
                )}

                {parsedData && (
                  <div className="space-y-3 border-t pt-3">
                    <div className="text-sm font-medium text-green-600">Analiz başarılı! Aşağıdaki bilgileri düzenleyebilirsiniz:</div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Pozisyon Adı *</Label><Input value={positionForm.pozisyon_adi} onChange={e => setPositionForm({...positionForm, pozisyon_adi: e.target.value})} /></div>
                      <div><Label className="text-sm">Lokasyon</Label><Input value={positionForm.lokasyon} onChange={e => setPositionForm({...positionForm, lokasyon: e.target.value})} /></div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Deneyim (yıl)</Label><Input type="number" value={positionForm.deneyim_yil} onChange={e => setPositionForm({...positionForm, deneyim_yil: e.target.value})} /></div>
                      <div>
                        <Label className="text-sm">Eğitim Seviyesi</Label>
                        <Select value={positionForm.egitim_seviyesi || "none"} onValueChange={v => setPositionForm({...positionForm, egitim_seviyesi: v === "none" ? "" : v})}>
                          <SelectTrigger><SelectValue placeholder="Seçin..." /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">-</SelectItem>
                            <SelectItem value="Lise">Lise</SelectItem>
                            <SelectItem value="Ön Lisans">Ön Lisans</SelectItem>
                            <SelectItem value="Lisans">Lisans</SelectItem>
                            <SelectItem value="Yüksek Lisans">Yüksek Lisans</SelectItem>
                            <SelectItem value="Doktora">Doktora</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div><Label className="text-sm">Anahtar Kelimeler (virgül ile)</Label><Input value={positionForm.keywords} onChange={e => setPositionForm({...positionForm, keywords: e.target.value})} /></div>
                    <div><Label className="text-sm">Aranan Nitelikler</Label><Textarea value={positionForm.aranan_nitelikler} onChange={e => setPositionForm({...positionForm, aranan_nitelikler: e.target.value})} rows={3} /></div>
                    <div><Label className="text-sm">İş Tanımı</Label><Textarea value={positionForm.is_tanimi} onChange={e => setPositionForm({...positionForm, is_tanimi: e.target.value})} rows={3} /></div>
                    <Button onClick={handleSaveParsed} disabled={savingPosition || !positionForm.pozisyon_adi} className="w-full">
                      {savingPosition ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}Kaydet
                    </Button>
                  </div>
                )}
              </TabsContent>



            </Tabs>
          ) : (
            /* Departman ekleme (eski basit form) */
            <div className="space-y-3">
              <div><Label className="text-sm">Ad *</Label><Input value={poolForm.name} onChange={e => setPoolForm({...poolForm, name: e.target.value})} placeholder="Örnek: Yazılım Geliştirme" /></div>
              <div><Label className="text-sm">Açıklama</Label><Textarea value={poolForm.description} onChange={e => setPoolForm({...poolForm, description: e.target.value})} rows={2} /></div>
              <DialogFooter><Button variant="outline" onClick={() => setCreateDialogOpen(false)}>İptal</Button><Button onClick={handleCreatePool} disabled={!poolForm.name}>Oluştur</Button></DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] flex flex-col">
          <DialogHeader><DialogTitle>İlan Detayı ve Düzenleme Ekranı</DialogTitle></DialogHeader>
          <div className="space-y-4 flex-1 overflow-y-auto">
            <div><Label className="text-sm">Ad *</Label><Input value={poolForm.name} onChange={e => setPoolForm({...poolForm, name: e.target.value})} /></div>
            <div><Label className="text-sm">Açıklama</Label><Textarea value={poolForm.description} onChange={e => setPoolForm({...poolForm, description: e.target.value})} rows={2} /></div>

            {/* Keyword Yönetimi */}
            {poolInfo?.pool_type === 'position' && (
              <div className="border rounded-md p-3 space-y-3">
                <Label className="text-sm font-medium">Anahtar Kelimeler</Label>
                {/* Mevcut Keywords */}
                <div className="flex flex-wrap gap-1.5">
                  {editKeywords.length === 0 ? (
                    <span className="text-xs text-muted-foreground">Henüz keyword yok</span>
                  ) : (
                    editKeywords.map((kw, i) => (
                      <Badge key={i} variant="secondary" className="text-xs pr-1 flex items-center gap-1">
                        {kw}
                        <button
                          onClick={() => handleRemoveKeyword(kw)}
                          disabled={keywordLoading}
                          className="ml-1 hover:bg-muted-foreground/20 rounded p-0.5"
                          title="Kaldır"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))
                  )}
                </div>
                {/* Yeni Keyword Ekle */}
                <div className="flex gap-2">
                  <Input
                    value={newKeyword}
                    onChange={e => setNewKeyword(e.target.value)}
                    placeholder="Yeni keyword..."
                    className="flex-1 h-8 text-sm"
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddKeyword() } }}
                  />
                  <Button size="sm" onClick={handleAddKeyword} disabled={keywordLoading || !newKeyword.trim()}>
                    {keywordLoading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    <span className="ml-1">Ekle</span>
                  </Button>
                </div>
              </div>
            )}
          </div>
          <DialogFooter className="shrink-0 border-t pt-4"><Button variant="outline" onClick={() => setEditDialogOpen(false)}>İptal</Button><Button onClick={handleUpdatePool} disabled={!poolForm.name}>Kaydet</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteConfirm !== null} onOpenChange={o => { if (!o) setDeleteConfirm(null) }}>
        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Havuz Sil</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Bu havuzu silmek istediğinizden emin misiniz? Adaylar Genel Havuz'a taşınacaktır.</p>
          <DialogFooter><Button variant="outline" onClick={() => setDeleteConfirm(null)}>İptal</Button><Button variant="destructive" onClick={handleDeletePool}>Sil</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Aday Ata</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-sm mb-2 block">Aday Seç</Label>
              <Popover open={candidateSearchOpen} onOpenChange={setCandidateSearchOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" role="combobox" className="w-full justify-between">
                    {selectedCandidate ? selectedCandidate.ad_soyad : "Aday ara veya seç..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[350px] p-0">
                  <Command>
                    <CommandInput placeholder="İsim ile ara..." />
                    <CommandList>
                      <CommandEmpty>Aday bulunamadı.</CommandEmpty>
                      <CommandGroup>
                        {candidateList.map((c) => (
                          <CommandItem key={c.id} value={c.ad_soyad} onSelect={() => {
                            setSelectedCandidate(c)
                            setAssignCandidateId(String(c.id))
                            setCandidateSearchOpen(false)
                          }}>
                            <Check className={cn("mr-2 h-4 w-4", selectedCandidate?.id === c.id ? "opacity-100" : "opacity-0")} />
                            <div className="flex flex-col">
                              <span className="font-medium">{c.ad_soyad}</span>
                              {c.mevcut_pozisyon && <span className="text-xs text-muted-foreground">{c.mevcut_pozisyon}</span>}
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignDialogOpen(false)}>İptal</Button>
            <Button onClick={handleAssignCandidate} disabled={!selectedCandidate}>Ata</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* B5: Görev Tanımı Upload Modal */}
      <Dialog open={jdUploadOpen} onOpenChange={setJdUploadOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Görev Tanımı Yükle</DialogTitle>
          </DialogHeader>

          {!jdResult ? (
            <div className="space-y-4">
              {!jdUploading ? (
                <div className="border-2 border-dashed rounded-lg p-6 text-center">
                  <FileText className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground mb-3">PDF veya DOCX dosyası sürükleyin veya tıklayarak seçin</p>
                  <Input
                    type="file"
                    accept=".pdf,.docx,.doc"
                    className="max-w-[250px] mx-auto"
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file) return

                      // Dosya tipi kontrolü
                      const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']
                      const allowedExts = ['.pdf', '.docx', '.doc']
                      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))

                      if (!allowedTypes.includes(file.type) && !allowedExts.includes(ext)) {
                        toast.error('Sadece PDF, DOCX veya DOC dosyaları yüklenebilir')
                        return
                      }

                      if (file.size > 10 * 1024 * 1024) {
                        toast.error('Dosya boyutu 10MB\'dan küçük olmalı')
                        return
                      }

                      // Upload
                      setJdUploading(true)
                      const formData = new FormData()
                      formData.append('file', file)

                      try {
                        const res = await fetch(`${API}/api/pools/${selectedPoolId}/job-description`, {
                          method: 'POST',
                          headers: { 'Authorization': H()['Authorization'] },
                          body: formData
                        })
                        const data = await res.json()

                        if (data.success) {
                          setJdResult({
                            success: true,
                            gorev_sayisi: data.data?.gorev_sayisi || 0,
                            keyword_sayisi: data.data?.keyword_sayisi || 0,
                            title_sayisi: data.data?.title_sayisi || 0,
                            rescore_sayisi: data.data?.rescore_sayisi || 0
                          })
                          toast.success('Görev tanımı başarıyla analiz edildi')
                          // Pozisyon verilerini yenile
                          if (selectedPoolId) {
                            loadCandidates(selectedPoolId)
                          }
                        } else {
                          toast.error(data.detail || 'Görev tanımı yüklenirken hata oluştu')
                        }
                      } catch (err) {
                        toast.error('Bağlantı hatası')
                      } finally {
                        setJdUploading(false)
                      }
                    }}
                  />
                  <p className="text-xs text-muted-foreground mt-2">Maksimum 10MB</p>
                </div>
              ) : (
                <div className="text-center py-8">
                  <RefreshCw className="h-8 w-8 mx-auto animate-spin text-primary mb-3" />
                  <p className="text-sm font-medium">Görev tanımı analiz ediliyor...</p>
                  <p className="text-xs text-muted-foreground mt-1">Bu işlem birkaç saniye sürebilir</p>
                </div>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setJdUploadOpen(false)} disabled={jdUploading}>İptal</Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2 text-green-700 font-medium mb-3">
                  <Check className="h-5 w-5" />
                  Görev Tanımı Analiz Edildi
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">📋 Bulunan Görevler:</span>
                    <span className="font-medium">{jdResult.gorev_sayisi}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">🔑 Eklenen Keyword'ler:</span>
                    <span className="font-medium">{jdResult.keyword_sayisi}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">🏷️ Önerilen Başlıklar:</span>
                    <span className="font-medium">{jdResult.title_sayisi} <span className="text-xs text-muted-foreground">(onay bekliyor)</span></span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">👥 Güncellenen Adaylar:</span>
                    <span className="font-medium">{jdResult.rescore_sayisi}</span>
                  </div>
                </div>
              </div>

              <DialogFooter>
                <Button onClick={() => setJdUploadOpen(false)}>Kapat</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Kara Liste Dialog */}
      <Dialog open={blacklistDialogOpen} onOpenChange={(o) => { setBlacklistDialogOpen(o); if (!o) { setBlacklistReason(''); setBlacklistCandidateId(null); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Ban className="h-5 w-5 text-red-600" />
              Kara Listeye Al
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-800 font-medium">⚠️ Bu işlem:</p>
              <ul className="text-sm text-red-700 mt-1 list-disc list-inside">
                <li>Adayı tüm havuzlardan çıkaracak</li>
                <li>Aktif mülakatları iptal edecek</li>
                <li>Aday tekrar CV gönderirse sisteme alınmayacak</li>
              </ul>
            </div>
            <div>
              <label className="text-sm font-medium">Kara Liste Nedeni *</label>
              <textarea
                className="w-full mt-1 p-2 border rounded-md text-sm min-h-[80px]"
                placeholder="Örn: Mülakata gelmedi, iletişime geçilemiyor..."
                value={blacklistReason}
                onChange={(e) => setBlacklistReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBlacklistDialogOpen(false)}>İptal</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (!blacklistCandidateId || !blacklistReason.trim()) {
                  toast.error('Kara liste nedeni zorunludur');
                  return;
                }
                if (blacklistReason.trim().length < 5) {
                  toast.error('Kara liste nedeni en az 5 karakter olmalı');
                  return;
                }
                setBlacklistLoading(true);
                try {
                  const res = await fetch(`${API}/api/candidates/${blacklistCandidateId}/blacklist`, {
                    method: 'POST',
                    headers: H(),
                    body: JSON.stringify({ reason: blacklistReason.trim() })
                  });
                  const data = await res.json();
                  if (data.success) {
                    toast.success('Aday kara listeye alındı');
                    setBlacklistDialogOpen(false);
                    setBlacklistReason('');
                    setBlacklistCandidateId(null);
                    // Listeyi yenile
                    if (selectedPoolId) {
                      loadCandidates(selectedPoolId);
                    }
                  } else {
                    toast.error(data.error || data.detail || 'Kara listeye ekleme başarısız');
                  }
                } catch (err) {
                  toast.error('Bir hata oluştu');
                } finally {
                  setBlacklistLoading(false);
                }
              }}
              disabled={blacklistLoading || !blacklistReason.trim()}
            >
              {blacklistLoading ? 'İşleniyor...' : 'Kara Listeye Al'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Kara Listeden Çıkar Dialog */}
      <Dialog open={removeBlacklistDialogOpen} onOpenChange={(o) => { setRemoveBlacklistDialogOpen(o); if (!o) setRemoveBlacklistReason(''); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Kara Listeden Çıkar
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <p className="text-sm text-green-800 font-medium">Bu işlem:</p>
              <ul className="text-sm text-green-700 mt-1 list-disc list-inside">
                <li>Adayın kara liste kaydını kaldıracak</li>
                <li>Aday tekrar CV gönderebilecek</li>
                <li>Aday havuzlara eklenebilecek</li>
              </ul>
            </div>
            <div>
              <label className="text-sm font-medium">Çıkarma Nedeni (Opsiyonel)</label>
              <textarea
                className="w-full mt-1 p-2 border rounded-md text-sm min-h-[60px]"
                placeholder="Örn: Yanlış kara liste, tekrar değerlendirilecek..."
                value={removeBlacklistReason}
                onChange={(e) => setRemoveBlacklistReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoveBlacklistDialogOpen(false)}>İptal</Button>
            <Button
              className="bg-green-600 hover:bg-green-700"
              onClick={async () => {
                if (!expandedCandidate) return;
                setRemoveBlacklistLoading(true);
                try {
                  const reasonParam = removeBlacklistReason.trim() ? `?removal_reason=${encodeURIComponent(removeBlacklistReason.trim())}` : '';
                  const res = await fetch(`${API}/api/candidates/${expandedCandidate}/blacklist${reasonParam}`, {
                    method: 'DELETE',
                    headers: H()
                  });
                  const data = await res.json();
                  if (data.success) {
                    toast.success('Aday kara listeden çıkarıldı');
                    setRemoveBlacklistDialogOpen(false);
                    setRemoveBlacklistReason('');
                    setBlacklistInfo(null);
                    if (selectedPoolId) {
                      loadCandidates(selectedPoolId);
                    }
                  } else {
                    toast.error(data.error || data.detail || 'Kara listeden çıkarma başarısız');
                  }
                } catch (err) {
                  toast.error('Bir hata oluştu');
                } finally {
                  setRemoveBlacklistLoading(false);
                }
              }}
              disabled={removeBlacklistLoading}
            >
              {removeBlacklistLoading ? 'İşleniyor...' : 'Kara Listeden Çıkar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Aday Detay Modalı - Yeni Dizayn */}
      <Dialog open={candidateDetailModalOpen} onOpenChange={setCandidateDetailModalOpen}>
        <DialogContent className="max-w-[90vw] min-w-[900px] max-h-[90vh] overflow-y-auto p-0">
          {selectedCandidateDetail && (
            <>
              {/* HEADER */}
              <div className="flex items-center justify-between p-4 border-b bg-white sticky top-0 z-10">
                <h2 className="text-2xl font-bold">{selectedCandidateDetail.ad_soyad || 'Aday Detayı'}</h2>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleViewCV(selectedCandidateDetail.id)} disabled={!selectedCandidateDetail.cv_dosya_adi}>
                    <FileText className="h-4 w-4 mr-1" />CV Görüntüle
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => {
                    setCandidateDetailModalOpen(false)
                    const params = new URLSearchParams({
                      newInterview: 'true',
                      candidateId: String(selectedCandidateDetail.id || ''),
                      candidateName: selectedCandidateDetail.ad_soyad || '',
                      positionId: String(poolInfo?.id || ''),
                      positionName: poolInfo?.name || ''
                    })
                    navigate({ to: `/mulakat-takvimi?${params.toString()}` })
                  }}>
                    <Calendar className="h-4 w-4 mr-1" />Mülakat Planla
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => {
                    // Genel havuza taşı
                    fetch(`${API}/api/candidates/${selectedCandidateDetail.id}/elen`, { method: 'POST', headers: H() })
                      .then(r => r.json())
                      .then(res => {
                        if (res.success) {
                          toast.success('Aday genel havuza taşındı')
                          setCandidateDetailModalOpen(false)
                          if (selectedPoolId) loadCandidates(selectedPoolId)
                          loadTree()
                        } else {
                          toast.error(res.detail || 'İşlem başarısız')
                        }
                      })
                      .catch(() => toast.error('Bağlantı hatası'))
                  }}>
                    <Inbox className="h-4 w-4 mr-1" />Genel Havuza
                  </Button>
                  <Button variant="outline" size="sm" className="text-red-500 hover:text-red-600" onClick={() => { setCandidateDetailModalOpen(false); }}>
                    <Archive className="h-4 w-4 mr-1" />Arşivle
                  </Button>
                </div>
              </div>

              {/* BODY - 2 SÜTUN */}
              <div className="grid grid-cols-2 gap-6 p-6 bg-gray-50">
                {/* SOL SÜTUN */}
                <div className="space-y-6">
                  {/* Kariyer Bilgileri */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <h3 className="font-semibold mb-4">Kariyer Bilgileri</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Mevcut Pozisyon</p>
                        <p className="font-semibold text-lg">{selectedCandidateDetail.mevcut_pozisyon || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Deneyim</p>
                        <p className="font-semibold text-lg">{selectedCandidateDetail.toplam_deneyim_yil ? `${selectedCandidateDetail.toplam_deneyim_yil} yıl` : '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Mevcut Şirket</p>
                        <p className="font-semibold text-lg">{selectedCandidateDetail.mevcut_sirket || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Durum</p>
                        <Badge variant={selectedCandidateDetail.durum === 'blacklist' ? 'destructive' : 'secondary'} className="text-sm">
                          {STATUS_MAP[selectedCandidateDetail.durum as keyof typeof STATUS_MAP]?.label || selectedCandidateDetail.durum || '-'}
                        </Badge>
                      </div>
                    </div>
                  </div>

                  {/* Uyum Değerlendirmesi */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <h3 className="font-semibold mb-4">Uyum Değerlendirmesi</h3>
                    <div className="space-y-4">
                      {/* AI Model Skorları */}
                      <div>
                        <h4 className="text-sm font-medium text-gray-600 mb-2">AI Model Skorları</h4>
                        <div className="grid grid-cols-4 gap-2">
                          <div className="text-center p-2 bg-white rounded">
                            <p className="text-xs text-gray-500">Gemini</p>
                            <p className="font-bold">{selectedCandidateDetail.gemini_score || '-'}%</p>
                          </div>
                          <div className="text-center p-2 bg-white rounded">
                            <p className="text-xs text-gray-500">Hermes</p>
                            <p className="font-bold">{selectedCandidateDetail.hermes_score || '-'}%</p>
                          </div>
                          <div className="text-center p-2 bg-white rounded">
                            <p className="text-xs text-gray-500">OpenAI</p>
                            <p className="font-bold">{selectedCandidateDetail.openai_score || '-'}%</p>
                          </div>
                          <div className="text-center p-2 bg-white rounded">
                            <p className="text-xs text-gray-500">Ortalama</p>
                            <p className="font-bold">{selectedCandidateDetail.avg_ai_score || '-'}%</p>
                          </div>
                        </div>
                      </div>
                      {/* Kelime Skoru ve Toplam Puan */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="text-center p-4 bg-white rounded-lg">
                          <p className="text-sm text-gray-500">Kelime Skoru</p>
                          <p className="text-4xl font-bold text-blue-600">{selectedCandidateDetail.keyword_score || selectedCandidateDetail.match_score || '-'}</p>
                        </div>
                        <div className="text-center p-4 bg-white rounded-lg">
                          <p className="text-sm text-gray-500">Toplam Puan</p>
                          <p className="text-4xl font-bold text-green-600">{selectedCandidateDetail.match_score || selectedCandidateDetail.uyum_puani || '-'}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* SAĞ SÜTUN */}
                <div className="space-y-6">
                  {/* Kişisel Bilgiler */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <h3 className="font-semibold mb-4">Kişisel Bilgiler</h3>
                    <div className="space-y-3">
                      <div>
                        <p className="text-xs text-gray-500">E-posta</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.email || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Telefon</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.telefon || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Doğum Tarihi</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.dogum_tarihi || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Lokasyon</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.lokasyon || '-'}</p>
                      </div>
                    </div>
                  </div>

                  {/* Eğitim Bilgileri */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <h3 className="font-semibold mb-4">Eğitim Bilgileri</h3>
                    <div className="space-y-3">
                      <div>
                        <p className="text-xs text-gray-500">Eğitim Seviyesi</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.egitim || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Üniversite</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.universite || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Bölüm</p>
                        <p className="font-medium bg-white px-3 py-2 rounded mt-1">{selectedCandidateDetail.bolum || '-'}</p>
                      </div>
                    </div>
                  </div>

                  {/* Diller */}
                  {selectedCandidateDetail.diller && (
                    <div className="p-4 bg-sky-50 rounded-lg">
                      <h3 className="font-semibold mb-3">Diller</h3>
                      <p className="text-sm bg-white rounded px-3 py-2">{selectedCandidateDetail.diller}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* ORTA BÖLÜM - BADGE'LER */}
              <div className="px-6 pb-4 space-y-4 bg-gray-50">
                {/* Teknik Beceriler */}
                {selectedCandidateDetail.teknik_beceriler && (
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <label className="text-sm text-gray-500 font-medium">Öne Çıkan Beceriler</label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {String(selectedCandidateDetail.teknik_beceriler).split(',').map((skill: string, i: number) => (
                        <span key={i} className="px-3 py-1 bg-white rounded-full text-sm border">{skill.trim()}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sertifikalar */}
                {selectedCandidateDetail.sertifikalar && (
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <label className="text-sm text-gray-500 font-medium">Sertifikalar</label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {String(selectedCandidateDetail.sertifikalar).split(',').map((cert: string, i: number) => (
                        <span key={i} className="px-3 py-1 bg-white rounded-full text-sm border">{cert.trim()}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* SKORLAR - PROGRESS BAR'LAR */}
              <div className="px-6 py-4 bg-gray-50">
                <div className="grid grid-cols-3 gap-4">
                  {/* Teknik Beceriler */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="font-medium text-sm">Teknik Beceriler</span>
                      <span className="text-blue-600 font-bold text-sm">{selectedCandidateDetail.teknik_puan || '-'}/25</span>
                    </div>
                    <div className="h-3 bg-white rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full transition-all" style={{width: `${((selectedCandidateDetail.teknik_puan || 0) / 25) * 100}%`}}></div>
                    </div>
                  </div>

                  {/* Pozisyon Uyumu */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="font-medium text-sm">Pozisyon Uyumu</span>
                      <span className="text-blue-600 font-bold text-sm">{selectedCandidateDetail.pozisyon_puan || '-'}/25</span>
                    </div>
                    <div className="h-3 bg-white rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full transition-all" style={{width: `${((selectedCandidateDetail.pozisyon_puan || 0) / 25) * 100}%`}}></div>
                    </div>
                  </div>

                  {/* Deneyim */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="font-medium text-sm">Deneyim</span>
                      <span className="text-blue-600 font-bold text-sm">{selectedCandidateDetail.deneyim_puan || '-'}/25</span>
                    </div>
                    <div className="h-3 bg-white rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full transition-all" style={{width: `${((selectedCandidateDetail.deneyim_puan || 0) / 25) * 100}%`}}></div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mt-4">
                  {/* Eğitim */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="font-medium text-sm">Eğitim</span>
                      <span className="text-blue-600 font-bold text-sm">{selectedCandidateDetail.egitim_puan || '-'}/15</span>
                    </div>
                    <div className="h-3 bg-white rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full transition-all" style={{width: `${((selectedCandidateDetail.egitim_puan || 0) / 15) * 100}%`}}></div>
                    </div>
                  </div>

                  {/* Diğer */}
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="font-medium text-sm">Diğer</span>
                      <span className="text-blue-600 font-bold text-sm">{selectedCandidateDetail.diger_puan || '-'}/10</span>
                    </div>
                    <div className="h-3 bg-white rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full transition-all" style={{width: `${((selectedCandidateDetail.diger_puan || 0) / 10) * 100}%`}}></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* EN ALT - GÜÇLÜ YÖNLER & GELİŞİM ALANLARI */}
              <div className="px-6 pb-6 bg-gray-50">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <h3 className="font-semibold mb-2">Güçlü Yönler</h3>
                    <p className="text-gray-600 text-sm">{selectedCandidateDetail.guclu_yonler || selectedCandidateDetail.strengths || '-'}</p>
                  </div>
                  <div className="p-4 bg-sky-50 rounded-lg">
                    <h3 className="font-semibold mb-2">Gelişim Alanları</h3>
                    <p className="text-gray-600 text-sm">{selectedCandidateDetail.gelisim_alanlari || selectedCandidateDetail.improvements || '-'}</p>
                  </div>
                </div>
              </div>

              {/* FOOTER */}
              <div className="flex justify-end p-4 border-t bg-white sticky bottom-0">
                <Button variant="outline" onClick={() => setCandidateDetailModalOpen(false)}>Kapat</Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
