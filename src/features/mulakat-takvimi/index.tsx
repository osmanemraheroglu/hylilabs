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
  CalendarClock, Plus, Edit, Trash2, RefreshCw, ChevronLeft, ChevronRight,
  Clock, MapPin, Star, List, CalendarDays, Info
} from 'lucide-react'

const API_URL = 'http://***REMOVED***:8000'

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
  ad_soyad: string
  email: string
  telefon: string | null
  pozisyon_baslik: string | null
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

const DAYS = ['Pzt', 'Sal', 'Car', 'Per', 'Cum', 'Cmt', 'Paz']
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
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [evalDialogOpen, setEvalDialogOpen] = useState(false)
  const [evalTarget, setEvalTarget] = useState<InterviewItem | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState('calendar')
  const [filterDurum, setFilterDurum] = useState('all')

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
  })

  // Eval form
  const [evalForm, setEvalForm] = useState({ degerlendirme: '', puan: '0' })

  // Email gönder checkbox (yeni mülakat için)
  const [sendEmail, setSendEmail] = useState(true)

  const loadInterviews = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (filterDurum !== 'all') params.append('durum', filterDurum)

    fetch(`${API_URL}/api/interviews?${params}`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) setInterviews(res.data)
      })
      .catch(err => console.error('Interview hatasi:', err))
      .finally(() => setLoading(false))
  }, [filterDurum])

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
      sure_dakika: '60', tur: 'teknik', lokasyon: 'online', mulakatci: '', notlar: '',
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
    })
    setEditingId(item.id)
    setDialogOpen(true)
  }

  const handleSave = () => {
    if (!form.candidate_id || !form.tarih || !form.saat) return

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
    }

    // Yeni mülakat için email gönderme seçeneği
    if (!editingId) {
      payload.send_email = sendEmail
    }

    const url = editingId
      ? `${API_URL}/api/interviews/${editingId}`
      : `${API_URL}/api/interviews`
    const method = editingId ? 'PUT' : 'POST'

    fetch(url, { method, headers: getHeaders(), body: JSON.stringify(payload) })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setDialogOpen(false); resetForm(); loadInterviews() }
      })
      .catch(err => console.error('Save hatasi:', err))
  }

  const handleDelete = (id: number) => {
    fetch(`${API_URL}/api/interviews/${id}`, { method: 'DELETE', headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setDeleteConfirm(null); loadInterviews() }
      })
      .catch(err => console.error('Delete hatasi:', err))
  }

  const openEval = (item: InterviewItem) => {
    setEvalTarget(item)
    setEvalForm({ degerlendirme: item.degerlendirme || '', puan: String(item.puan || 0) })
    setEvalDialogOpen(true)
  }

  const handleEvalSave = () => {
    if (!evalTarget) return
    const payload = {
      durum: 'tamamlandi',
      degerlendirme: evalForm.degerlendirme,
      puan: Number(evalForm.puan),
    }
    fetch(`${API_URL}/api/interviews/${evalTarget.id}`, {
      method: 'PUT', headers: getHeaders(), body: JSON.stringify(payload)
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setEvalDialogOpen(false); setEvalTarget(null); loadInterviews() }
      })
      .catch(err => console.error('Eval hatasi:', err))
  }

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
              className={`text-[10px] leading-tight p-0.5 rounded mb-0.5 cursor-pointer truncate ${
                iv.durum === 'tamamlandi' ? 'bg-green-100 text-green-700' :
                iv.durum === 'iptal' ? 'bg-red-100 text-red-700' :
                iv.durum === 'ertelendi' ? 'bg-yellow-100 text-yellow-700' :
                'bg-blue-100 text-blue-700'
              }`}
            >
              {formatTime(iv.tarih)} {iv.ad_soyad.split(' ')[0]}
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
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <CalendarClock className="h-6 w-6" /> Mülakat Takvimi
          </h2>
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
      <div className="grid grid-cols-4 gap-3">
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold">{stats.total}</div><div className="text-xs text-muted-foreground">Toplam</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-blue-600">{stats.planlanmis}</div><div className="text-xs text-muted-foreground">Planlanmış</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-green-600">{stats.tamamlandi}</div><div className="text-xs text-muted-foreground">Tamamlandı</div></CardContent></Card>
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
        <Select value={filterDurum} onValueChange={setFilterDurum}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tüm Durumlar</SelectItem>
            <SelectItem value="planlanmis">Planlanmış</SelectItem>
            <SelectItem value="tamamlandi">Tamamlandı</SelectItem>
            <SelectItem value="iptal">İptal</SelectItem>
            <SelectItem value="ertelendi">Ertelendi</SelectItem>
          </SelectContent>
        </Select>
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
                  <TableHead>Puan</TableHead>
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
                    <TableCell><Badge className={`text-xs ${DURUM_BADGE[iv.durum] || ''}`}>{DURUM_LABEL[iv.durum] || iv.durum}</Badge></TableCell>
                    <TableCell>
                      {iv.puan ? (
                        <div className="flex items-center gap-0.5">{[1,2,3,4,5].map(s => <Star key={s} className={`h-3 w-3 ${s <= iv.puan! ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`} />)}</div>
                      ) : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {iv.durum === 'planlanmis' && (
                          <Button variant="ghost" size="sm" onClick={() => openEval(iv)} title="Değerlendir"><Star className="h-3.5 w-3.5" /></Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => openEdit(iv)}><Edit className="h-3.5 w-3.5" /></Button>
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
                <Label className="text-sm">Sure (dk)</Label>
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
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDialogOpen(false); resetForm() }}>İptal</Button>
            <Button onClick={handleSave} disabled={!form.candidate_id || !form.tarih || !form.saat}>Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Evaluation Dialog */}
      <Dialog open={evalDialogOpen} onOpenChange={o => { if (!o) setEvalDialogOpen(false) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Mülakat Değerlendirmesi</DialogTitle>
          </DialogHeader>
          {evalTarget && (
            <div className="space-y-3">
              <div className="text-sm"><span className="font-medium">{evalTarget.ad_soyad}</span> - {evalTarget.pozisyon_baslik || 'Pozisyon belirtilmemiş'}</div>
              <div>
                <Label className="text-sm">Puan (1-5)</Label>
                <div className="flex gap-1 mt-1">
                  {[1,2,3,4,5].map(s => (
                    <button key={s} onClick={() => setEvalForm({...evalForm, puan: String(s)})} className="focus:outline-none">
                      <Star className={`h-6 w-6 ${s <= Number(evalForm.puan) ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`} />
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label className="text-sm">Değerlendirme</Label>
                <Textarea value={evalForm.degerlendirme} onChange={e => setEvalForm({...evalForm, degerlendirme: e.target.value})} placeholder="Mülakat değerlendirmesi..." rows={4} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEvalDialogOpen(false)}>İptal</Button>
            <Button onClick={handleEvalSave}>Tamamla</Button>
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
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>İptal</Button>
            <Button variant="destructive" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>Sil</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
