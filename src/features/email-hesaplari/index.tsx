import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import {
  Mail, Plus, Edit, Trash2, RefreshCw, Wifi, WifiOff,
  Eye, EyeOff, Star, Server, Shield
} from 'lucide-react'

const API_URL = 'http://***REMOVED***:8000'

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

interface EmailAccount {
  id: number
  ad: string
  saglayici: string
  email: string
  sifre: string
  imap_server: string
  imap_port: number
  smtp_server: string
  smtp_port: number
  sender_name: string | null
  aktif: number
  varsayilan_okuma: number
  varsayilan_gonderim: number
  son_kontrol: string | null
  toplam_cv: number
  olusturma_tarihi: string | null
}

const PROVIDERS: Record<string, { imap: string; smtp: string; imap_port: number; smtp_port: number }> = {
  gmail: { imap: 'imap.gmail.com', smtp: 'smtp.gmail.com', imap_port: 993, smtp_port: 587 },
  outlook: { imap: 'outlook.office365.com', smtp: 'smtp.office365.com', imap_port: 993, smtp_port: 587 },
  yandex: { imap: 'imap.yandex.com', smtp: 'smtp.yandex.com', imap_port: 993, smtp_port: 465 },
  custom: { imap: '', smtp: '', imap_port: 993, smtp_port: 587 },
}

const PROVIDER_LABELS: Record<string, string> = {
  gmail: 'Gmail',
  outlook: 'Outlook / Office 365',
  yandex: 'Yandex',
  custom: 'Özel (Manuel)',
}

export default function EmailHesaplari() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ id: number; success: boolean; message: string } | null>(null)
  const [showPassword, setShowPassword] = useState(false)

  const [form, setForm] = useState({
    ad: '',
    saglayici: 'gmail',
    email: '',
    sifre: '',
    imap_server: 'imap.gmail.com',
    imap_port: '993',
    smtp_server: 'smtp.gmail.com',
    smtp_port: '587',
    sender_name: '',
  })

  const loadAccounts = useCallback(() => {
    setLoading(true)
    fetch(`${API_URL}/api/emails`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) setAccounts(res.data)
      })
      .catch(err => console.error('Email hesap hatasi:', err))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadAccounts() }, [loadAccounts])

  const resetForm = () => {
    setForm({
      ad: '', saglayici: 'gmail', email: '', sifre: '',
      imap_server: 'imap.gmail.com', imap_port: '993',
      smtp_server: 'smtp.gmail.com', smtp_port: '587', sender_name: '',
    })
    setEditingId(null)
    setShowPassword(false)
  }

  const openCreate = () => { resetForm(); setDialogOpen(true) }

  const openEdit = (acc: EmailAccount) => {
    setForm({
      ad: acc.ad,
      saglayici: acc.saglayici,
      email: acc.email,
      sifre: '',
      imap_server: acc.imap_server,
      imap_port: String(acc.imap_port),
      smtp_server: acc.smtp_server,
      smtp_port: String(acc.smtp_port),
      sender_name: acc.sender_name || '',
    })
    setEditingId(acc.id)
    setDialogOpen(true)
  }

  const handleProviderChange = (provider: string) => {
    const p = PROVIDERS[provider]
    setForm({
      ...form,
      saglayici: provider,
      imap_server: p.imap,
      smtp_server: p.smtp,
      imap_port: String(p.imap_port),
      smtp_port: String(p.smtp_port),
    })
  }

  const handleSave = () => {
    if (!form.ad || !form.email || !form.imap_server || !form.smtp_server) return
    if (!editingId && !form.sifre) return

    const payload: Record<string, unknown> = {
      ad: form.ad,
      saglayici: form.saglayici,
      email: form.email,
      imap_server: form.imap_server,
      imap_port: Number(form.imap_port),
      smtp_server: form.smtp_server,
      smtp_port: Number(form.smtp_port),
      sender_name: form.sender_name || null,
    }

    if (form.sifre) payload.sifre = form.sifre

    const url = editingId ? `${API_URL}/api/emails/${editingId}` : `${API_URL}/api/emails`
    const method = editingId ? 'PUT' : 'POST'

    fetch(url, { method, headers: getHeaders(), body: JSON.stringify(payload) })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setDialogOpen(false); resetForm(); loadAccounts() }
        else toast.error(res.detail || 'Hata oluştu')
      })
      .catch(err => console.error('Save hatasi:', err))
  }

  const handleDelete = (id: number) => {
    fetch(`${API_URL}/api/emails/${id}`, { method: 'DELETE', headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setDeleteConfirm(null); loadAccounts() }
      })
      .catch(err => console.error('Delete hatasi:', err))
  }

  const handleTest = (id: number) => {
    setTestingId(id)
    setTestResult(null)
    fetch(`${API_URL}/api/emails/${id}/test`, { method: 'POST', headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        setTestResult({ id, success: res.success, message: res.message })
      })
      .catch(err => {
        setTestResult({ id, success: false, message: String(err) })
      })
      .finally(() => setTestingId(null))
  }

  const handleToggleAktif = (acc: EmailAccount) => {
    const newAktif = acc.aktif ? 0 : 1
    fetch(`${API_URL}/api/emails/${acc.id}`, {
      method: 'PUT', headers: getHeaders(),
      body: JSON.stringify({ aktif: newAktif })
    })
      .then(r => r.json())
      .then(res => { if (res.success) loadAccounts() })
      .catch(err => console.error('Toggle hatasi:', err))
  }

  const handleSetDefault = (id: number, type: 'reading' | 'sending') => {
    fetch(`${API_URL}/api/emails/${id}/default`, {
      method: 'PUT', headers: getHeaders(),
      body: JSON.stringify(type === 'reading' ? { for_reading: true } : { for_sending: true })
    })
      .then(r => r.json())
      .then(res => { if (res.success) loadAccounts() })
      .catch(err => console.error('Default hatasi:', err))
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Email Hesapları</h2>
          <p className="text-muted-foreground text-sm">CV toplama ve iletişim için email hesaplarını yönetin</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadAccounts} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Yenile
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 mr-1" /> Yeni Hesap
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold">{accounts.length}</div><div className="text-xs text-muted-foreground">Toplam Hesap</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-green-600">{accounts.filter(a => a.aktif).length}</div><div className="text-xs text-muted-foreground">Aktif</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-blue-600">{accounts.reduce((s, a) => s + a.toplam_cv, 0)}</div><div className="text-xs text-muted-foreground">Toplam CV</div></CardContent></Card>
      </div>

      {/* Account Cards */}
      {accounts.length === 0 && !loading ? (
        <Card><CardContent className="p-8 text-center text-muted-foreground">Henüz email hesabı eklenmemiş. "Yeni Hesap" butonuna tıklayın.</CardContent></Card>
      ) : (
        <div className="grid gap-3">
          {accounts.map(acc => (
            <Card key={acc.id} className={`${!acc.aktif ? 'opacity-60' : ''}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                      <Mail className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        {acc.ad}
                        {acc.varsayilan_okuma ? <Badge variant="outline" className="text-[10px]"><Star className="h-2.5 w-2.5 mr-0.5 fill-yellow-400 text-yellow-400" />Okuma</Badge> : null}
                        {acc.varsayilan_gonderim ? <Badge variant="outline" className="text-[10px]"><Star className="h-2.5 w-2.5 mr-0.5 fill-green-400 text-green-400" />Gönderim</Badge> : null}
                      </div>
                      <div className="text-sm text-muted-foreground">{acc.email}</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                        <Badge variant="secondary" className="text-[10px]">{PROVIDER_LABELS[acc.saglayici] || acc.saglayici}</Badge>
                        <span className="flex items-center gap-0.5"><Server className="h-3 w-3" />{acc.imap_server}:{acc.imap_port}</span>
                        <span>CV: {acc.toplam_cv}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {testResult && testResult.id === acc.id && (
                      <Badge className={`text-xs ${testResult.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {testResult.success ? <Wifi className="h-3 w-3 mr-1" /> : <WifiOff className="h-3 w-3 mr-1" />}
                        {testResult.message.substring(0, 40)}
                      </Badge>
                    )}
                    <Button variant="outline" size="sm" onClick={() => handleTest(acc.id)} disabled={testingId === acc.id}>
                      {testingId === acc.id ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
                    </Button>
                    <div className="flex flex-col gap-0.5">
                      <button onClick={() => handleSetDefault(acc.id, 'reading')} className="text-[10px] text-muted-foreground hover:text-blue-600" title="Varsayılan okuma">
                        <Shield className="h-3 w-3 inline mr-0.5" />O
                      </button>
                      <button onClick={() => handleSetDefault(acc.id, 'sending')} className="text-[10px] text-muted-foreground hover:text-green-600" title="Varsayılan gönderim">
                        <Shield className="h-3 w-3 inline mr-0.5" />G
                      </button>
                    </div>
                    <Switch checked={!!acc.aktif} onCheckedChange={() => handleToggleAktif(acc)} />
                    <Button variant="ghost" size="sm" onClick={() => openEdit(acc)}><Edit className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeleteConfirm(acc.id)} className="text-red-500 hover:text-red-700"><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={o => { if (!o) { setDialogOpen(false); resetForm() } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingId ? 'Email Hesabı Düzenle' : 'Yeni Email Hesabı'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-sm">Hesap Adı *</Label>
              <Input value={form.ad} onChange={e => setForm({...form, ad: e.target.value})} placeholder="Örnek: İK Gmail" />
            </div>
            <div>
              <Label className="text-sm">Sağlayıcı *</Label>
              <Select value={form.saglayici} onValueChange={handleProviderChange}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(PROVIDER_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm">Email Adresi *</Label>
                <Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="ornek@gmail.com" />
              </div>
              <div>
                <Label className="text-sm">{editingId ? 'Şifre (boş bırakırsanız değişmez)' : 'Şifre *'}</Label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={form.sifre}
                    onChange={e => setForm({...form, sifre: e.target.value})}
                    placeholder={editingId ? '****' : 'Uygulama şifresi'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </div>
            <div>
              <Label className="text-sm">Gönderici Adı</Label>
              <Input value={form.sender_name} onChange={e => setForm({...form, sender_name: e.target.value})} placeholder="Şirket İK" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm">IMAP Sunucu</Label>
                <Input value={form.imap_server} onChange={e => setForm({...form, imap_server: e.target.value})} disabled={form.saglayici !== 'custom'} />
              </div>
              <div>
                <Label className="text-sm">IMAP Port</Label>
                <Input value={form.imap_port} onChange={e => setForm({...form, imap_port: e.target.value})} disabled={form.saglayici !== 'custom'} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm">SMTP Sunucu</Label>
                <Input value={form.smtp_server} onChange={e => setForm({...form, smtp_server: e.target.value})} disabled={form.saglayici !== 'custom'} />
              </div>
              <div>
                <Label className="text-sm">SMTP Port</Label>
                <Input value={form.smtp_port} onChange={e => setForm({...form, smtp_port: e.target.value})} disabled={form.saglayici !== 'custom'} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDialogOpen(false); resetForm() }}>İptal</Button>
            <Button onClick={handleSave} disabled={!form.ad || !form.email || !form.imap_server || !form.smtp_server || (!editingId && !form.sifre)}>Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <Dialog open={deleteConfirm !== null} onOpenChange={o => { if (!o) setDeleteConfirm(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Email Hesabı Sil</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Bu email hesabini silmek istediğinizden emin misiniz? Bu islem geri alınamaz.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>İptal</Button>
            <Button variant="destructive" onClick={() => deleteConfirm && handleDelete(deleteConfirm)}>Sil</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
