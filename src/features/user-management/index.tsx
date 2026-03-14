import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Users, UserPlus, Shield, UserX, RefreshCw, Pencil, Trash2, ToggleLeft, KeyRound } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || ""

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

interface UserItem {
  id: number
  email: string
  ad_soyad: string
  rol: string
  aktif: number
  son_giris: string | null
  olusturma_tarihi: string
  created_by_name: string | null
}

interface UserStats {
  toplam: number
  aktif: number
  pasif: number
  admin_sayisi: number
}

export default function UserManagement() {
  const [users, setUsers] = useState<UserItem[]>([])
  const [stats, setStats] = useState<UserStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editUser, setEditUser] = useState<UserItem | null>(null)
  const [newEmail, setNewEmail] = useState('')
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState('user')
  const [editName, setEditName] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editRole, setEditRole] = useState('')
  const [tempPassword, setTempPassword] = useState('')
  const [message, setMessage] = useState('')

  const loadUsers = useCallback(() => {
    fetch(`${API_URL}/api/users`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setUsers(res.data.users)
          setStats(res.data.stats)
        }
      })
      .catch(err => console.error('Users hatasi:', err))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])

  const showMsg = (msg: string) => {
    setMessage(msg)
    setTimeout(() => setMessage(''), 4000)
  }

  const handleAdd = async () => {
    if (!newEmail || !newName) return
    try {
      const res = await fetch(`${API_URL}/api/users`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ email: newEmail, ad_soyad: newName, rol: newRole })
      })
      const data = await res.json()
      if (data.success) {
        setTempPassword(data.data.temp_password)
        showMsg('Kullanıcı oluşturuldu.')
        setShowAddForm(false)
        setNewEmail('')
        setNewName('')
        setNewRole('user')
        loadUsers()
      } else {
        showMsg('Hata: ' + (data.detail || 'Bilinmeyen hata'))
      }
    } catch (err) {
      showMsg('Bağlantı hatası')
    }
  }

  const handleUpdate = async () => {
    if (!editUser) return
    const fields: Record<string, string> = {}
    if (editName && editName !== editUser.ad_soyad) fields.ad_soyad = editName
    if (editEmail && editEmail !== editUser.email) fields.email = editEmail
    if (editRole && editRole !== editUser.rol) fields.rol = editRole
    if (Object.keys(fields).length === 0) { setEditUser(null); return }

    try {
      const res = await fetch(`${API_URL}/api/users/${editUser.id}`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify(fields)
      })
      const data = await res.json()
      if (data.success) {
        showMsg('Kullanıcı güncellendi')
        setEditUser(null)
        loadUsers()
      } else {
        showMsg('Hata: ' + (data.detail || 'Bilinmeyen hata'))
      }
    } catch (err) {
      showMsg('Bağlantı hatası')
    }
  }

  const handleDelete = async (userId: number, userName: string) => {
    if (!confirm(userName + ' kullanıcısını silmek istediğinize emin misiniz?')) return
    try {
      const res = await fetch(`${API_URL}/api/users/${userId}`, {
        method: 'DELETE',
        headers: getHeaders()
      })
      const data = await res.json()
      if (data.success) {
        showMsg('Kullanıcı silindi')
        loadUsers()
      } else {
        showMsg('Hata: ' + (data.detail || 'Bilinmeyen hata'))
      }
    } catch (err) {
      showMsg('Bağlantı hatası')
    }
  }

  const handleToggle = async (userId: number) => {
    try {
      const res = await fetch(`${API_URL}/api/users/${userId}/toggle-status`, {
        method: 'POST',
        headers: getHeaders()
      })
      const data = await res.json()
      showMsg(data.message)
      loadUsers()
    } catch (err) {
      showMsg('Bağlantı hatası')
    }
  }

  const handleResetPassword = async (userId: number, userName: string) => {
    if (!confirm(userName + ' kullanıcısının şifresini sıfırlamak istiyor musunuz?')) return
    try {
      const res = await fetch(`${API_URL}/api/users/${userId}/reset-password`, {
        method: 'POST',
        headers: getHeaders()
      })
      const data = await res.json()
      if (data.success) {
        setTempPassword(data.data.temp_password)
        showMsg('Şifre sıfırlandı.')
      } else {
        showMsg('Hata: ' + (data.detail || 'Bilinmeyen hata'))
      }
    } catch (err) {
      showMsg('Bağlantı hatası')
    }
  }

  const startEdit = (user: UserItem) => {
    setEditUser(user)
    setEditName(user.ad_soyad)
    setEditEmail(user.email)
    setEditRole(user.rol)
  }

  if (loading) {
    return (
      <div className='flex items-center justify-center h-64'>
        <RefreshCw className='h-8 w-8 animate-spin text-muted-foreground' />
      </div>
    )
  }

  return (
    <div className='space-y-6'>
      <div className='flex items-center justify-between'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>Kullanıcı Yönetimi</h2>
          <p className='text-muted-foreground'>Firma kullanıcılarını yönetin</p>
        </div>
        <Button onClick={() => setShowAddForm(!showAddForm)}>
          <UserPlus className='mr-2 h-4 w-4' />
          Yeni Kullanıcı
        </Button>
      </div>

      {message && (
        <div className='rounded-md bg-blue-50 p-4 text-sm text-blue-800 border border-blue-200'>
          {message}
        </div>
      )}

      {tempPassword && (
        <div className='rounded-md bg-yellow-50 p-4 text-sm text-yellow-800 border border-yellow-200'>
          <strong>Geçici Şifre:</strong> {tempPassword}
          <span className='ml-2 text-xs'>(Bu şifreyi not edin, tekrar gösterilmeyecek)</span>
          <Button variant='ghost' size='sm' className='ml-4' onClick={() => setTempPassword('')}>Kapat</Button>
        </div>
      )}

      <div className='grid gap-4 md:grid-cols-4'>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Toplam Kullanıcı</CardTitle>
            <Users className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{stats?.toplam ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Aktif</CardTitle>
            <Users className='h-4 w-4 text-green-500' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold text-green-600'>{stats?.aktif ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Pasif</CardTitle>
            <UserX className='h-4 w-4 text-red-500' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold text-red-600'>{stats?.pasif ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Admin Sayısı</CardTitle>
            <Shield className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{stats?.admin_sayisi ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Yeni Kullanıcı Ekle</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='flex gap-4 items-end flex-wrap'>
              <div className='space-y-1'>
                <label className='text-sm font-medium'>Ad Soyad</label>
                <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder='Ad Soyad' />
              </div>
              <div className='space-y-1'>
                <label className='text-sm font-medium'>Email</label>
                <Input value={newEmail} onChange={e => setNewEmail(e.target.value)} placeholder='email@firma.com' />
              </div>
              <div className='space-y-1'>
                <label className='text-sm font-medium'>Rol</label>
                <Select value={newRole} onValueChange={setNewRole}>
                  <SelectTrigger className='w-[180px]'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='user'>Kullanıcı</SelectItem>
                    <SelectItem value='company_admin'>Firma Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleAdd}>Ekle</Button>
              <Button variant='outline' onClick={() => setShowAddForm(false)}>İptal</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {editUser && (
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Kullanıcı Düzenle: {editUser.ad_soyad}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='flex gap-4 items-end flex-wrap'>
              <div className='space-y-1'>
                <label className='text-sm font-medium'>Ad Soyad</label>
                <Input value={editName} onChange={e => setEditName(e.target.value)} />
              </div>
              <div className='space-y-1'>
                <label className='text-sm font-medium'>Email</label>
                <Input value={editEmail} onChange={e => setEditEmail(e.target.value)} />
              </div>
              <div className='space-y-1'>
                <label className='text-sm font-medium'>Rol</label>
                <Select value={editRole} onValueChange={setEditRole}>
                  <SelectTrigger className='w-[180px]'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='user'>Kullanıcı</SelectItem>
                    <SelectItem value='company_admin'>Firma Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleUpdate}>Kaydet</Button>
              <Button variant='outline' onClick={() => setEditUser(null)}>İptal</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className='text-base'>Kullanıcı Listesi</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ad Soyad</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Son Giriş</TableHead>
                <TableHead className='text-right'>İşlemler</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map(user => (
                <TableRow key={user.id}>
                  <TableCell className='font-medium'>{user.ad_soyad}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Badge variant={user.rol === 'company_admin' ? 'default' : 'secondary'}>
                      {user.rol === 'company_admin' ? 'Admin' : user.rol === 'super_admin' ? 'Super Admin' : 'Kullanıcı'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.aktif ? 'default' : 'destructive'}>
                      {user.aktif ? 'Aktif' : 'Pasif'}
                    </Badge>
                  </TableCell>
                  <TableCell className='text-sm text-muted-foreground'>
                    {user.son_giris ? new Date(user.son_giris).toLocaleDateString('tr-TR') : 'Hiç giriş yok'}
                  </TableCell>
                  <TableCell className='text-right'>
                    <div className='flex justify-end gap-1'>
                      <Button variant='ghost' size='sm' onClick={() => startEdit(user)} title='Düzenle'>
                        <Pencil className='h-4 w-4' />
                      </Button>
                      <Button variant='ghost' size='sm' onClick={() => handleToggle(user.id)} title={user.aktif ? 'Pasif Yap' : 'Aktif Yap'}>
                        <ToggleLeft className='h-4 w-4' />
                      </Button>
                      <Button variant='ghost' size='sm' onClick={() => handleResetPassword(user.id, user.ad_soyad)} title='Şifre Sıfırla'>
                        <KeyRound className='h-4 w-4' />
                      </Button>
                      <Button variant='ghost' size='sm' onClick={() => handleDelete(user.id, user.ad_soyad)} title='Sil'>
                        <Trash2 className='h-4 w-4 text-red-500' />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
