import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Plus, Edit, Trash2, RefreshCw, ChevronLeft, ChevronRight,
  Clock, MapPin, List, CalendarDays, Info, Mail, Send, Loader2, XCircle, ClipboardCheck,
  ShieldCheck, Eye, Search
} from 'lucide-react'
import { toast } from 'sonner'

const API_URL = import.meta.env.VITE_API_URL || ""

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

interface InterviewItem {
  id: number
  candidate_id: number
  position_id: number | null
  tarih: string
  saat: string | null
  sure_dakika: number
  tur: string
  lokasyon: string
  mulakatci: string | null
  durum: string
  notlar: string | null
  degerlendirme: string | null
  puan: number | null
  sonuc_karari: string | null
  degerlendiren: string | null
  ad_soyad: string
  email: string
  telefon: string | null
  pozisyon_baslik: string | null
  confirmation_status: string | null
  confirmed_at: string | null
}

interface CandidateItem {
  id: number
  ad_soyad: string
  email: string
}

interface DropdownData {
  positions: Array<{ id: number; baslik: string }>
  candidates: CandidateItem[]
  positionCandidates?: Record<string, CandidateItem[]>
}

interface KvkkConsentItem {
  id: number
  ad_soyad: string
  email: string | null
  telefon: string | null
  pozisyon: string | null
  consent_given: number
  consent_text: string
  kvkk_metin_versiyonu: string
  confirm_token: string
  ip_address: string | null
  user_agent: string | null
  created_at: string
  mulakat_tarih: string
  mulakat_durum: string
}

interface KvkkStats {
  toplam: number
  bu_ay: number
  aktif_mulakat: number
  metin_versiyonu: string
}

const DURUM_BADGE: Record<string, string> = {
  planlanmis: 'bg-blue-100 text-blue-800',
  tamamlandi: 'bg-green-100 text-green-800',
  iptal: 'bg-red-100 text-red-800',
  ertelendi: 'bg-yellow-100 text-yellow-800',
}

const DURUM_LABEL: Record<string, string> = {
  planlanmis: 'Planlanmış',
  tamamlandi: 'Tamamlandı',
  iptal: 'İptal',
  ertelendi: 'Ertelendi',
}

const TUR_LABEL: Record<string, string> = {
  teknik: 'Teknik',
  hr: 'İK',
  yonetici: 'Yönetici',
  genel: 'Genel',
}

const SONUC_BADGE: Record<string, string> = {
  beklemede: 'bg-amber-100 text-amber-800',
  degerlendirilecek: 'bg-blue-100 text-blue-800',
  genel_havuz: 'bg-slate-100 text-slate-800',
  arsiv: 'bg-gray-100 text-gray-800',
  kara_liste: 'bg-gray-900 text-white',
  ise_alindi: 'bg-emerald-100 text-emerald-800',
}

const SONUC_LABEL: Record<string, string> = {
  beklemede: 'Beklemede',
  degerlendirilecek: 'Değerlendirilecek',
  genel_havuz: 'Genel Havuz',
  arsiv: 'Arşiv',
  kara_liste: 'Kara Liste',
  ise_alindi: 'İşe Alındı',
}

// Onay durumu badge'i
function ConfirmationBadge({ status }: { status: string | null }) {
  if (status === 'confirmed') {
    return <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">✓ Onaylandı</span>
  }
  if (status === 'pending') {
    return <span className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded-full">⏳ Bekliyor</span>
  }
  return null
}

const DAYS = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
const MONTHS = [
  'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'
]

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('tr-TR')
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function MulakatTakvimi() {
  const [interviews, setInterviews] = useState<InterviewItem[]>([])
  const [dropdown, setDropdown] = useState<DropdownData>({ positions: [], candidates: [] })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [evalDialogOpen, setEvalDialogOpen] = useState(false)
  const [evalTarget, setEvalTarget] = useState<InterviewItem | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [cancelConfirm, setCancelConfirm] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState('calendar')
  const [filterDurum, setFilterDurum] = useState('all')
  const [filterConfirmation, setFilterConfirmation] = useState('all')

  // Calendar state
  const [calYear, setCalYear] = useState(new Date().getFullYear())
  const [calMonth, setCalMonth] = useState(new Date().getMonth())

  // Form state
  const [form, setForm] = useState({
    candidate_id: '',
    position_id: '',
    tarih: '',
    saat: '10:00',
    sure_dakika: '60',
    tur: 'teknik',
    lokasyon: 'online',
    mulakatci: '',
    notlar: '',
    onay_suresi: '3',
  })

  // Eval form
  const [evalForm, setEvalForm] = useState({
    degerlendirme: '',
    puan: '0',
    sonuc_karari: '',
    degerlendiren: '',
  })

  // Email gönder checkbox (yeni mülakat için)
  const [sendEmail, setSendEmail] = useState(true)

  // Email preview state
  const [emailPreviewOpen, setEmailPreviewOpen] = useState(false)
  const [emailPreview, setEmailPreview] = useState<{konu: string; icerik: string; to_email: string; aday_adi: string} | null>(null)
  const [emailToSend, setEmailToSend] = useState('')
  const [emailSending, setEmailSending] = useState(false)
  const [newInterviewId, setNewInterviewId] = useState<number | null>(null)

  // KVKK Onayları state
  const [kvkkModalOpen, setKvkkModalOpen] = useState(false)
  const [kvkkConsents, setKvkkConsents] = useState<KvkkConsentItem[]>([])
  const [kvkkStats, setKvkkStats] = useState<KvkkStats | null>(null)
  const [kvkkLoading, setKvkkLoading] = useState(false)
  const [kvkkSearch, setKvkkSearch] = useState('')
  const [kvkkDetailOpen, setKvkkDetailOpen] = useState(false)
  const [kvkkDetailItem, setKvkkDetailItem] = useState<KvkkConsentItem | null>(null)

  const loadInterviews = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (filterDurum !== 'all') params.append('durum', filterDurum)
    if (filterConfirmation !== 'all') params.append('confirmation_status', filterConfirmation)

    fetch(`${API_URL}/api/interviews?${params}`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) setInterviews(res.data)
      })
      .catch(err => console.error('Interview hatasi:', err))
      .finally(() => setLoading(false))
  }, [filterDurum, filterConfirmation])

  const loadDropdown = useCallback(() => {
    fetch(`${API_URL}/api/interviews/dropdown-data`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) setDropdown(res.data)
      })
      .catch(err => console.error('Dropdown hatasi:', err))
  }, [])

  useEffect(() => { loadInterviews() }, [loadInterviews])
  useEffect(() => { loadDropdown() }, [loadDropdown])

  const resetForm = () => {
    setForm({
      candidate_id: '', position_id: '', tarih: '', saat: '10:00',
      sure_dakika: '60', tur: 'teknik', lokasyon: 'online', mulakatci: '', notlar: '', onay_suresi: '3',
    })
    setEditingId(null)
    setSendEmail(true)
  }

  const openCreate = () => { resetForm(); setDialogOpen(true) }

  const openEdit = (item: InterviewItem) => {
    const d = new Date(item.tarih)
    setForm({
      candidate_id: String(item.candidate_id),
      position_id: item.position_id ? String(item.position_id) : 'none',
      tarih: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
      saat: item.saat || formatTime(item.tarih),
      sure_dakika: String(item.sure_dakika),
      tur: item.tur,
      lokasyon: item.lokasyon,
      mulakatci: item.mulakatci || '',
      notlar: item.notlar || '',
      onay_suresi: '3',
    })
    setEditingId(item.id)
    setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!form.candidate_id || !form.tarih || !form.saat) return

    setSaving(true)
    try {
      const tarihStr = `${form.tarih}T${form.saat}:00`
      const payload: Record<string, unknown> = {
        candidate_id: Number(form.candidate_id),
        position_id: form.position_id && form.position_id !== 'none' ? Number(form.position_id) : null,
        tarih: tarihStr,
        sure_dakika: Number(form.sure_dakika),
        tur: form.tur,
        lokasyon: form.lokasyon,
        mulakatci: form.mulakatci || null,
        notlar: form.notlar || null,
        onay_suresi: parseInt(form.onay_suresi) || 3,
      }

      // Kaydetmeden önce email preview gösterilecek mi kontrol et
      const shouldShowEmailPreview = !editingId && sendEmail

      const url = editingId
        ? `${API_URL}/api/interviews/${editingId}`
        : `${API_URL}/api/interviews`
      const method = editingId ? 'PUT' : 'POST'

      const res = await fetch(url, { method, headers: getHeaders(), body: JSON.stringify(payload) })
      const data = await res.json()

      if (!res.ok) {
        toast.error(data.detail || 'Mülakat kaydedilemedi')
        return
      }

      if (data.success) {
        const interviewId = data.id

        // Başarı bildirimi
        toast.success(editingId ? 'Mülakat güncellendi' : 'Mülakat oluşturuldu')

        // Önce form dialog'u kapat
        setDialogOpen(false)
        resetForm()

        // Email preview gösterilecekse
        if (shouldShowEmailPreview && interviewId) {
          // Önce email preview verisini çek
          try {
            const previewRes = await fetch(`${API_URL}/api/interviews/${interviewId}/email-preview`, { headers: getHeaders() })
            const previewData = await previewRes.json()

            if (previewData.success && previewData.data) {
              // State'leri set et
              setNewInterviewId(interviewId)
              setEmailPreview(previewData.data)
              setEmailToSend(previewData.data.to_email)

              // Dialog'un açılması için kısa bir bekleme
              setTimeout(() => {
                setEmailPreviewOpen(true)
              }, 200)
            }
          } catch (err) {
            console.error('Email preview hatasi:', err)
          }
        }

        // En son interview listesini yenile
        loadInterviews()
      } else {
        toast.error('Beklenmeyen sunucu yanıtı')
      }
    } catch (err) {
      console.error('Save hatasi:', err)
      toast.error('Mülakat kaydedilemedi')
    } finally {
      setSaving(false)
    }
  }

  const handleSendEmail = async () => {
    if (!newInterviewId || !emailToSend) return

    setEmailSending(true)
    try {
      const res = await fetch(`${API_URL}/api/interviews/${newInterviewId}/send-email`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ to_email: emailToSend })
      })
      const data = await res.json()

      if (data.success) {
        setEmailPreviewOpen(false)
        setEmailPreview(null)
        setNewInterviewId(null)
        setEmailToSend('')
      } else {
        console.error('Email gonderme hatasi:', data.detail)
        toast.error(`Email gönderilemedi: ${data.detail}`)
      }
    } catch (err) {
      console.error('Email gonderme hatasi:', err)
      toast.error('Email gönderilemedi')
    } finally {
      setEmailSending(false)
    }
  }

  const handleDelete = (id: number) => {
    fetch(`${API_URL}/api/interviews/${id}`, { method: 'DELETE', headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setDeleteConfirm(null); loadInterviews() }
      })
      .catch(err => console.error('Delete hatasi:', err))
  }

  const handleCancel = async (id: number) => {
    try {
      const res = await fetch(`${API_URL}/api/interviews/${id}`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify({ durum: 'iptal' })
      })
      const data = await res.json()

      if (data.success) {
        setCancelConfirm(null)
        // Düzenleme dialogu açıksa kapat
        if (dialogOpen && editingId === id) {
          setDialogOpen(false)
          resetForm()
        }
        toast.success('Mülakat iptal edildi')
        loadInterviews()
      } else {
        toast.error(`Mülakat iptal edilemedi: ${data.detail || 'Bilinmeyen hata'}`)
      }
    } catch (err) {
      console.error('Cancel hatasi:', err)
      toast.error('Mülakat iptal edilemedi')
    }
  }

  const openEval = (item: InterviewItem) => {
    setEvalTarget(item)
    setEvalForm({
      degerlendirme: item.degerlendirme || '',
      puan: String(item.puan || 0),
      sonuc_karari: item.sonuc_karari || '',
      degerlendiren: item.degerlendiren || '',
    })
    setEvalDialogOpen(true)
  }

  const handleEvalSave = async () => {
    if (!evalTarget) return
    const payload: Record<string, unknown> = {
      durum: 'tamamlandi',
      degerlendirme: evalForm.degerlendirme || null,
      puan: evalForm.puan && Number(evalForm.puan) > 0 ? Number(evalForm.puan) : null,
      sonuc_karari: evalForm.sonuc_karari || 'beklemede',
      degerlendiren: evalForm.degerlendiren || null,
    }
    try {
      const res = await fetch(`${API_URL}/api/interviews/${evalTarget.id}`, {
        method: 'PUT', headers: getHeaders(), body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (data.success) {
        setEvalDialogOpen(false)
        setEvalTarget(null)
        const actionMessages: Record<string, string> = {
          genel_havuz: 'Değerlendirme kaydedildi, aday Genel Havuz\'a taşındı',
          arsiv: 'Değerlendirme kaydedildi, aday Arşiv\'e taşındı',
          kara_liste: 'Değerlendirme kaydedildi, aday Arşiv\'e taşındı (Kara Liste notu)',
          ise_alindi: 'Değerlendirme kaydedildi, aday İşe Alındı olarak işaretlendi',
        }
        toast.success(actionMessages[evalForm.sonuc_karari] || 'Değerlendirme kaydedildi')
        loadInterviews()
      } else {
        toast.error(data.detail || 'Değerlendirme kaydedilemedi')
      }
    } catch (err) {
      console.error('Eval hatasi:', err)
      toast.error('Değerlendirme kaydedilemedi')
    }
  }

  // KVKK Onayları yükleme
  const loadKvkkConsents = () => {
    setKvkkLoading(true)
    fetch(`${API_URL}/api/interviews/kvkk-consents`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setKvkkConsents(res.data)
          setKvkkStats(res.stats)
        }
      })
      .catch(err => {
        console.error('KVKK consents hatası:', err)
        toast.error('KVKK onay kayıtları yüklenemedi')
      })
      .finally(() => setKvkkLoading(false))
  }

  // KVKK arama filtresi
  const filteredKvkkConsents = kvkkConsents.filter(item => {
    if (!kvkkSearch) return true
    const search = kvkkSearch.toLocaleLowerCase('tr-TR')
    return (
      item.ad_soyad.toLocaleLowerCase('tr-TR').includes(search) ||
      (item.email && item.email.toLocaleLowerCase('tr-TR').includes(search)) ||
      (item.pozisyon && item.pozisyon.toLocaleLowerCase('tr-TR').includes(search))
    )
  })

  // Calendar helpers
  const getDaysInMonth = (y: number, m: number) => new Date(y, m + 1, 0).getDate()
  const getFirstDayOfMonth = (y: number, m: number) => {
    const day = new Date(y, m, 1).getDay()
    return day === 0 ? 6 : day - 1 // Pazartesi=0
  }

  const interviewsByDate = interviews.reduce((acc, iv) => {
    const key = iv.tarih.split('T')[0]
    if (!acc[key]) acc[key] = []
    acc[key].push(iv)
    return acc
  }, {} as Record<string, InterviewItem[]>)

  const prevMonth = () => {
    if (calMonth === 0) { setCalMonth(11); setCalYear(calYear - 1) }
    else setCalMonth(calMonth - 1)
  }
  const nextMonth = () => {
    if (calMonth === 11) { setCalMonth(0); setCalYear(calYear + 1) }
    else setCalMonth(calMonth + 1)
  }

  // Düzenleme dialogundaki mülakatın durumunu bul
  const editingInterview = editingId ? interviews.find(i => i.id === editingId) : null

  const renderCalendar = () => {
    const daysInMonth = getDaysInMonth(calYear, calMonth)
    const firstDay = getFirstDayOfMonth(calYear, calMonth)
    const cells: React.ReactNode[] = []

    for (let i = 0; i < firstDay; i++) {
      cells.push(<div key={`empty-${i}`} className="h-24 border border-gray-100 bg-gray-50/50" />)
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const dateKey = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
      const dayInterviews = interviewsByDate[dateKey] || []
      const isToday = new Date().toISOString().split('T')[0] === dateKey

      cells.push(
        <div key={day} className={`h-24 border border-gray-100 p-1 overflow-hidden ${isToday ? 'bg-blue-50 border-blue-300' : 'hover:bg-gray-50'}`}>
          <div className={`text-xs font-medium mb-0.5 ${isToday ? 'text-blue-600' : 'text-gray-600'}`}>{day}</div>
          {dayInterviews.slice(0, 2).map(iv => (
            <div
              key={iv.id}
              onClick={() => openEdit(iv)}
              className={`text-[10px] leading-tight p-0.5 rounded mb-0.5 cursor-pointer ${
                iv.durum === 'tamamlandi' ? 'bg-green-100 text-green-700' :
                iv.durum === 'iptal' ? 'bg-red-100 text-red-700' :
                iv.durum === 'ertelendi' ? 'bg-yellow-100 text-yellow-700' :
                'bg-blue-100 text-blue-700'
              }`}
            >
              <div className="flex items-center gap-0.5 truncate">
                <span>{formatTime(iv.tarih)} {iv.ad_soyad.split(' ')[0]}</span>
                {iv.confirmation_status === 'confirmed' && <span className="text-green-600">✓</span>}
              </div>
            </div>
          ))}
          {dayInterviews.length > 2 && (
            <div className="text-[10px] text-gray-500">+{dayInterviews.length - 2} daha</div>
          )}
        </div>
      )
    }

    return (
      <div className="grid grid-cols-7 gap-0">
        {DAYS.map(d => (
          <div key={d} className="h-8 flex items-center justify-center text-xs font-medium text-gray-500 border-b">{d}</div>
        ))}
        {cells}
      </div>
    )
  }

  const stats = {
    total: interviews.length,
    planlanmis: interviews.filter(i => i.durum === 'planlanmis').length,
    tamamlandi: interviews.filter(i => i.durum === 'tamamlandi').length,
    iptal: interviews.filter(i => i.durum === 'iptal').length,
    onaylandi: interviews.filter(i => i.confirmation_status === 'confirmed').length,
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Mülakat Takvimi</h2>
          <p className="text-muted-foreground text-sm">Mülakatları planlayın ve takip edin</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadInterviews} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Yenile
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 mr-1" /> Yeni Mülakat
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3">
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold">{stats.total}</div><div className="text-xs text-muted-foreground">Toplam</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-blue-600">{stats.planlanmis}</div><div className="text-xs text-muted-foreground">Planlanmış</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-green-600">{stats.onaylandi}</div><div className="text-xs text-muted-foreground">Onaylandı</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-emerald-600">{stats.tamamlandi}</div><div className="text-xs text-muted-foreground">Tamamlandı</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-red-600">{stats.iptal}</div><div className="text-xs text-muted-foreground">İptal</div></CardContent></Card>
      </div>

      {/* Filter + Tabs */}
      <div className="flex items-center justify-between">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="calendar"><CalendarDays className="h-4 w-4 mr-1" /> Takvim</TabsTrigger>
            <TabsTrigger value="list"><List className="h-4 w-4 mr-1" /> Liste</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex gap-2">
          <Select value={filterDurum} onValueChange={setFilterDurum}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tüm Durumlar</SelectItem>
              <SelectItem value="planlanmis">Planlanmış</SelectItem>
              <SelectItem value="tamamlandi">Tamamlandı</SelectItem>
              <SelectItem value="iptal">İptal</SelectItem>
              <SelectItem value="ertelendi">Ertelendi</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterConfirmation} onValueChange={setFilterConfirmation}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tüm Onay</SelectItem>
              <SelectItem value="confirmed">✓ Onaylandı</SelectItem>
              <SelectItem value="pending">⏳ Bekliyor</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={() => { setKvkkModalOpen(true); loadKvkkConsents() }}>
            <ShieldCheck className="h-4 w-4 mr-1" /> KVKK Onayları
          </Button>
        </div>
      </div>

      {/* Calendar View */}
      {activeTab === 'calendar' && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Button variant="ghost" size="sm" onClick={prevMonth}><ChevronLeft className="h-4 w-4" /></Button>
              <CardTitle className="text-lg">{MONTHS[calMonth]} {calYear}</CardTitle>
              <Button variant="ghost" size="sm" onClick={nextMonth}><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </CardHeader>
          <CardContent className="p-2">
            {renderCalendar()}
          </CardContent>
        </Card>
      )}

      {/* List View */}
      {activeTab === 'list' && (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Aday</TableHead>
                  <TableHead>Pozisyon</TableHead>
                  <TableHead>Tarih / Saat</TableHead>
                  <TableHead>Tür</TableHead>
                  <TableHead>Lokasyon</TableHead>
                  <TableHead>Mülakatçı</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead>Sonuç</TableHead>
                  <TableHead className="text-right">İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {interviews.length === 0 ? (
                  <TableRow><TableCell colSpan={9} className="text-center py-8 text-muted-foreground">Mülakat bulunamadı</TableCell></TableRow>
                ) : interviews.map(iv => (
                  <TableRow key={iv.id}>
                    <TableCell>
                      <div className="font-medium text-sm">{iv.ad_soyad}</div>
                      <div className="text-xs text-muted-foreground">{iv.email}</div>
                    </TableCell>
                    <TableCell className="text-sm">{iv.pozisyon_baslik || '-'}</TableCell>
                    <TableCell>
                      <div className="text-sm">{formatDate(iv.tarih)}</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="h-3 w-3" />{formatTime(iv.tarih)} ({iv.sure_dakika} dk)</div>
                    </TableCell>
                    <TableCell><Badge variant="outline" className="text-xs">{TUR_LABEL[iv.tur] || iv.tur}</Badge></TableCell>
                    <TableCell className="text-sm flex items-center gap-1"><MapPin className="h-3 w-3 text-muted-foreground" />{iv.lokasyon}</TableCell>
                    <TableCell className="text-sm">{iv.mulakatci || '-'}</TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge className={`text-xs ${DURUM_BADGE[iv.durum] || ''}`}>{DURUM_LABEL[iv.durum] || iv.durum}</Badge>
                        <ConfirmationBadge status={iv.confirmation_status} />
                      </div>
                    </TableCell>
                    <TableCell>
                      {iv.sonuc_karari ? (
                        <Badge className={`text-xs ${SONUC_BADGE[iv.sonuc_karari] || ''}`}>
                          {SONUC_LABEL[iv.sonuc_karari] || iv.sonuc_karari}
                        </Badge>
                      ) : iv.puan && iv.puan > 0 ? (
                        <span className="text-xs text-muted-foreground">{iv.puan}/10</span>
                      ) : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openEval(iv)} title="Değerlendir"><Edit className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleteConfirm(iv.id)} className="text-red-500 hover:text-red-700"><Trash2 className="h-3.5 w-3.5" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(o) => { if (!o) { setDialogOpen(false); resetForm() } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingId ? 'Mülakat Düzenle' : 'Yeni Mülakat'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-sm">Pozisyon</Label>
              <Select value={form.position_id} onValueChange={v => setForm({...form, position_id: v, candidate_id: ''})}>
                <SelectTrigger><SelectValue placeholder="Pozisyon seçin (opsiyonel)" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Tümü (pozisyon seçme)</SelectItem>
                  {dropdown.positions.map(p => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.baslik}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm">Aday *</Label>
              <Select value={form.candidate_id} onValueChange={v => setForm({...form, candidate_id: v})}>
                <SelectTrigger><SelectValue placeholder="Aday seçin" /></SelectTrigger>
                <SelectContent>
                  {form.position_id && form.position_id !== 'none' && dropdown.positionCandidates?.[form.position_id] ? (
                    dropdown.positionCandidates[form.position_id].length > 0 ? (
                      dropdown.positionCandidates[form.position_id].map(c => (
                        <SelectItem key={c.id} value={String(c.id)}>{c.ad_soyad} ({c.email})</SelectItem>
                      ))
                    ) : (
                      <div className="px-2 py-1.5 text-sm text-muted-foreground">Bu pozisyona atanmış aday yok</div>
                    )
                  ) : (
                    dropdown.candidates.map(c => (
                      <SelectItem key={c.id} value={String(c.id)}>{c.ad_soyad} ({c.email})</SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {(!form.position_id || form.position_id === 'none') && form.candidate_id && (
                <div className="flex items-start gap-1.5 mt-1.5 p-2 bg-blue-50 rounded text-xs text-blue-700">
                  <Info className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                  <span>Bu aday henüz bir pozisyona atanmamış. Pozisyonsuz mülakat oluşturabilirsiniz.</span>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm">Tarih *</Label>
                <Input type="date" value={form.tarih} onChange={e => setForm({...form, tarih: e.target.value})} placeholder="GG.AA.YYYY" />
              </div>
              <div>
                <Label className="text-sm">Saat *</Label>
                <Input type="time" value={form.saat} onChange={e => setForm({...form, saat: e.target.value})} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-sm">Süre (dk)</Label>
                <Select value={form.sure_dakika} onValueChange={v => setForm({...form, sure_dakika: v})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 dk</SelectItem>
                    <SelectItem value="45">45 dk</SelectItem>
                    <SelectItem value="60">60 dk</SelectItem>
                    <SelectItem value="90">90 dk</SelectItem>
                    <SelectItem value="120">120 dk</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm">Tür</Label>
                <Select value={form.tur} onValueChange={v => setForm({...form, tur: v})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="teknik">Teknik</SelectItem>
                    <SelectItem value="hr">İK</SelectItem>
                    <SelectItem value="yonetici">Yönetici</SelectItem>
                    <SelectItem value="genel">Genel</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm">Lokasyon</Label>
                <Select value={form.lokasyon} onValueChange={v => setForm({...form, lokasyon: v})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="online">Online</SelectItem>
                    <SelectItem value="ofis">Ofis</SelectItem>
                    <SelectItem value="telefon">Telefon</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-sm">Mülakatçı</Label>
              <Input value={form.mulakatci} onChange={e => setForm({...form, mulakatci: e.target.value})} placeholder="Mülakatçı adı" />
            </div>
            <div>
              <Label className="text-sm">Onay Süresi</Label>
              <Select value={form.onay_suresi} onValueChange={v => setForm({...form, onay_suresi: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 gün</SelectItem>
                  <SelectItem value="3">3 gün</SelectItem>
                  <SelectItem value="7">7 gün</SelectItem>
                  <SelectItem value="14">14 gün</SelectItem>
                  <SelectItem value="30">30 gün</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm">Notlar</Label>
              <Textarea value={form.notlar} onChange={e => setForm({...form, notlar: e.target.value})} placeholder="Notlar..." rows={2} />
            </div>
            {!editingId && (
              <div className="flex items-center gap-2 mt-2">
                <input
                  type="checkbox"
                  id="sendEmail"
                  checked={sendEmail}
                  onChange={e => setSendEmail(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="sendEmail" className="text-sm text-muted-foreground cursor-pointer">
                  Adaya mülakat daveti emaili gönder
                </label>
              </div>
            )}
          </div>
          <DialogFooter className="flex items-center justify-between sm:justify-between">
            {editingId && editingInterview?.durum === 'planlanmis' ? (
              <Button variant="destructive" size="sm" onClick={() => setCancelConfirm(editingId)}>
                <XCircle className="h-4 w-4 mr-1" /> İptal Et
              </Button>
            ) : (
              <div />
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => { setDialogOpen(false); resetForm() }}>Vazgeç</Button>
              <Button onClick={handleSave} disabled={!form.candidate_id || !form.tarih || !form.saat || saving}>
                {saving ? (
                  <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Kaydediliyor...</>
                ) : (
                  'Kaydet'
                )}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Evaluation Dialog */}
      <Dialog open={evalDialogOpen} onOpenChange={o => { if (!o) setEvalDialogOpen(false) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5" /> Mülakat Değerlendirmesi
            </DialogTitle>
          </DialogHeader>
          {evalTarget && (
            <div className="space-y-4">
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="text-sm font-medium">{evalTarget.ad_soyad}</div>
                <div className="text-xs text-muted-foreground">{evalTarget.pozisyon_baslik || 'Pozisyon belirtilmemiş'}</div>
                <div className="text-xs text-muted-foreground mt-1">{formatDate(evalTarget.tarih)} - {formatTime(evalTarget.tarih)}</div>
              </div>
              <div>
                <Label className="text-sm">Değerlendirme Durumu</Label>
                <Select value={evalForm.sonuc_karari || 'beklemede'} onValueChange={v => setEvalForm({...evalForm, sonuc_karari: v})}>
                  <SelectTrigger className="mt-1"><SelectValue placeholder="Durum seçin" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="beklemede">Beklemede</SelectItem>
                    <SelectItem value="degerlendirilecek">Değerlendirilecek</SelectItem>
                    <SelectItem value="genel_havuz">Genel Havuz</SelectItem>
                    <SelectItem value="arsiv">Arşiv</SelectItem>
                    <SelectItem value="kara_liste">Kara Liste</SelectItem>
                    <SelectItem value="ise_alindi">İşe Alındı</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm">Puan (1-10)</Label>
                <div className="flex items-center gap-2 mt-1">
                  <Input
                    type="number"
                    min="0"
                    max="10"
                    value={evalForm.puan}
                    onChange={e => {
                      const val = Math.min(10, Math.max(0, Number(e.target.value)))
                      setEvalForm({...evalForm, puan: String(val)})
                    }}
                    className="w-20"
                  />
                  <span className="text-sm text-muted-foreground">/ 10</span>
                  {Number(evalForm.puan) > 0 && (
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          Number(evalForm.puan) >= 7 ? 'bg-emerald-500' :
                          Number(evalForm.puan) >= 4 ? 'bg-amber-500' :
                          'bg-red-500'
                        }`}
                        style={{ width: `${Number(evalForm.puan) * 10}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
              <div>
                <Label className="text-sm">Değerlendiren</Label>
                <Input
                  value={evalForm.degerlendiren}
                  onChange={e => setEvalForm({...evalForm, degerlendiren: e.target.value})}
                  placeholder="Değerlendiren kişi adı"
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-sm">Değerlendirme Notu</Label>
                <Textarea
                  value={evalForm.degerlendirme}
                  onChange={e => setEvalForm({...evalForm, degerlendirme: e.target.value})}
                  placeholder="Mülakat değerlendirmesi, notlar..."
                  rows={4}
                  className="mt-1"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEvalDialogOpen(false)}>Vazgeç</Button>
            <Button onClick={handleEvalSave}>
              <ClipboardCheck className="h-4 w-4 mr-1" /> Tamamla ve Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={deleteConfirm !== null} onOpenChange={o => { if (!o) setDeleteConfirm(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Mülakatı Sil</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Bu mülakatı silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Vazgeç</Button>
            <Button variant="destructive" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>Sil</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Confirm Dialog */}
      <Dialog open={cancelConfirm !== null} onOpenChange={o => { if (!o) setCancelConfirm(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Mülakatı İptal Et</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Bu mülakatı iptal etmek istediğinize emin misiniz? Aday durumu otomatik olarak güncellenecektir.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelConfirm(null)}>Vazgeç</Button>
            <Button variant="destructive" onClick={() => cancelConfirm && handleCancel(cancelConfirm)}>
              <XCircle className="h-4 w-4 mr-1" /> İptal Et
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Email Preview Dialog */}
      <Dialog open={emailPreviewOpen} onOpenChange={o => {
        if (!o) {
          setEmailPreviewOpen(false)
          setEmailPreview(null)
          setNewInterviewId(null)
          setEmailToSend('')
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" /> Email Önizleme
            </DialogTitle>
          </DialogHeader>
          {emailPreview && (
            <div className="space-y-4 flex-1 overflow-auto">
              <div>
                <Label className="text-sm font-medium">Alıcı Email</Label>
                <Input
                  value={emailToSend}
                  onChange={e => setEmailToSend(e.target.value)}
                  placeholder="aday@email.com"
                  className="mt-1"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Aday: {emailPreview.aday_adi}
                </p>
              </div>
              <div>
                <Label className="text-sm font-medium">Konu</Label>
                <div className="mt-1 p-2 bg-gray-50 rounded border text-sm">
                  {emailPreview.konu}
                </div>
              </div>
              <div>
                <Label className="text-sm font-medium">İçerik</Label>
                <div className="mt-1 p-3 bg-gray-50 rounded border text-sm whitespace-pre-wrap font-mono text-xs max-h-64 overflow-auto">
                  {emailPreview.icerik}
                </div>
              </div>
            </div>
          )}
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => {
              setEmailPreviewOpen(false)
              setEmailPreview(null)
              setNewInterviewId(null)
              setEmailToSend('')
            }}>
              Gönderme
            </Button>
            <Button onClick={handleSendEmail} disabled={emailSending || !emailToSend}>
              {emailSending ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Gönderiliyor...</>
              ) : (
                <><Send className="h-4 w-4 mr-2" /> Gönder</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* KVKK Onayları Modal */}
      <Dialog open={kvkkModalOpen} onOpenChange={(o) => { if (!o) { setKvkkModalOpen(false); setKvkkSearch('') } }}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" /> KVKK Onayları
            </DialogTitle>
          </DialogHeader>

          {/* İstatistik Kartları */}
          <div className="grid grid-cols-4 gap-3">
            <Card>
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold">{kvkkStats?.toplam || 0}</div>
                <div className="text-xs text-muted-foreground">Toplam Onay</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-blue-600">{kvkkStats?.bu_ay || 0}</div>
                <div className="text-xs text-muted-foreground">Bu Ay</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <div className="text-2xl font-bold text-green-600">{kvkkStats?.aktif_mulakat || 0}</div>
                <div className="text-xs text-muted-foreground">Aktif Mülakat</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <div className="text-sm font-bold text-purple-600">{kvkkStats?.metin_versiyonu || '-'}</div>
                <div className="text-xs text-muted-foreground">Metin Versiyonu</div>
              </CardContent>
            </Card>
          </div>

          {/* Arama */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Aday adı, email veya pozisyon ara..."
              value={kvkkSearch}
              onChange={e => setKvkkSearch(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Tablo */}
          <div className="flex-1 overflow-auto">
            {kvkkLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Aday</TableHead>
                    <TableHead>Pozisyon</TableHead>
                    <TableHead>Onay Tarihi</TableHead>
                    <TableHead>KVKK Durumu</TableHead>
                    <TableHead>Mülakat Durumu</TableHead>
                    <TableHead>IP Adresi</TableHead>
                    <TableHead>Versiyon</TableHead>
                    <TableHead className="text-right">İşlemler</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredKvkkConsents.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                        {kvkkSearch ? 'Aramayla eşleşen kayıt bulunamadı' : 'KVKK onay kaydı bulunamadı'}
                      </TableCell>
                    </TableRow>
                  ) : filteredKvkkConsents.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <div className="font-medium text-sm">{item.ad_soyad}</div>
                        <div className="text-xs text-muted-foreground">{item.email || '-'}</div>
                      </TableCell>
                      <TableCell className="text-sm">{item.pozisyon || '-'}</TableCell>
                      <TableCell className="text-sm">
                        {new Date(item.created_at).toLocaleString('tr-TR')}
                      </TableCell>
                      <TableCell>
                        <Badge className="bg-green-100 text-green-800 text-xs">Onaylandı</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={`text-xs ${DURUM_BADGE[item.mulakat_durum] || ''}`}>
                          {DURUM_LABEL[item.mulakat_durum] || item.mulakat_durum}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{item.ip_address || '-'}</TableCell>
                      <TableCell className="text-xs">{item.kvkk_metin_versiyonu}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => { setKvkkDetailItem(item); setKvkkDetailOpen(true) }}>
                          <Eye className="h-3.5 w-3.5 mr-1" /> Görüntüle
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* KVKK Detay Modal */}
      <Dialog open={kvkkDetailOpen} onOpenChange={(o) => { if (!o) { setKvkkDetailOpen(false); setKvkkDetailItem(null) } }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" /> KVKK Onay Detayı
            </DialogTitle>
          </DialogHeader>
          {kvkkDetailItem && (
            <div className="space-y-4 flex-1 overflow-auto">
              {/* Immutable Uyarı */}
              <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <span className="text-lg">🔒</span>
                <p className="text-sm text-amber-800">Bu kayıt değiştirilemez (immutable KVKK audit trail). Onay anındaki bilgiler korunmaktadır.</p>
              </div>

              {/* Damgalama Bilgileri */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">Ad Soyad</div>
                  <div className="text-sm font-medium">{kvkkDetailItem.ad_soyad}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">Email</div>
                  <div className="text-sm font-medium">{kvkkDetailItem.email || '-'}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">Telefon</div>
                  <div className="text-sm font-medium">{kvkkDetailItem.telefon || '-'}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">IP Adresi</div>
                  <div className="text-sm font-medium">{kvkkDetailItem.ip_address || '-'}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">Onay Tarihi</div>
                  <div className="text-sm font-medium">{new Date(kvkkDetailItem.created_at).toLocaleString('tr-TR')}</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">KVKK Metin Versiyonu</div>
                  <div className="text-sm font-medium">{kvkkDetailItem.kvkk_metin_versiyonu}</div>
                </div>
                <div className="col-span-2 p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-muted-foreground mb-1">Tarayıcı Bilgisi</div>
                  <div className="text-xs font-mono break-all">{kvkkDetailItem.user_agent || '-'}</div>
                </div>
              </div>

              {/* KVKK Metni */}
              <div>
                <div className="text-sm font-medium mb-2">Onaylanan KVKK Aydınlatma Metni</div>
                <div className="p-4 bg-gray-50 rounded-lg border max-h-48 overflow-y-auto">
                  <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed">{kvkkDetailItem.consent_text}</pre>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setKvkkDetailOpen(false); setKvkkDetailItem(null) }}>Kapat</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
