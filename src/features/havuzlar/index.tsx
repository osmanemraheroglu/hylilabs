import { toast } from 'sonner'
import { useState, useEffect, useCallback, Fragment } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  FolderTree, Plus, Edit, Trash2, RefreshCw, ChevronRight, ChevronDown,
  Archive, Inbox, Building2, Target, UserPlus, ArrowRightLeft, Search,
  Download, ChevronUp, Brain, FileText, Link, X
} from 'lucide-react'

const API = 'http://***REMOVED***:8000'
const H = () => ({ 'Authorization': `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' })

interface Pool { id: number; name: string; icon: string; pool_type: string; is_system: number; keywords: string|null; description: string|null }
interface SysPool { id: number; name: string; icon: string; is_system: boolean; candidate_count: number }
interface Position { id: number; name: string; icon: string; keywords: string|null; description: string|null; candidate_count: number }
interface Dept { id: number; name: string; icon: string; candidate_count: number; positions: Position[]; total_position_candidates: number }
interface TreeData { system_pools: SysPool[]; departments: Dept[] }
interface Candidate { id: number; ad_soyad: string; email: string|null; telefon: string|null; mevcut_pozisyon: string|null; toplam_deneyim_yil: number|null; lokasyon: string|null; match_score?: number; match_reason?: string; remaining_days?: number; assignment_type?: string; status?: string }

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  aktif: { label: 'Aktif', color: 'bg-blue-100 text-blue-800' },
  beklemede: { label: 'Beklemede', color: 'bg-yellow-100 text-yellow-800' },
  inceleniyor: { label: 'İnceleniyor', color: 'bg-purple-100 text-purple-800' },
  mulakat: { label: 'Mülakat', color: 'bg-cyan-100 text-cyan-800' },
  teklif: { label: 'Teklif', color: 'bg-green-100 text-green-800' },
  red: { label: 'Red', color: 'bg-red-100 text-red-800' },
}

function dayColor(d: number|undefined) {
  if (d === undefined) return ''
  if (d <= 7) return 'bg-red-100 text-red-700'
  if (d <= 15) return 'bg-orange-100 text-orange-700'
  return 'bg-green-100 text-green-700'
}

function scoreIcon(s: number) {
  if (s >= 80) return { icon: '\uD83D\uDFE2', label: 'Tam Uyumlu' }
  if (s >= 50) return { icon: '\uD83D\uDFE1', label: 'Kısmi Uyumlu' }
  return { icon: '\uD83D\uDD34', label: 'Uyumsuz' }
}

export default function Havuzlar() {
  const [tree, setTree] = useState<TreeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPoolId, setSelectedPoolId] = useState<number | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [poolInfo, setPoolInfo] = useState<Pool | null>(null)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [expandedDepts, setExpandedDepts] = useState<Set<number>>(new Set())
  const [selectedCandidates, setSelectedCandidates] = useState<Set<number>>(new Set())
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
  const [transferDialogOpen, setTransferDialogOpen] = useState(false)
  const [statusDialogOpen, setStatusDialogOpen] = useState(false)

  // Forms
  const [poolForm, setPoolForm] = useState({ name: '', pool_type: 'department', parent_id: '', icon: '', keywords: '', description: '', gerekli_deneyim_yil: '0', gerekli_egitim: '', lokasyon: '' })
  const [assignCandidateId, setAssignCandidateId] = useState('')
  const [transferTargetId, setTransferTargetId] = useState('')
  const [statusValue, setStatusValue] = useState('')
  const [allPools, setAllPools] = useState<Array<{ id: number; name: string; pool_type: string }>>([])

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

  // AI Evaluation
  const [evaluating, setEvaluating] = useState(false)
  const [downloadingCVs, setDownloadingCVs] = useState(false)

  const loadTree = useCallback(() => {
    setLoading(true)
    fetch(`${API}/api/pools/hierarchical`, { headers: H() })
      .then(r => r.json()).then(res => {
        if (res.success) { setTree(res.data); const ids = new Set<number>(); res.data.departments?.forEach((d: Dept) => ids.add(d.id)); setExpandedDepts(ids) }
      }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const loadAllPools = useCallback(() => {
    fetch(`${API}/api/pools`, { headers: H() }).then(r => r.json()).then(res => { if (res.success) setAllPools(res.data) }).catch(console.error)
  }, [])

  const loadCandidates = useCallback((poolId: number) => {
    setCandidatesLoading(true); setSelectedCandidates(new Set()); setExpandedCandidate(null); setCandidateDetail(null)
    fetch(`${API}/api/pools/${poolId}/candidates`, { headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { setCandidates(res.data); setPoolInfo(res.pool) } })
      .catch(console.error).finally(() => setCandidatesLoading(false))
  }, [])

  useEffect(() => { loadTree(); loadAllPools() }, [loadTree, loadAllPools])
  useEffect(() => { if (selectedPoolId) loadCandidates(selectedPoolId) }, [selectedPoolId, loadCandidates])

  const toggleDept = (id: number) => setExpandedDepts(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const toggleCandidate = (id: number) => setSelectedCandidates(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })

  // Candidate Detail
  const loadDetail = (candidateId: number) => {
    if (expandedCandidate === candidateId) { setExpandedCandidate(null); setCandidateDetail(null); return }
    setExpandedCandidate(candidateId); setDetailLoading(true); setCandidateDetail(null)
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/detail`, { headers: H() })
      .then(r => r.json()).then(res => { if (res.success) setCandidateDetail(res) })
      .catch(console.error).finally(() => setDetailLoading(false))
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
      .then(r => r.json()).then(res => { if (res.success) { setCreateDialogOpen(false); resetPoolForm(); loadTree(); loadAllPools() } else alert(res.detail || 'Hata') })
  }

  const handleUpdatePool = () => {
    if (!selectedPoolId || !poolForm.name) return
    fetch(`${API}/api/pools/${selectedPoolId}`, { method: 'PUT', headers: H(), body: JSON.stringify({ name: poolForm.name, keywords: poolForm.keywords ? poolForm.keywords.split(',').map(k => k.trim()).filter(Boolean) : [], description: poolForm.description }) })
      .then(r => r.json()).then(res => { if (res.success) { setEditDialogOpen(false); loadTree(); loadAllPools(); loadCandidates(selectedPoolId) } else alert(res.detail || 'Hata') })
  }

  const handleDeletePool = () => {
    if (!deleteConfirm) return
    fetch(`${API}/api/pools/${deleteConfirm}`, { method: 'DELETE', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { setDeleteConfirm(null); if (selectedPoolId === deleteConfirm) { setSelectedPoolId(null); setCandidates([]); setPoolInfo(null) }; loadTree(); loadAllPools() } else alert(res.detail || 'Hata') })
  }

  const handleAssignCandidate = () => {
    if (!selectedPoolId || !assignCandidateId) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates`, { method: 'POST', headers: H(), body: JSON.stringify({ candidate_id: Number(assignCandidateId), reason: 'Manuel atama' }) })
      .then(r => r.json()).then(res => { if (res.success) { setAssignDialogOpen(false); setAssignCandidateId(''); loadCandidates(selectedPoolId); loadTree() } else alert(res.detail || 'Hata') })
  }

  const handleRemoveCandidate = (cid: number) => {
    if (!selectedPoolId) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${cid}`, { method: 'DELETE', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { loadCandidates(selectedPoolId); loadTree() } })
  }

  const handleTransfer = () => {
    if (!selectedPoolId || !transferTargetId || selectedCandidates.size === 0) return
    fetch(`${API}/api/pools/transfer`, { method: 'POST', headers: H(), body: JSON.stringify({ candidate_ids: Array.from(selectedCandidates), source_pool_id: selectedPoolId, target_pool_id: Number(transferTargetId) }) })
      .then(r => r.json()).then(res => { if (res.success) { setTransferDialogOpen(false); setTransferTargetId(''); setSelectedCandidates(new Set()); loadCandidates(selectedPoolId); loadTree() } else alert(res.detail || 'Hata') })
  }

  const handleStatusUpdate = () => {
    if (!selectedPoolId || !statusValue || selectedCandidates.size === 0) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/status`, { method: 'PUT', headers: H(), body: JSON.stringify({ candidate_ids: Array.from(selectedCandidates), durum: statusValue }) })
      .then(r => r.json()).then(res => { if (res.success) { setStatusDialogOpen(false); setStatusValue(''); setSelectedCandidates(new Set()); loadCandidates(selectedPoolId) } else alert(res.detail || 'Hata') })
  }

  const handleSyncAll = () => {
    setSyncing(true)
    fetch(`${API}/api/pools/sync-all`, { method: 'POST', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { alert(`${res.data.positions_scanned} pozisyon tarandi, ${res.data.total_transferred} aday aktarildi`); loadTree(); loadAllPools(); if (selectedPoolId) loadCandidates(selectedPoolId) } else alert(res.detail || 'Hata') })
      .catch(console.error).finally(() => setSyncing(false))
  }

  const handlePullCandidates = () => {
    if (!selectedPoolId) return; setPulling(true)
    fetch(`${API}/api/pools/${selectedPoolId}/pull-candidates`, { method: 'POST', headers: H() })
      .then(r => r.json()).then(res => { if (res.success) { alert(`${res.data.total_scanned} aday tarandi, ${res.data.matched} eslesti, ${res.data.transferred} aktarildi`); loadCandidates(selectedPoolId); loadTree() } else alert(res.detail || 'Hata') })
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

  const handleDownloadPoolCVs = async () => {
    if (!selectedPoolId) return
    setDownloadingCVs(true)
    try {
      const token = localStorage.getItem("access_token")
      const response = await fetch(`${API}/api/candidates/export/download-cvs?pool_id=${selectedPoolId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || "İndirme hatası")
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `havuz_${selectedPoolId}_cvler.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      toast.success("CV dosyaları indirildi")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Bilinmeyen hata"
      toast.error(message)
    } finally {
      setDownloadingCVs(false)
    }
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
        } else { alert(res.detail || res.hata || 'Parse hatası') }
      }).catch(e => alert('Hata: ' + e)).finally(() => setParseLoading(false))
  }

  // Parse Sonucu veya Manuel Kaydet
  const handleSaveParsed = () => {
    if (!positionForm.pozisyon_adi) { alert("Pozisyon adı gerekli"); return }
    if (!poolForm.parent_id) { alert("Departman seçilmedi"); return }
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
          loadTree(); loadAllPools()
          alert('Pozisyon başarıyla eklendi!')
        } else { alert(res.detail || 'Kayıt hatası') }
      }).catch(e => alert('Hata: ' + e)).finally(() => setSavingPosition(false))
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
        } else { alert(res.detail || 'Hata') }
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
        } else { alert(res.detail || 'Hata') }
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
          alert(`${res.approved} başlık onaylandı, ${res.transferred} aday eşleştirildi`)
          loadTitles(selectedPoolId)
          loadCandidates(selectedPoolId)
        } else { alert(res.detail || 'Hata') }
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

  // AI Değerlendirme
  const handleEvaluate = (candidateId: number) => {
    if (!selectedPoolId) return
    setEvaluating(true)
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/evaluate`, { method: 'POST', headers: H() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          alert('AI değerlendirme tamamlandı!')
          loadDetail(candidateId)
        } else { alert(res.detail || 'Hata') }
      })
      .catch(e => alert('Hata: ' + e))
      .finally(() => setEvaluating(false))
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
      .catch(e => alert('Hata: ' + e))
  }

  const handleViewCV = (candidateId: number) => {
    if (!selectedPoolId) return
    fetch(`${API}/api/pools/${selectedPoolId}/candidates/${candidateId}/cv`, { headers: H() })
      .then(r => {
        if (!r.ok) throw new Error('CV bulunamadı')
        return r.blob()
      })
      .then(blob => {
        const url = URL.createObjectURL(blob)
        window.open(url, '_blank')
      })
      .catch(() => alert('CV dosyası bulunamadı'))
  }

  // Filtering & Sorting
  const filteredCandidates = candidates.filter(c => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      if (!(c.ad_soyad || '').toLowerCase().includes(q) && !(c.email || '').toLowerCase().includes(q) && !(c.mevcut_pozisyon || '').toLowerCase().includes(q)) return false
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

  const toggleAllCandidates = () => {
    if (selectedCandidates.size === filteredCandidates.length) setSelectedCandidates(new Set())
    else setSelectedCandidates(new Set(filteredCandidates.map(c => c.id)))
  }

  const totalCandidates = tree ? (tree.system_pools?.reduce((s, p) => s + p.candidate_count, 0) || 0) + (tree.departments?.reduce((s, d) => s + d.total_position_candidates, 0) || 0) : 0

  // V2 Detail Renderer
  const renderV2Detail = (v2: any) => {
    if (!v2 || !v2.version) return null
    return (
      <div className="grid grid-cols-2 gap-3 text-xs mt-2">
        <div className="space-y-1">
          <div className="font-medium">Pozisyon Uyumu: <span className="text-blue-600">{String(v2.position_score || 0)}/33</span></div>
          <div className="text-muted-foreground ml-2">Baslik: {String(v2.title_match_score || 0)} ({String(v2.title_match_level || '-')})</div>
          <div className="text-muted-foreground ml-2">Sektor: {String(v2.sector_score || 0)} ({String(v2.detected_sector || '-')})</div>
        </div>
        <div className="space-y-1">
          <div className="font-medium">Teknik Yetkinlik: <span className="text-purple-600">{String(v2.technical_score || 0)}/37</span></div>
          <div className="text-muted-foreground ml-2">Kritik: {String(v2.critical_score || 0)}</div>
          <div className="text-muted-foreground ml-2">Önemli: {String(v2.important_score || 0)}</div>
        </div>
        <div className="space-y-1">
          <div className="font-medium">Genel: <span className="text-green-600">{String(v2.general_score || 0)}/20</span></div>
          <div className="text-muted-foreground ml-2">Deneyim: {String(v2.experience_score || 0)}</div>
          <div className="text-muted-foreground ml-2">Eğitim: {String(v2.education_score || 0)}</div>
        </div>
        <div className="space-y-1">
          <div className="font-medium">Eleme: <span className="text-orange-600">{String(v2.elimination_score || 0)}/10</span></div>
          <div className="text-muted-foreground ml-2">Lokasyon: {String(v2.location_score || 0)}</div>
        </div>
        {v2.knockout && <div className="col-span-2 bg-red-50 border border-red-200 rounded p-2 text-red-700 font-medium">KNOCKOUT: {String(v2.knockout_reason || '')}</div>}
        {Array.isArray(v2.critical_missing) && (v2.critical_missing as string[]).length > 0 && (
          <div className="col-span-2"><span className="font-medium text-red-600">Eksik Kritik:</span> {(v2.critical_missing as string[]).join(', ')}</div>
        )}
        {Array.isArray(v2.critical_matched) && (v2.critical_matched as string[]).length > 0 && (
          <div className="col-span-2"><span className="font-medium text-green-600">Eşleşen Kritik:</span> {(v2.critical_matched as string[]).join(', ')}</div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2"><FolderTree className="h-6 w-6" /> Havuzlar</h2>
          <p className="text-muted-foreground text-sm">Departman ve pozisyon havuzlarını yönetin</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { loadTree(); loadAllPools(); if (selectedPoolId) loadCandidates(selectedPoolId) }} disabled={loading}><RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />Yenile</Button>
          <Button size="sm" variant="outline" onClick={handleSyncAll} disabled={syncing}>{syncing ? <RefreshCw className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}Eşleştir</Button>
          <Button size="sm" onClick={() => openCreate('department')}><Plus className="h-4 w-4 mr-1" />Departman</Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold">{totalCandidates}</div><div className="text-xs text-muted-foreground">Toplam Aday</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-blue-600">{tree?.system_pools?.find(s => s.name === 'Genel Havuz')?.candidate_count || 0}</div><div className="text-xs text-muted-foreground">Genel Havuz</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-orange-600">{tree?.system_pools?.find(s => s.name === 'Ar\u015Fiv')?.candidate_count || 0}</div><div className="text-xs text-muted-foreground">Arşiv</div></CardContent></Card>
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
                <div className="flex items-center gap-2">{sp.name === 'Ar\u015Fiv' ? <Archive className="h-4 w-4 text-orange-500" /> : <Inbox className="h-4 w-4 text-blue-500" />}<span className="text-sm font-medium">{sp.name}</span></div>
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
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2">{poolInfo?.name}<Badge variant="outline" className="text-xs">{poolInfo?.pool_type}</Badge></h3>
                  {poolInfo?.description && <p className="text-xs text-muted-foreground">{poolInfo.description}</p>}
                </div>
                <div className="flex gap-1.5">
                  {poolInfo && !poolInfo.is_system && (<><Button variant="outline" size="sm" onClick={openEdit}><Edit className="h-3.5 w-3.5 mr-1" />Düzenle</Button><Button variant="outline" size="sm" className="text-red-500" onClick={() => setDeleteConfirm(selectedPoolId)}><Trash2 className="h-3.5 w-3.5 mr-1" />Sil</Button></>)}
                  {poolInfo && poolInfo.pool_type === 'position' && !poolInfo.is_system && (
                    <Button variant="default" size="sm" onClick={handlePullCandidates} disabled={pulling}>{pulling ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Search className="h-3.5 w-3.5 mr-1" />}CV Cek</Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setAssignDialogOpen(true)}><UserPlus className="h-3.5 w-3.5 mr-1" />Aday Ata</Button>
                </div>
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
                    <SelectItem value="medium">50-79 Kismi</SelectItem>
                    <SelectItem value="low">0-49 Uyumsuz</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tüm Durum</SelectItem>
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
                {selectedCandidates.size > 0 && (
                  <>
                    <Button size="sm" variant="outline" onClick={() => setTransferDialogOpen(true)}><ArrowRightLeft className="h-3.5 w-3.5 mr-1" />Transfer ({selectedCandidates.size})</Button>
                    <Button size="sm" variant="outline" onClick={() => setStatusDialogOpen(true)}>Durum ({selectedCandidates.size})</Button>
                  </>
                )}
                <div className="flex-1" />
                <Button size="sm" variant="outline" onClick={handleDownloadPoolCVs} disabled={downloadingCVs || filteredCandidates.length === 0}>{downloadingCVs ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Download className="h-3.5 w-3.5 mr-1" />}CV İndir</Button>
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
                        <TableHead className="w-8"><Checkbox checked={selectedCandidates.size === filteredCandidates.length && filteredCandidates.length > 0} onCheckedChange={toggleAllCandidates} /></TableHead>
                        <TableHead className="w-[220px]">Ad Soyad</TableHead>
                        <TableHead className="w-[180px]">Pozisyon</TableHead>
                        <TableHead className="w-[80px]">Deneyim</TableHead>
                        <TableHead className="w-[120px]">Lokasyon</TableHead>
                        <TableHead className="w-[80px]">Skor</TableHead>
                        <TableHead className="w-[80px]">Durum</TableHead>
                        <TableHead className="w-20"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredCandidates.map(c => {
                        const si = c.match_score ? scoreIcon(c.match_score) : null
                        return (
                          <Fragment key={c.id}>
                            <TableRow className={`${selectedCandidates.has(c.id) ? 'bg-muted/50' : ''} cursor-pointer`} onClick={() => loadDetail(c.id)}>
                              <TableCell onClick={e => e.stopPropagation()}><Checkbox checked={selectedCandidates.has(c.id)} onCheckedChange={() => toggleCandidate(c.id)} /></TableCell>
                              <TableCell>
                                <div className="font-medium text-sm flex items-center gap-1">{expandedCandidate === c.id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}{c.ad_soyad}</div>
                                {c.email && <div className="text-xs text-muted-foreground ml-4">{c.email}</div>}
                              </TableCell>
                              <TableCell className="text-sm truncate">{c.mevcut_pozisyon || '-'}</TableCell>
                              <TableCell className="text-sm">{c.toplam_deneyim_yil ? `${c.toplam_deneyim_yil} yıl` : '-'}</TableCell>
                              <TableCell className="text-sm truncate">{c.lokasyon || '-'}</TableCell>
                              <TableCell>
                                {c.match_score ? <Badge variant="outline" className="text-xs">{si?.icon} {c.match_score}</Badge>
                                  : c.remaining_days !== undefined ? <Badge className={`text-xs ${dayColor(c.remaining_days)}`}>{c.remaining_days}g</Badge>
                                  : '-'}
                              </TableCell>
                              <TableCell>
                                {c.status && STATUS_MAP[c.status] ? <Badge className={`text-[10px] ${STATUS_MAP[c.status].color}`}>{STATUS_MAP[c.status].label}</Badge>
                                  : c.assignment_type ? <Badge variant="secondary" className="text-[10px]">{c.assignment_type}</Badge> : null}
                              </TableCell>
                              <TableCell onClick={e => e.stopPropagation()}>
                                <div className="flex items-center gap-1">
                                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleEvaluate(c.id)} disabled={evaluating} title="AI Değerlendir"><Brain className="h-3.5 w-3.5 text-purple-500" /></Button>
                                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 h-7 w-7 p-0" onClick={() => handleRemoveCandidate(c.id)} title="Çıkar"><Trash2 className="h-3.5 w-3.5" /></Button>
                                </div>
                              </TableCell>
                            </TableRow>
                            {/* Expanded Detail Row */}
                            {expandedCandidate === c.id && (
                              <TableRow key={`detail-${c.id}`}>
                                <TableCell colSpan={8} className="bg-muted/30 p-4">
                                  {detailLoading ? <div className="text-center py-4"><RefreshCw className="h-4 w-4 animate-spin inline mr-2" />Yükleniyor...</div> : candidateDetail ? (() => { const cd = candidateDetail.candidate as any; const v2d = (candidateDetail as any).v2_detail; const aie = (candidateDetail as any).ai_evaluation; return (
                                    <div className="space-y-3">
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
                                        <div><span className="text-xs font-medium">Teknik Beceriler:</span>
                                          <div className="flex flex-wrap gap-1 mt-1">
                                            {String(cd?.teknik_beceriler).split(',').map((s, i) => <Badge key={i} variant="secondary" className="text-[10px]">{s.trim()}</Badge>)}
                                          </div>
                                        </div>
                                      )}
                                      {/* Deneyim Detay */}
                                      {cd?.deneyim_detay && (
                                        <div className="text-xs"><span className="font-medium">Deneyim:</span> {String(cd?.deneyim_detay)}</div>
                                      )}
                                      {/* v2 Score Detail */}
                                      {v2d && (
                                        <div className="border rounded p-3 bg-white">
                                          <div className="text-xs font-medium mb-1 flex items-center gap-1"><FileText className="h-3 w-3" />v2 Skor Detayi (Toplam: {String((v2d)?.uyum_puani || (candidateDetail as any).position_score || '-')})</div>
                                          {renderV2Detail(v2d)}
                                        </div>
                                      )}
                                      {/* AI Evaluation */}
                                      <div className="border rounded p-3 bg-white">
                                        <div className="flex items-center justify-between mb-2">
                                          <div className="text-xs font-medium flex items-center gap-1"><Brain className="h-3 w-3" />AI Değerlendirme {aie ? `(v2: ${String((aie)?.v2_score || '-')})` : ''}</div>
                                          <div className="flex gap-1">
                                            <Button size="sm" variant="outline" onClick={() => handleViewCV(cd.id)} disabled={!cd?.cv_dosya_adi} className="h-6 text-[10px] px-2" title={cd?.cv_dosya_adi ? 'CV Görüntüle' : 'CV yok'}>
                                              <FileText className="h-3 w-3 mr-1" />CV
                                            </Button>
                                            <Button size="sm" variant="outline" onClick={() => handleEvaluate(cd.id)} disabled={evaluating} className="h-6 text-[10px] px-2">
                                              {evaluating ? <RefreshCw className="h-3 w-3 animate-spin mr-1" /> : <Brain className="h-3 w-3 mr-1" />}
                                              {aie ? 'Yeniden Değerlendir' : 'AI Değerlendir'}
                                            </Button>
                                            <Button size="sm" variant="outline" onClick={() => handleDownloadReport(cd.id)} disabled={!aie} className="h-6 text-[10px] px-2">
                                              <FileText className="h-3 w-3 mr-1" />Rapor
                                            </Button>
                                          </div>
                                        </div>
                                        {aie ? (
                                          <div className="text-xs whitespace-pre-line text-muted-foreground">{String((aie)?.text || '')}</div>
                                        ) : (
                                          <div className="text-xs text-muted-foreground italic">Henüz AI değerlendirme yapılmamış</div>
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
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="url"><Link className="h-3.5 w-3.5 mr-1" />URL ile Ekle</TabsTrigger>
                <TabsTrigger value="document"><FileText className="h-3.5 w-3.5 mr-1" />Dokumandan Ekle</TabsTrigger>
                <TabsTrigger value="manual"><Edit className="h-3.5 w-3.5 mr-1" />Manuel Giris</TabsTrigger>
              </TabsList>

              {/* TAB 1: URL ile Ekle */}
              <TabsContent value="url" className="space-y-3 mt-3">
                <div>
                  <Label className="text-sm">Kariyer.net Ilan URL</Label>
                  <div className="flex gap-2 mt-1">
                    <Input value={urlInput} onChange={e => setUrlInput(e.target.value)} placeholder="https://www.kariyer.net/is-ilani/..." className="flex-1" />
                    <Button onClick={handleParseUrl} disabled={parseLoading || !urlInput}>
                      {parseLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      <span className="ml-1">Analiz</span>
                    </Button>
                  </div>
                </div>

                {parsedData && (
                  <div className="space-y-3 border-t pt-3">
                    <div className="text-sm font-medium text-green-600">Analiz başarılı! Aşağıdaki bilgileri düzenleyebilirsiniz:</div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Pozisyon Adi *</Label><Input value={positionForm.pozisyon_adi} onChange={e => setPositionForm({...positionForm, pozisyon_adi: e.target.value})} /></div>
                      <div><Label className="text-sm">Lokasyon</Label><Input value={positionForm.lokasyon} onChange={e => setPositionForm({...positionForm, lokasyon: e.target.value})} /></div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Deneyim (yil)</Label><Input type="number" value={positionForm.deneyim_yil} onChange={e => setPositionForm({...positionForm, deneyim_yil: e.target.value})} /></div>
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
                    <div><Label className="text-sm">Anahtar Kelimeler (virgul ile)</Label><Input value={positionForm.keywords} onChange={e => setPositionForm({...positionForm, keywords: e.target.value})} /></div>
                    <div><Label className="text-sm">Aranan Nitelikler</Label><Textarea value={positionForm.aranan_nitelikler} onChange={e => setPositionForm({...positionForm, aranan_nitelikler: e.target.value})} rows={3} /></div>
                    <div><Label className="text-sm">İş Tanımı</Label><Textarea value={positionForm.is_tanimi} onChange={e => setPositionForm({...positionForm, is_tanimi: e.target.value})} rows={3} /></div>
                    <Button onClick={handleSaveParsed} disabled={savingPosition || !positionForm.pozisyon_adi} className="w-full">
                      {savingPosition ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}Kaydet
                    </Button>
                  </div>
                )}
              </TabsContent>

              {/* TAB 2: Dokumandan Ekle */}
              <TabsContent value="document" className="space-y-3 mt-3">
                <div>
                  <Label className="text-sm">Ilan Dokumani (PDF, Word, JPEG)</Label>
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
                              alert(res.detail || res.message || 'Parse hatası')
                            }
                          })
                          .catch(err => alert('Hata: ' + err.message))
                          .finally(() => setParseLoading(false))
                      }
                    }}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, DOC, JPG, JPEG, PNG desteklenir</p>
                </div>

                {parseLoading && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin" /> Dokuman analiz ediliyor...
                  </div>
                )}

                {parsedData && (
                  <div className="space-y-3 border-t pt-3">
                    <div className="text-sm font-medium text-green-600">Analiz başarılı! Aşağıdaki bilgileri düzenleyebilirsiniz:</div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Pozisyon Adi *</Label><Input value={positionForm.pozisyon_adi} onChange={e => setPositionForm({...positionForm, pozisyon_adi: e.target.value})} /></div>
                      <div><Label className="text-sm">Lokasyon</Label><Input value={positionForm.lokasyon} onChange={e => setPositionForm({...positionForm, lokasyon: e.target.value})} /></div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-sm">Deneyim (yil)</Label><Input type="number" value={positionForm.deneyim_yil} onChange={e => setPositionForm({...positionForm, deneyim_yil: e.target.value})} /></div>
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
                    <div><Label className="text-sm">Anahtar Kelimeler (virgul ile)</Label><Input value={positionForm.keywords} onChange={e => setPositionForm({...positionForm, keywords: e.target.value})} /></div>
                    <div><Label className="text-sm">Aranan Nitelikler</Label><Textarea value={positionForm.aranan_nitelikler} onChange={e => setPositionForm({...positionForm, aranan_nitelikler: e.target.value})} rows={3} /></div>
                    <div><Label className="text-sm">İş Tanımı</Label><Textarea value={positionForm.is_tanimi} onChange={e => setPositionForm({...positionForm, is_tanimi: e.target.value})} rows={3} /></div>
                    <Button onClick={handleSaveParsed} disabled={savingPosition || !positionForm.pozisyon_adi} className="w-full">
                      {savingPosition ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}Kaydet
                    </Button>
                  </div>
                )}
              </TabsContent>

              {/* TAB 3: Manuel Giris */}
              <TabsContent value="manual" className="space-y-3 mt-3">
                <div className="grid grid-cols-2 gap-2">
                  <div><Label className="text-sm">Pozisyon Adi *</Label><Input value={positionForm.pozisyon_adi} onChange={e => setPositionForm({...positionForm, pozisyon_adi: e.target.value})} placeholder="Örnek: Frontend Developer" /></div>
                  <div><Label className="text-sm">Lokasyon</Label><Input value={positionForm.lokasyon} onChange={e => setPositionForm({...positionForm, lokasyon: e.target.value})} placeholder="Istanbul" /></div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div><Label className="text-sm">Deneyim (yil)</Label><Input type="number" value={positionForm.deneyim_yil} onChange={e => setPositionForm({...positionForm, deneyim_yil: e.target.value})} /></div>
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
                <div><Label className="text-sm">Anahtar Kelimeler (virgul ile)</Label><Input value={positionForm.keywords} onChange={e => setPositionForm({...positionForm, keywords: e.target.value})} placeholder="react, typescript, node.js" /></div>
                <div><Label className="text-sm">Aranan Nitelikler</Label><Textarea value={positionForm.aranan_nitelikler} onChange={e => setPositionForm({...positionForm, aranan_nitelikler: e.target.value})} rows={3} placeholder="Gerekli beceriler ve nitelikler..." /></div>
                <div><Label className="text-sm">İş Tanımı</Label><Textarea value={positionForm.is_tanimi} onChange={e => setPositionForm({...positionForm, is_tanimi: e.target.value})} rows={3} placeholder="Pozisyon hakkinda detaylar..." /></div>
                <Button onClick={handleSaveParsed} disabled={savingPosition || !positionForm.pozisyon_adi} className="w-full">
                  {savingPosition ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}Kaydet
                </Button>
              </TabsContent>
            </Tabs>
          ) : (
            /* Departman ekleme (eski basit form) */
            <div className="space-y-3">
              <div><Label className="text-sm">Ad *</Label><Input value={poolForm.name} onChange={e => setPoolForm({...poolForm, name: e.target.value})} placeholder="Örnek: Yazilim Gelistirme" /></div>
              <div><Label className="text-sm">Açıklama</Label><Textarea value={poolForm.description} onChange={e => setPoolForm({...poolForm, description: e.target.value})} rows={2} /></div>
              <DialogFooter><Button variant="outline" onClick={() => setCreateDialogOpen(false)}>İptal</Button><Button onClick={handleCreatePool} disabled={!poolForm.name}>Oluştur</Button></DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Havuz Düzenle</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-sm">Ad *</Label><Input value={poolForm.name} onChange={e => setPoolForm({...poolForm, name: e.target.value})} /></div>
            <div><Label className="text-sm">Açıklama</Label><Textarea value={poolForm.description} onChange={e => setPoolForm({...poolForm, description: e.target.value})} rows={2} /></div>

            {/* Keyword Yonetimi */}
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
          <DialogFooter><Button variant="outline" onClick={() => setEditDialogOpen(false)}>İptal</Button><Button onClick={handleUpdatePool} disabled={!poolForm.name}>Kaydet</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteConfirm !== null} onOpenChange={o => { if (!o) setDeleteConfirm(null) }}>
        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Havuz Sil</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Bu havuzu silmek istediginizden emin misiniz? Adaylar Genel Havuz'a tasinacaktir.</p>
          <DialogFooter><Button variant="outline" onClick={() => setDeleteConfirm(null)}>İptal</Button><Button variant="destructive" onClick={handleDeletePool}>Sil</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Aday Ata</DialogTitle></DialogHeader>
          <div><Label className="text-sm">Aday ID</Label><Input type="number" value={assignCandidateId} onChange={e => setAssignCandidateId(e.target.value)} placeholder="Örnek: 421" /></div>
          <DialogFooter><Button variant="outline" onClick={() => setAssignDialogOpen(false)}>İptal</Button><Button onClick={handleAssignCandidate} disabled={!assignCandidateId}>Ata</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={transferDialogOpen} onOpenChange={setTransferDialogOpen}>
        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Transfer ({selectedCandidates.size} aday)</DialogTitle></DialogHeader>
          <div><Label className="text-sm">Hedef Havuz</Label>
            <Select value={transferTargetId} onValueChange={setTransferTargetId}><SelectTrigger><SelectValue placeholder="Havuz secin..." /></SelectTrigger>
              <SelectContent>{allPools.filter(p => p.id !== selectedPoolId).map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setTransferDialogOpen(false)}>İptal</Button><Button onClick={handleTransfer} disabled={!transferTargetId}>Transfer</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
        <DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Durum Guncelle ({selectedCandidates.size} aday)</DialogTitle></DialogHeader>
          <div><Label className="text-sm">Yeni Durum</Label>
            <Select value={statusValue} onValueChange={setStatusValue}><SelectTrigger><SelectValue placeholder="Durum secin..." /></SelectTrigger>
              <SelectContent>{Object.entries(STATUS_MAP).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setStatusDialogOpen(false)}>İptal</Button><Button onClick={handleStatusUpdate} disabled={!statusValue}>Guncelle</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
