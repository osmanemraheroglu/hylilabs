import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Loader2, Languages, Plus, Sparkles, CheckCircle, XCircle, Search, Trash2, History } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

// API config
const API = 'http://***REMOVED***:8000'
const H = () => ({
  'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
  'Content-Type': 'application/json'
})

// Types
interface Synonym {
  id: number
  keyword: string
  synonym: string
  synonym_type: 'turkish' | 'english' | 'abbreviation' | 'variation' | 'exact_synonym' | 'broader_term' | 'narrower_term'
  source: 'ai' | 'manual' | 'migrated'
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  company_id: number | null
  match_weight?: number  // FAZ 8.3: Eşleşme ağırlığı
  confidence_score?: number  // FAZ 10.1: Confidence skoru
}

// FAZ 9.2: Çakışma bilgisi
interface SynonymConflict {
  synonym: string
  primary_keyword: string
  secondary_keywords: string[]
  conflict_count: number
  ambiguity_score: number
}

interface RejectReason {
  code: string
  label: string
  description: string
}

export default function Synonyms() {
  // FAZ 3: Auth - scope seçimi için
  const { auth } = useAuthStore()
  const isSuperAdmin = auth.user?.role?.includes("super_admin") || false

  // Tab state
  const [activeTab, setActiveTab] = useState('pending')

  // Pending tab state
  const [pendingList, setPendingList] = useState<Synonym[]>([])
  const [pendingLoading, setPendingLoading] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  // FAZ 3: Onay kapsamı (global/company)
  const [approveScope, setApproveScope] = useState<"company" | "global">("company")

  // All synonyms tab state
  const [searchKeyword, setSearchKeyword] = useState('')
  const [synonymList, setSynonymList] = useState<Synonym[]>([])
  const [searchLoading, setSearchLoading] = useState(false)

  // AI generate tab state
  const [generateKeyword, setGenerateKeyword] = useState('')
  const [generateLoading, setGenerateLoading] = useState(false)
  const [generatedSynonyms, setGeneratedSynonyms] = useState<string[]>([])

  // Manual add tab state
  const [manualKeyword, setManualKeyword] = useState('')
  const [manualSynonym, setManualSynonym] = useState('')
  const [manualType, setManualType] = useState<string>('turkish')
  const [manualLoading, setManualLoading] = useState(false)

  // Reject dialog state
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [rejectReasons, setRejectReasons] = useState<RejectReason[]>([])
  const [selectedReason, setSelectedReason] = useState('')
  const [rejectNote, setRejectNote] = useState('')
  const [rejectLoading, setRejectLoading] = useState(false)

  // Keyword importance tab state (FAZ 8.2.5)
  const [importanceList, setImportanceList] = useState<{id: number, keyword: string, importance_level: string, created_at: string}[]>([])
  const [importanceKeyword, setImportanceKeyword] = useState('')
  const [importanceLevel, setImportanceLevel] = useState('normal')
  const [importanceLoading, setImportanceLoading] = useState(false)

  // FAZ 9.2: Çakışma durumu
  const [conflicts, setConflicts] = useState<SynonymConflict[]>([])

  // FAZ 9.3: Blacklist adayları
  const [blacklistCandidates, setBlacklistCandidates] = useState<{id: number, synonym: string, reject_count: number, reasons_history: string, status: string, last_rejected_at: string}[]>([])
  const [blacklistLoading, setBlacklistLoading] = useState(false)

  // FAZ 9.4: History modal
  const [historyModalOpen, setHistoryModalOpen] = useState(false)
  const [historyData, setHistoryData] = useState<{id: number, action: string, old_values: string, new_values: string, changed_by_email: string, changed_at: string}[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [selectedSynonymForHistory, setSelectedSynonymForHistory] = useState<{id: number, keyword: string, synonym: string} | null>(null)

  // Load pending count and reject reasons on mount
  useEffect(() => {
    loadPendingCount()
    loadRejectReasons()
    loadConflicts()
  }, [])

  // Load pending list when tab changes to pending
  useEffect(() => {
    if (activeTab === 'pending') {
      loadPendingList()
    }
    if (activeTab === 'importance') {
      loadImportanceList()
    }
    if (activeTab === 'blacklist') {
      loadBlacklistCandidates()
    }
  }, [activeTab])

  // ═══════════════════════════════════════════════════════════════════
  // API FONKSİYONLARI
  // ═══════════════════════════════════════════════════════════════════

  const loadRejectReasons = async () => {
    try {
      const res = await fetch(`${API}/api/synonyms/reject_reasons`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setRejectReasons(data.data.reasons || [])
      }
    } catch (err) {
      console.error('loadRejectReasons error:', err)
    }
  }

  const loadPendingCount = async () => {
    try {
      const res = await fetch(`${API}/api/synonyms/pending/count`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setPendingCount(data.data.count)
      }
    } catch (err) {
      console.error('loadPendingCount error:', err)
    }
  }

  // FAZ 9.2: Çakışmaları yükle
  const loadConflicts = async () => {
    try {
      const res = await fetch(`${API}/api/synonyms/conflicts`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setConflicts(data.data || [])
      }
    } catch (err) {
      console.error('loadConflicts error:', err)
    }
  }

  // FAZ 9.2: Synonym çakışma kontrolü
  const hasConflict = (synonym: string): SynonymConflict | undefined => {
    return conflicts.find(c => c.synonym === synonym.toLowerCase())
  }

  // FAZ 9.3: Blacklist adaylarını yükle
  const loadBlacklistCandidates = async () => {
    setBlacklistLoading(true)
    try {
      const res = await fetch(`${API}/api/synonyms/blacklist_candidates`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setBlacklistCandidates(data.data?.candidates || [])
      }
    } catch (err) {
      console.error('loadBlacklistCandidates error:', err)
    } finally {
      setBlacklistLoading(false)
    }
  }

  // FAZ 9.3: Blacklist adayını onayla (GLOBAL_BLACKLIST'e ekle)
  const handleApproveBlacklist = async (id: number, synonym: string) => {
    try {
      const res = await fetch(`${API}/api/synonyms/blacklist_candidates/${id}/approve`, {
        method: 'POST',
        headers: H()
      })
      const data = await res.json()
      if (data.success) {
        toast.success(`"${synonym}" blacklist'e eklendi`)
        loadBlacklistCandidates()
      } else {
        toast.error(data.detail || 'Onaylama başarısız')
      }
    } catch (err) {
      console.error('handleApproveBlacklist error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  // FAZ 9.3: Blacklist adayını reddet (listeden kaldır)
  const handleDismissBlacklist = async (id: number, synonym: string) => {
    try {
      const res = await fetch(`${API}/api/synonyms/blacklist_candidates/${id}/dismiss`, {
        method: 'POST',
        headers: H()
      })
      const data = await res.json()
      if (data.success) {
        toast.success(`"${synonym}" aday listesinden kaldırıldı`)
        loadBlacklistCandidates()
      } else {
        toast.error(data.detail || 'İşlem başarısız')
      }
    } catch (err) {
      console.error('handleDismissBlacklist error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  // FAZ 9.4: Synonym geçmişini yükle
  const loadHistory = async (synonymId: number, keyword: string, synonym: string) => {
    setSelectedSynonymForHistory({ id: synonymId, keyword, synonym })
    setHistoryModalOpen(true)
    setHistoryLoading(true)
    try {
      const res = await fetch(`${API}/api/synonyms/${synonymId}/history`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setHistoryData(data.data || [])
      } else {
        toast.error(data.detail || 'Geçmiş alınamadı')
      }
    } catch (err) {
      console.error('loadHistory error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setHistoryLoading(false)
    }
  }

  // FAZ 9.4: Action label helper
  const getActionLabel = (action: string) => {
    switch (action) {
      case 'created': return { label: 'Oluşturuldu', color: 'bg-blue-100 text-blue-800' }
      case 'approved': return { label: 'Onaylandı', color: 'bg-green-100 text-green-800' }
      case 'rejected': return { label: 'Reddedildi', color: 'bg-red-100 text-red-800' }
      case 'updated': return { label: 'Güncellendi', color: 'bg-yellow-100 text-yellow-800' }
      case 'deleted': return { label: 'Silindi', color: 'bg-gray-100 text-gray-800' }
      default: return { label: action, color: 'bg-gray-100 text-gray-800' }
    }
  }

  const loadPendingList = async () => {
    setPendingLoading(true)
    try {
      const res = await fetch(`${API}/api/synonyms/pending`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setPendingList(data.data.synonyms || [])
      } else {
        toast.error(data.detail || 'Liste alınamadı')
      }
    } catch (err) {
      console.error('loadPendingList error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setPendingLoading(false)
    }
  }

  const handleApprove = async () => {
    if (selectedIds.length === 0) return

    try {
      const res = await fetch(`${API}/api/synonyms/approve`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ synonym_ids: selectedIds, scope: approveScope })
      })
      const data = await res.json()

      if (data.success) {
        toast.success(`${data.data.updated || selectedIds.length} eş anlamlı onaylandı`)
        setSelectedIds([])
        loadPendingList()
        loadPendingCount()
      } else {
        toast.error(data.detail || 'Onaylama başarısız')
      }
    } catch (err) {
      console.error('handleApprove error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  const openRejectDialog = () => {
    if (selectedIds.length === 0) return
    setSelectedReason('')
    setRejectNote('')
    setRejectDialogOpen(true)
  }

  const closeRejectDialog = () => {
    setRejectDialogOpen(false)
    setSelectedReason('')
    setRejectNote('')
  }

  const confirmReject = async () => {
    if (selectedIds.length === 0 || !selectedReason) return

    setRejectLoading(true)
    try {
      const res = await fetch(`${API}/api/synonyms/reject`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({
          synonym_ids: selectedIds,
          reject_reason: selectedReason,
          reject_note: rejectNote.trim() || null
        })
      })
      const data = await res.json()

      if (data.success) {
        toast.success(`${data.data.updated || selectedIds.length} eş anlamlı reddedildi`)
        setSelectedIds([])
        closeRejectDialog()
        loadPendingList()
        loadPendingCount()
      } else {
        toast.error(data.detail || 'Reddetme başarısız')
      }
    } catch (err) {
      console.error('confirmReject error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setRejectLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchKeyword.trim()) return

    setSearchLoading(true)
    try {
      const res = await fetch(
        `${API}/api/synonyms?keyword=${encodeURIComponent(searchKeyword.trim())}`,
        { headers: H() }
      )
      const data = await res.json()

      if (data.success) {
        setSynonymList(data.data.synonyms || [])
        if ((data.data.synonyms || []).length === 0) {
          toast.success('Bu keyword için eş anlamlı bulunamadı')
        }
      } else {
        toast.error(data.detail || 'Arama başarısız')
      }
    } catch (err) {
      console.error('handleSearch error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setSearchLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Bu eş anlamlıyı silmek istediğinizden emin misiniz?')) return

    try {
      const res = await fetch(`${API}/api/synonyms/${id}`, {
        method: 'DELETE',
        headers: H()
      })
      const data = await res.json()

      if (data.success) {
        toast.success('Eş anlamlı silindi')
        setSynonymList(prev => prev.filter(s => s.id !== id))
        loadPendingCount()
      } else {
        toast.error(data.detail || 'Silme başarısız')
      }
    } catch (err) {
      console.error('handleDelete error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  const handleGenerate = async () => {
    if (!generateKeyword.trim()) return

    setGenerateLoading(true)
    setGeneratedSynonyms([])

    try {
      const res = await fetch(`${API}/api/synonyms/generate`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ keyword: generateKeyword.trim() })
      })
      const data = await res.json()

      if (data.success) {
        // API'den dönen synonyms array'ini göster
        const synonyms = data.data.synonyms || []
        const synonymTexts = synonyms.map((s: { synonym: string }) => s.synonym)
        setGeneratedSynonyms(synonymTexts)

        const inserted = data.data.inserted || 0
        const skipped = data.data.skipped || 0

        if (inserted > 0) {
          toast.success(`${inserted} eş anlamlı üretildi ve onay listesine eklendi`)
          // Pending count'u güncelle
          loadPendingCount()
        } else if (skipped > 0) {
          toast.success(`Tüm öneriler zaten mevcut (${skipped} atlandı)`)
        } else {
          toast.error('AI öneri üretemedi')
        }
      } else {
        // Rate limit hatası (429) veya diğer hatalar
        toast.error(data.detail || 'Üretim başarısız')
      }
    } catch (err) {
      console.error('handleGenerate error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setGenerateLoading(false)
    }
  }

  const handleManualAdd = async () => {
    if (!manualKeyword.trim() || !manualSynonym.trim()) return

    setManualLoading(true)

    try {
      const res = await fetch(`${API}/api/synonyms`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({
          keyword: manualKeyword.trim().toLowerCase(),
          synonym: manualSynonym.trim().toLowerCase(),
          synonym_type: manualType,
          auto_approve: false
        })
      })
      const data = await res.json()

      if (data.success) {
        toast.success('Eş anlamlı başarıyla eklendi')
        // Formu temizle
        setManualKeyword('')
        setManualSynonym('')
        setManualType('turkish')
        // Pending count'u güncelle
        loadPendingCount()
      } else {
        // Duplicate hatası kontrolü
        if (data.detail && data.detail.includes('zaten mevcut')) {
          toast.error('Bu eş anlamlı zaten mevcut')
        } else if (data.detail && data.detail.includes('aynı olamaz')) {
          toast.error('Keyword ve eş anlamlı aynı olamaz')
        } else {
          toast.error(data.detail || 'Ekleme başarısız')
        }
      }
    } catch (err) {
      console.error('handleManualAdd error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setManualLoading(false)
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // KEYWORD IMPORTANCE FONKSİYONLARI (FAZ 8.2.5)
  // ═══════════════════════════════════════════════════════════════════

  const loadImportanceList = async () => {
    try {
      setImportanceLoading(true)
      const res = await fetch(`${API}/api/synonyms/keyword-importance`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setImportanceList(data.data || [])
      }
    } catch (err) {
      console.error('loadImportanceList error:', err)
      toast.error('Öncelik listesi yüklenemedi')
    } finally {
      setImportanceLoading(false)
    }
  }

  const handleAddImportance = async () => {
    if (!importanceKeyword.trim()) {
      toast.error('Keyword giriniz')
      return
    }

    try {
      setImportanceLoading(true)
      const res = await fetch(`${API}/api/synonyms/keyword-importance`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({
          keyword: importanceKeyword.trim().toLowerCase(),
          importance_level: importanceLevel
        })
      })
      const data = await res.json()

      if (res.ok && data.success) {
        toast.success(`"${importanceKeyword}" ${data.data.action === 'created' ? 'eklendi' : 'güncellendi'}`)
        setImportanceKeyword('')
        setImportanceLevel('normal')
        loadImportanceList()
      } else {
        toast.error(data.detail || 'Ekleme başarısız')
      }
    } catch (err) {
      console.error('handleAddImportance error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setImportanceLoading(false)
    }
  }

  const handleDeleteImportance = async (id: number, keyword: string) => {
    if (!confirm(`"${keyword}" önceliğini silmek istediğinize emin misiniz?`)) {
      return
    }

    try {
      const res = await fetch(`${API}/api/synonyms/keyword-importance/${id}`, {
        method: 'DELETE',
        headers: H()
      })
      const data = await res.json()

      if (res.ok && data.success) {
        toast.success(data.message)
        loadImportanceList()
      } else {
        toast.error(data.detail || 'Silme başarısız')
      }
    } catch (err) {
      console.error('handleDeleteImportance error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  const getImportanceBadge = (level: string) => {
    switch (level) {
      case 'high':
        return <Badge className="bg-green-500">Yüksek (5)</Badge>
      case 'low':
        return <Badge variant="destructive">Düşük (2)</Badge>
      default:
        return <Badge variant="secondary">Normal (3)</Badge>
    }
  }

  // FAZ 8.3: Match weight badge
  const getWeightBadge = (weight?: number) => {
    if (!weight) return null
    const percent = Math.round(weight * 100)
    if (weight >= 0.95) {
      return <Badge className="bg-green-600 text-white text-xs">{percent}%</Badge>
    } else if (weight >= 0.90) {
      return <Badge className="bg-blue-500 text-white text-xs">{percent}%</Badge>
    } else if (weight >= 0.85) {
      return <Badge className="bg-yellow-500 text-white text-xs">{percent}%</Badge>
    } else {
      return <Badge variant="secondary" className="text-xs">{percent}%</Badge>
    }
  }

  // FAZ 10.1: Confidence score badge
  const getConfidenceBadge = (confidence?: number) => {
    if (!confidence && confidence !== 0) return null
    const percent = Math.round(confidence * 100)
    if (confidence >= 0.8) {
      return <Badge className="bg-emerald-600 text-white text-xs" title="Yüksek güven">{percent}%</Badge>
    } else if (confidence >= 0.5) {
      return <Badge className="bg-amber-500 text-white text-xs" title="Orta güven">{percent}%</Badge>
    } else {
      return <Badge className="bg-red-500 text-white text-xs" title="Düşük güven">{percent}%</Badge>
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // HELPER FONKSİYONLAR
  // ═══════════════════════════════════════════════════════════════════

  const toggleSelect = (id: number) => {
    setSelectedIds(prev =>
      prev.includes(id)
        ? prev.filter(i => i !== id)
        : [...prev, id]
    )
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === pendingList.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(pendingList.map(s => s.id))
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return <Badge variant="default" className="bg-green-500">Onaylı</Badge>
      case 'pending':
        return <Badge variant="secondary">Bekliyor</Badge>
      case 'rejected':
        return <Badge variant="destructive">Reddedildi</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  // FAZ 9.1: 6 tip için badge
  const getTypeBadge = (type: string) => {
    const typeConfig: Record<string, { label: string; color: string }> = {
      exact_synonym: { label: 'Birebir', color: 'bg-green-100 text-green-800' },
      abbreviation: { label: 'Kısaltma', color: 'bg-blue-100 text-blue-800' },
      english: { label: 'İngilizce', color: 'bg-purple-100 text-purple-800' },
      turkish: { label: 'Türkçe', color: 'bg-orange-100 text-orange-800' },
      broader_term: { label: 'Üst Kavram', color: 'bg-yellow-100 text-yellow-800' },
      narrower_term: { label: 'Alt Kavram', color: 'bg-gray-100 text-gray-800' },
      variation: { label: 'Varyasyon', color: 'bg-gray-100 text-gray-800' } // Geriye uyumluluk
    }
    const config = typeConfig[type] || { label: type, color: '' }
    return <Badge variant="outline" className={config.color}>{config.label}</Badge>
  }

  // FAZ 9.2: Çakışma badge'i (sarı uyarı)
  const getConflictBadge = (synonym: string) => {
    const conflict = hasConflict(synonym)
    if (!conflict) return null

    const keywords = [conflict.primary_keyword, ...conflict.secondary_keywords].join(', ')
    const title = `Bu synonym ${conflict.conflict_count} farklı keyword'de kullanılıyor: ${keywords}`

    return (
      <Badge
        variant="outline"
        className="bg-yellow-100 text-yellow-800 cursor-help ml-1"
        title={title}
      >
        ⚠ {conflict.conflict_count} çakışma
      </Badge>
    )
  }

  // ═══════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Languages className="h-6 w-6" />
            Eş Anlamlılar Yönetimi
          </h1>
          <p className="text-muted-foreground">
            Keyword eş anlamlılarını yönetin, AI ile yeni öneriler oluşturun
          </p>
        </div>
        {pendingCount > 0 && (
          <Badge variant="destructive" className="text-lg px-3 py-1">
            {pendingCount} Onay Bekliyor
          </Badge>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="pending" className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            Onay Bekleyenler
            {pendingCount > 0 && (
              <Badge variant="secondary" className="ml-1">{pendingCount}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="all" className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            Tüm Eş Anlamlılar
          </TabsTrigger>
          <TabsTrigger value="generate" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            AI Üretimi
          </TabsTrigger>
          <TabsTrigger value="manual" className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Manuel Ekleme
          </TabsTrigger>
          <TabsTrigger value="importance" className="flex items-center gap-2">
            🎯
            Öncelikler
            {importanceList.length > 0 && (
              <Badge variant="outline" className="ml-1">{importanceList.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="blacklist" className="flex items-center gap-2">
            🚫
            Blacklist Adayları
            {blacklistCandidates.length > 0 && (
              <Badge variant="destructive" className="ml-1">{blacklistCandidates.length}</Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: Onay Bekleyenler */}
        <TabsContent value="pending">
          <Card>
            <CardHeader>
              <CardTitle>Onay Bekleyen Eş Anlamlılar</CardTitle>
              <CardDescription>
                AI tarafından üretilen veya manuel eklenen eş anlamlıları onaylayın veya reddedin
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* FAZ 3: Scope seçici - sadece super_admin için */}
              {isSuperAdmin && (
                <div className="flex items-center gap-4 mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <Label className="font-medium text-amber-800">Onay Kapsamı:</Label>
                  <RadioGroup
                    value={approveScope}
                    onValueChange={(v) => setApproveScope(v as "company" | "global")}
                    className="flex gap-4"
                  >
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="company" id="scope-company" />
                      <Label htmlFor="scope-company" className="cursor-pointer">
                        Firma Bazlı
                        <span className="text-xs text-muted-foreground ml-1">(Sadece bu firma)</span>
                      </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="global" id="scope-global" />
                      <Label htmlFor="scope-global" className="cursor-pointer">
                        Global
                        <span className="text-xs text-muted-foreground ml-1">(Tüm firmalar)</span>
                      </Label>
                    </div>
                  </RadioGroup>
                </div>
              )}

              {/* Toplu işlem butonları */}
              <div className="flex gap-2 mb-4">
                <Button
                  onClick={handleApprove}
                  disabled={selectedIds.length === 0}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Seçilenleri Onayla ({selectedIds.length})
                </Button>
                <Button
                  onClick={openRejectDialog}
                  disabled={selectedIds.length === 0}
                  variant="destructive"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Seçilenleri Reddet ({selectedIds.length})
                </Button>
              </div>

              {/* Tablo */}
              {pendingLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : pendingList.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Onay bekleyen eş anlamlı bulunmuyor
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <Checkbox
                          checked={selectedIds.length === pendingList.length && pendingList.length > 0}
                          onCheckedChange={toggleSelectAll}
                        />
                      </TableHead>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Eş Anlamlı</TableHead>
                      <TableHead>Tip</TableHead>
                      <TableHead>Ağırlık</TableHead>
                      <TableHead>Kaynak</TableHead>
                      <TableHead>Tarih</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingList.map(item => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.includes(item.id)}
                            onCheckedChange={() => toggleSelect(item.id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{item.keyword}</TableCell>
                        <TableCell>
                          <span className="flex items-center gap-1">
                            {item.synonym}
                            {getConflictBadge(item.synonym)}
                          </span>
                        </TableCell>
                        <TableCell>{getTypeBadge(item.synonym_type)}</TableCell>
                        <TableCell>{getWeightBadge(item.match_weight)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {item.source === 'ai' ? 'AI' : item.source === 'manual' ? 'Manuel' : 'Migrated'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(item.created_at).toLocaleDateString('tr-TR')}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 2: Tüm Eş Anlamlılar */}
        <TabsContent value="all">
          <Card>
            <CardHeader>
              <CardTitle>Tüm Eş Anlamlılar</CardTitle>
              <CardDescription>
                Keyword'e göre arama yapın ve mevcut eş anlamlıları görüntüleyin
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Arama */}
              <div className="flex gap-2 mb-4">
                <Input
                  placeholder="Keyword ara..."
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="max-w-sm"
                />
                <Button onClick={handleSearch} disabled={searchLoading || !searchKeyword.trim()}>
                  {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  <span className="ml-2">Ara</span>
                </Button>
              </div>

              {/* Sonuçlar */}
              {searchLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : synonymList.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  {searchKeyword ? 'Sonuç bulunamadı' : 'Arama yapmak için keyword girin'}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Eş Anlamlı</TableHead>
                      <TableHead>Tip</TableHead>
                      <TableHead>Ağırlık</TableHead>
                      <TableHead>Güven</TableHead>
                      <TableHead>Durum</TableHead>
                      <TableHead>Kaynak</TableHead>
                      <TableHead className="w-24">İşlem</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {synonymList.map(item => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.keyword}</TableCell>
                        <TableCell>
                          <span className="flex items-center gap-1">
                            {item.synonym}
                            {getConflictBadge(item.synonym)}
                          </span>
                        </TableCell>
                        <TableCell>{getTypeBadge(item.synonym_type)}</TableCell>
                        <TableCell>{getWeightBadge(item.match_weight)}</TableCell>
                        <TableCell>{getConfidenceBadge(item.confidence_score)}</TableCell>
                        <TableCell>{getStatusBadge(item.status)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {item.source === 'ai' ? 'AI' : item.source === 'manual' ? 'Manuel' : 'Migrated'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => loadHistory(item.id, item.keyword, item.synonym)}
                              title="Geçmişi Görüntüle"
                            >
                              <History className="h-4 w-4 text-blue-500" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(item.id)}
                              title="Sil"
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: AI Üretimi */}
        <TabsContent value="generate">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                AI ile Eş Anlamlı Üret
              </CardTitle>
              <CardDescription>
                Bir keyword girin, AI sizin için eş anlamlılar önersin
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Keyword girin (örn: yazılım geliştirme)"
                  value={generateKeyword}
                  onChange={(e) => setGenerateKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                  className="max-w-md"
                />
                <Button onClick={handleGenerate} disabled={generateLoading || !generateKeyword.trim()}>
                  {generateLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  AI ile Üret
                </Button>
              </div>

              {/* Üretilen sonuçlar */}
              {generatedSynonyms.length > 0 && (
                <div className="mt-4 p-4 border rounded-lg bg-muted/50">
                  <h4 className="font-medium mb-2">Üretilen Eş Anlamlılar:</h4>
                  <div className="flex flex-wrap gap-2">
                    {generatedSynonyms.map((s, i) => (
                      <Badge key={i} variant="secondary" className="text-sm">
                        {s}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground mt-3">
                    Bu eş anlamlılar "Onay Bekleyenler" listesine eklendi.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 4: Manuel Ekleme */}
        <TabsContent value="manual">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Manuel Eş Anlamlı Ekle
              </CardTitle>
              <CardDescription>
                Kendi eş anlamlılarınızı manuel olarak ekleyin
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 max-w-md">
                <div>
                  <label className="text-sm font-medium mb-1 block">Keyword</label>
                  <Input
                    placeholder="Keyword girin"
                    value={manualKeyword}
                    onChange={(e) => setManualKeyword(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Eş Anlamlı</label>
                  <Input
                    placeholder="Eş anlamlı girin"
                    value={manualSynonym}
                    onChange={(e) => setManualSynonym(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Tip</label>
                  <Select value={manualType} onValueChange={setManualType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Tip seçin" />
                    </SelectTrigger>
                    <SelectContent>
                      {/* FAZ 9.1: 6 tip - weight sırasına göre */}
                      <SelectItem value="exact_synonym">Birebir Eş Anlamlı (1.00)</SelectItem>
                      <SelectItem value="abbreviation">Kısaltma (0.95)</SelectItem>
                      <SelectItem value="english">İngilizce Çeviri (0.90)</SelectItem>
                      <SelectItem value="turkish">Türkçe Çeviri (0.85)</SelectItem>
                      <SelectItem value="broader_term">Üst Kavram (0.70)</SelectItem>
                      <SelectItem value="narrower_term">Alt Kavram (0.60)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  onClick={handleManualAdd}
                  disabled={manualLoading || !manualKeyword.trim() || !manualSynonym.trim()}
                  className="w-full"
                >
                  {manualLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Plus className="h-4 w-4 mr-2" />
                  )}
                  Eş Anlamlı Ekle
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 5: Keyword Öncelikleri (FAZ 8.2.5) */}
        <TabsContent value="importance">
          <Card>
            <CardHeader>
              <CardTitle>Keyword Öncelikleri</CardTitle>
              <CardDescription>
                Keyword başına üretilecek maksimum eş anlamlı sayısını belirleyin.
                Yüksek: 5, Normal: 3, Düşük: 2
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Ekleme formu */}
              <div className="flex gap-2 mb-6">
                <Input
                  placeholder="Keyword giriniz..."
                  value={importanceKeyword}
                  onChange={(e) => setImportanceKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddImportance()}
                  className="max-w-xs"
                />
                <Select value={importanceLevel} onValueChange={setImportanceLevel}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">Yüksek (5)</SelectItem>
                    <SelectItem value="normal">Normal (3)</SelectItem>
                    <SelectItem value="low">Düşük (2)</SelectItem>
                  </SelectContent>
                </Select>
                <Button onClick={handleAddImportance} disabled={importanceLoading}>
                  {importanceLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Plus className="h-4 w-4 mr-2" />
                  )}
                  Ekle
                </Button>
              </div>

              {/* Liste */}
              {importanceLoading && importanceList.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" />
                  Yükleniyor...
                </div>
              ) : importanceList.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Henüz özel öncelik tanımlanmamış.
                  <br />
                  <span className="text-sm">
                    Varsayılan olarak HIGH_COVERAGE keyword'leri 5, uzun keyword'ler 4, diğerleri 3 eş anlamlı alır.
                  </span>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Öncelik</TableHead>
                      <TableHead>Eklenme</TableHead>
                      <TableHead className="w-[80px]">İşlem</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {importanceList.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.keyword}</TableCell>
                        <TableCell>{getImportanceBadge(item.importance_level)}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {new Date(item.created_at).toLocaleDateString('tr-TR')}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteImportance(item.id, item.keyword)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 6: Blacklist Adayları */}
        <TabsContent value="blacklist">
          <Card>
            <CardHeader>
              <CardTitle>Blacklist Adayları</CardTitle>
              <CardDescription>
                Çok sık reddedilen eş anlamlılar. Onayla butonuyla GLOBAL_BLACKLIST'e kalıcı olarak ekleyebilirsiniz.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {blacklistLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" />
                  Yükleniyor...
                </div>
              ) : blacklistCandidates.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Henüz blacklist adayı bulunmuyor.
                  <br />
                  <span className="text-sm">
                    3+ kez reddedilen eş anlamlılar otomatik olarak burada görünecek.
                  </span>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Eş Anlamlı</TableHead>
                      <TableHead>Red Sayısı</TableHead>
                      <TableHead>Red Sebepleri</TableHead>
                      <TableHead>Son Red</TableHead>
                      <TableHead className="w-[150px]">İşlem</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {blacklistCandidates.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.synonym}</TableCell>
                        <TableCell>
                          <Badge variant="destructive">{item.reject_count}x</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                          {item.reasons_history || '-'}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {item.last_rejected_at ? new Date(item.last_rejected_at).toLocaleDateString('tr-TR') : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="default"
                              size="sm"
                              className="bg-red-600 hover:bg-red-700"
                              onClick={() => handleApproveBlacklist(item.id, item.synonym)}
                            >
                              <CheckCircle className="h-4 w-4 mr-1" />
                              Onayla
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDismissBlacklist(item.id, item.synonym)}
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Reject Dialog */}
      <Dialog open={rejectDialogOpen} onOpenChange={(open) => !open && closeRejectDialog()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Eş Anlamlı Reddet</DialogTitle>
            <DialogDescription>
              {selectedIds.length} eş anlamlı reddedilecek. Lütfen bir sebep seçin.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Red Sebebi Dropdown */}
            <div className="space-y-2">
              <Label htmlFor="reject-reason">Red Sebebi *</Label>
              <Select value={selectedReason} onValueChange={setSelectedReason}>
                <SelectTrigger id="reject-reason">
                  <SelectValue placeholder="Sebep seçiniz..." />
                </SelectTrigger>
                <SelectContent>
                  {rejectReasons.map((reason) => (
                    <SelectItem key={reason.code} value={reason.code}>
                      {reason.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedReason && (
                <p className="text-xs text-muted-foreground">
                  {rejectReasons.find(r => r.code === selectedReason)?.description}
                </p>
              )}
            </div>

            {/* Not Alanı */}
            <div className="space-y-2">
              <Label htmlFor="reject-note">Not (opsiyonel)</Label>
              <Textarea
                id="reject-note"
                placeholder="Ek açıklama ekleyin..."
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={closeRejectDialog}>
              İptal
            </Button>
            <Button
              variant="destructive"
              onClick={confirmReject}
              disabled={!selectedReason || rejectLoading}
            >
              {rejectLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <XCircle className="h-4 w-4 mr-2" />
              )}
              Reddet ({selectedIds.length})
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* FAZ 9.4: History Modal */}
      <Dialog open={historyModalOpen} onOpenChange={setHistoryModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Değişiklik Geçmişi
            </DialogTitle>
            {selectedSynonymForHistory && (
              <DialogDescription>
                <span className="font-medium">{selectedSynonymForHistory.keyword}</span> → <span className="font-medium">{selectedSynonymForHistory.synonym}</span>
              </DialogDescription>
            )}
          </DialogHeader>

          <div className="max-h-[400px] overflow-y-auto">
            {historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                Yükleniyor...
              </div>
            ) : historyData.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                Henüz değişiklik kaydı bulunmuyor.
              </div>
            ) : (
              <div className="space-y-3">
                {historyData.map((item) => {
                  const actionInfo = getActionLabel(item.action)
                  return (
                    <div key={item.id} className="border rounded-lg p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <Badge className={actionInfo.color}>
                          {actionInfo.label}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {new Date(item.changed_at).toLocaleString('tr-TR')}
                        </span>
                      </div>
                      {item.changed_by_email && (
                        <div className="text-sm text-muted-foreground">
                          Kullanıcı: {item.changed_by_email}
                        </div>
                      )}
                      {item.new_values && (
                        <div className="text-xs bg-muted p-2 rounded">
                          {item.new_values}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryModalOpen(false)}>
              Kapat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
