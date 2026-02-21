import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Building2, Plus, Pencil, Trash2, ToggleLeft, ToggleRight, RefreshCw, ChevronDown, ChevronUp, Users, Target, FileText } from 'lucide-react'

const API = 'http://***REMOVED***:8000'
const H = () => ({ 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` })

interface Company {
  id: number
  ad: string
  slug: string
  email: string | null
  telefon: string | null
  adres: string | null
  website: string | null
  aktif: number
  max_kullanici: number
  max_aday: number
  plan: string
  yetkili_adi: string | null
  yetkili_email: string | null
  yetkili_telefon: string | null
  olusturma_tarihi: string
}

interface CompanyStats {
  toplam_aday: number
  toplam_pozisyon: number
  toplam_kullanici: number
}

const PLAN_COLORS: Record<string, string> = {
  basic: 'bg-gray-100 text-gray-800',
  professional: 'bg-blue-100 text-blue-800',
  enterprise: 'bg-purple-100 text-purple-800'
}

export default function FirmaYonetimi() {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Dialog states
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  // Form state
  const [form, setForm] = useState({
    ad: '', email: '', telefon: '', adres: '', website: '',
    yetkili_adi: '', yetkili_email: '', yetkili_telefon: '',
    plan: 'basic', max_kullanici: '5', max_aday: '1000'
  })
  const [editId, setEditId] = useState<number | null>(null)

  // Expand state for stats
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [stats, setStats] = useState<CompanyStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  const loadCompanies = useCallback(() => {
    setLoading(true)
    fetch(`${API}/api/companies`, { headers: H() })
      .then(r => r.json())
      .then(d => setCompanies(d.companies || []))
      .catch(e => console.error(e))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadCompanies() }, [loadCompanies])

  const loadStats = (companyId: number) => {
    if (expandedId === companyId) {
      setExpandedId(null)
      setStats(null)
      return
    }
    setExpandedId(companyId)
    setStatsLoading(true)
    fetch(`${API}/api/companies/${companyId}/stats`, { headers: H() })
      .then(r => r.json())
      .then(d => setStats(d.stats || null))
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false))
  }

  const resetForm = () => {
    setForm({
      ad: '', email: '', telefon: '', adres: '', website: '',
      yetkili_adi: '', yetkili_email: '', yetkili_telefon: '',
      plan: 'basic', max_kullanici: '5', max_aday: '1000'
    })
    setEditId(null)
  }

  const handleCreate = () => {
    if (!form.ad.trim()) { alert('Firma adı zorunlu'); return }
    setSaving(true)
    fetch(`${API}/api/companies`, {
      method: 'POST',
      headers: H(),
      body: JSON.stringify({
        ...form,
        max_kullanici: parseInt(form.max_kullanici),
        max_aday: parseInt(form.max_aday)
      })
    })
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setCreateOpen(false)
          resetForm()
          loadCompanies()
        } else {
          alert(d.detail || 'Hata oluştu')
        }
      })
      .catch(e => alert('Hata: ' + e))
      .finally(() => setSaving(false))
  }

  const handleEdit = (c: Company) => {
    setEditId(c.id)
    setForm({
      ad: c.ad || '',
      email: c.email || '',
      telefon: c.telefon || '',
      adres: c.adres || '',
      website: c.website || '',
      yetkili_adi: c.yetkili_adi || '',
      yetkili_email: c.yetkili_email || '',
      yetkili_telefon: c.yetkili_telefon || '',
      plan: c.plan || 'basic',
      max_kullanici: String(c.max_kullanici || 5),
      max_aday: String(c.max_aday || 1000)
    })
    setEditOpen(true)
  }

  const handleUpdate = () => {
    if (!editId) return
    setSaving(true)
    fetch(`${API}/api/companies/${editId}`, {
      method: 'PUT',
      headers: H(),
      body: JSON.stringify({
        ...form,
        max_kullanici: parseInt(form.max_kullanici),
        max_aday: parseInt(form.max_aday)
      })
    })
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setEditOpen(false)
          resetForm()
          loadCompanies()
        } else {
          alert(d.detail || 'Hata oluştu')
        }
      })
      .catch(e => alert('Hata: ' + e))
      .finally(() => setSaving(false))
  }

  const handleToggleStatus = (c: Company) => {
    fetch(`${API}/api/companies/${c.id}/status`, {
      method: 'PUT',
      headers: H(),
      body: JSON.stringify({ aktif: c.aktif ? 0 : 1 })
    })
      .then(r => r.json())
      .then(d => { if (d.success) loadCompanies() })
      .catch(e => console.error(e))
  }

  const handleDelete = () => {
    if (!deleteConfirm) return
    fetch(`${API}/api/companies/${deleteConfirm}`, {
      method: 'DELETE',
      headers: H()
    })
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setDeleteConfirm(null)
          loadCompanies()
        } else {
          alert(d.detail || 'Hata oluştu')
        }
      })
      .catch(e => alert('Hata: ' + e))
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="h-8 w-8 text-primary" />
          <h1 className="text-2xl font-bold">Firma Yönetimi</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadCompanies} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Yenile
          </Button>
          <Button size="sm" onClick={() => { resetForm(); setCreateOpen(true) }}>
            <Plus className="h-4 w-4 mr-2" />
            Yeni Firma
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>Firma Adı</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Yetkili</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead>Limitler</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead className="text-right">İşlemler</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8">
                    <RefreshCw className="h-5 w-5 animate-spin inline mr-2" />
                    Yükleniyor...
                  </TableCell>
                </TableRow>
              ) : companies.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                    Henüz firma bulunmuyor
                  </TableCell>
                </TableRow>
              ) : companies.map(c => (
                <>
                  <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell onClick={() => loadStats(c.id)}>
                      {expandedId === c.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </TableCell>
                    <TableCell className="font-medium" onClick={() => loadStats(c.id)}>{c.ad}</TableCell>
                    <TableCell onClick={() => loadStats(c.id)}>{c.email || '-'}</TableCell>
                    <TableCell onClick={() => loadStats(c.id)}>
                      {c.yetkili_adi || '-'}
                      {c.yetkili_email && <div className="text-xs text-muted-foreground">{c.yetkili_email}</div>}
                    </TableCell>
                    <TableCell onClick={() => loadStats(c.id)}>
                      <Badge className={PLAN_COLORS[c.plan] || PLAN_COLORS.basic}>{c.plan}</Badge>
                    </TableCell>
                    <TableCell onClick={() => loadStats(c.id)}>
                      <div className="text-xs">
                        <span className="text-muted-foreground">Kullanici:</span> {c.max_kullanici}
                        <span className="mx-1">|</span>
                        <span className="text-muted-foreground">Aday:</span> {c.max_aday}
                      </div>
                    </TableCell>
                    <TableCell onClick={() => loadStats(c.id)}>
                      <Badge variant={c.aktif ? 'default' : 'secondary'}>
                        {c.aktif ? 'Aktif' : 'Pasif'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => handleEdit(c)} title="Düzenle">
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleToggleStatus(c)} title={c.aktif ? 'Pasif Yap' : 'Aktif Yap'}>
                          {c.aktif ? <ToggleRight className="h-4 w-4 text-green-600" /> : <ToggleLeft className="h-4 w-4 text-gray-400" />}
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteConfirm(c.id)} title="Sil">
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  {expandedId === c.id && (
                    <TableRow>
                      <TableCell colSpan={8} className="bg-muted/30 p-4">
                        {statsLoading ? (
                          <div className="text-center py-2"><RefreshCw className="h-4 w-4 animate-spin inline mr-2" />Yükleniyor...</div>
                        ) : stats ? (
                          <div className="grid grid-cols-3 gap-4">
                            <Card>
                              <CardContent className="p-4 flex items-center gap-3">
                                <FileText className="h-8 w-8 text-blue-500" />
                                <div>
                                  <div className="text-2xl font-bold">{stats.toplam_aday}</div>
                                  <div className="text-xs text-muted-foreground">Toplam Aday</div>
                                </div>
                              </CardContent>
                            </Card>
                            <Card>
                              <CardContent className="p-4 flex items-center gap-3">
                                <Target className="h-8 w-8 text-green-500" />
                                <div>
                                  <div className="text-2xl font-bold">{stats.toplam_pozisyon}</div>
                                  <div className="text-xs text-muted-foreground">Toplam Pozisyon</div>
                                </div>
                              </CardContent>
                            </Card>
                            <Card>
                              <CardContent className="p-4 flex items-center gap-3">
                                <Users className="h-8 w-8 text-purple-500" />
                                <div>
                                  <div className="text-2xl font-bold">{stats.toplam_kullanici}</div>
                                  <div className="text-xs text-muted-foreground">Toplam Kullanıcı</div>
                                </div>
                              </CardContent>
                            </Card>
                          </div>
                        ) : (
                          <div className="text-center text-muted-foreground">İstatistik yüklenemedi</div>
                        )}
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Yeni Firma Ekle</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-4">
            <div className="space-y-2">
              <Label>Firma Adı *</Label>
              <Input value={form.ad} onChange={e => setForm({...form, ad: e.target.value})} placeholder="Firma adi" />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="info@firma.com" />
            </div>
            <div className="space-y-2">
              <Label>Telefon</Label>
              <Input value={form.telefon} onChange={e => setForm({...form, telefon: e.target.value})} placeholder="+90 555 123 4567" />
            </div>
            <div className="space-y-2">
              <Label>Website</Label>
              <Input value={form.website} onChange={e => setForm({...form, website: e.target.value})} placeholder="https://firma.com" />
            </div>
            <div className="col-span-2 space-y-2">
              <Label>Adres</Label>
              <Input value={form.adres} onChange={e => setForm({...form, adres: e.target.value})} placeholder="Adres" />
            </div>
            <div className="space-y-2">
              <Label>Yetkili Adı</Label>
              <Input value={form.yetkili_adi} onChange={e => setForm({...form, yetkili_adi: e.target.value})} placeholder="Ad Soyad" />
            </div>
            <div className="space-y-2">
              <Label>Yetkili Email</Label>
              <Input value={form.yetkili_email} onChange={e => setForm({...form, yetkili_email: e.target.value})} placeholder="yetkili@firma.com" />
            </div>
            <div className="space-y-2">
              <Label>Yetkili Telefon</Label>
              <Input value={form.yetkili_telefon} onChange={e => setForm({...form, yetkili_telefon: e.target.value})} placeholder="+90 555 987 6543" />
            </div>
            <div className="space-y-2">
              <Label>Plan</Label>
              <Select value={form.plan} onValueChange={v => setForm({...form, plan: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="basic">Basic</SelectItem>
                  <SelectItem value="professional">Professional</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Max Kullanıcı</Label>
              <Input type="number" value={form.max_kullanici} onChange={e => setForm({...form, max_kullanici: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Max Aday</Label>
              <Input type="number" value={form.max_aday} onChange={e => setForm({...form, max_aday: e.target.value})} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>İptal</Button>
            <Button onClick={handleCreate} disabled={saving}>
              {saving && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
              Oluştur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Firma Düzenle</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-4">
            <div className="space-y-2">
              <Label>Firma Adı *</Label>
              <Input value={form.ad} onChange={e => setForm({...form, ad: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={form.email} onChange={e => setForm({...form, email: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Telefon</Label>
              <Input value={form.telefon} onChange={e => setForm({...form, telefon: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Website</Label>
              <Input value={form.website} onChange={e => setForm({...form, website: e.target.value})} />
            </div>
            <div className="col-span-2 space-y-2">
              <Label>Adres</Label>
              <Input value={form.adres} onChange={e => setForm({...form, adres: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Yetkili Adı</Label>
              <Input value={form.yetkili_adi} onChange={e => setForm({...form, yetkili_adi: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Yetkili Email</Label>
              <Input value={form.yetkili_email} onChange={e => setForm({...form, yetkili_email: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Yetkili Telefon</Label>
              <Input value={form.yetkili_telefon} onChange={e => setForm({...form, yetkili_telefon: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Plan</Label>
              <Select value={form.plan} onValueChange={v => setForm({...form, plan: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="basic">Basic</SelectItem>
                  <SelectItem value="professional">Professional</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Max Kullanıcı</Label>
              <Input type="number" value={form.max_kullanici} onChange={e => setForm({...form, max_kullanici: e.target.value})} />
            </div>
            <div className="space-y-2">
              <Label>Max Aday</Label>
              <Input type="number" value={form.max_aday} onChange={e => setForm({...form, max_aday: e.target.value})} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>İptal</Button>
            <Button onClick={handleUpdate} disabled={saving}>
              {saving && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Firma Sil</DialogTitle>
          </DialogHeader>
          <p>Bu firmayi silmek istediginizden emin misiniz? Bu islem geri alınamaz.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>İptal</Button>
            <Button variant="destructive" onClick={handleDelete}>Sil</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
