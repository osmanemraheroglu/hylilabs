import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Settings, Building2, Users, FileText, Target, RefreshCw, ToggleLeft, ToggleRight, Search } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || ""
const H = () => ({ 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` })

interface SystemStats {
  toplam_firma: number
  aktif_firma: number
  askida_firma: number
  toplam_kullanici: number
  toplam_cv: number
  toplam_pozisyon: number
  son_30_gun_cv: number
}

interface CompanyStat {
  company_id: number
  company_name: string
  plan: string
  aktif: number
  cv_count: number
  position_count: number
  user_count: number
  last_cv_date: string | null
}

interface UserItem {
  id: number
  email: string
  ad_soyad: string
  rol: string
  aktif: number
  company_id: number | null
  firma_adi: string | null
  son_giris: string | null
  olusturma_tarihi: string
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Sistem Yöneticisi',
  company_admin: 'Firma Yöneticisi',
  user: 'Kullanıcı'
}

const ROLE_COLORS: Record<string, string> = {
  super_admin: 'bg-red-100 text-red-800',
  company_admin: 'bg-blue-100 text-blue-800',
  user: 'bg-gray-100 text-gray-800'
}

export default function AdminPanel() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [companyStats, setCompanyStats] = useState<CompanyStat[]>([])
  const [users, setUsers] = useState<UserItem[]>([])
  const [loading, setLoading] = useState(true)
  const [usersLoading, setUsersLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const loadStats = useCallback(() => {
    setLoading(true)
    Promise.all([
      fetch(`${API}/api/admin/stats`, { headers: H() }).then(r => r.json()),
      fetch(`${API}/api/admin/company-stats`, { headers: H() }).then(r => r.json())
    ])
      .then(([statsRes, companyRes]) => {
        setStats(statsRes.stats || null)
        setCompanyStats(companyRes.stats || [])
      })
      .catch(e => console.error(e))
      .finally(() => setLoading(false))
  }, [])

  const loadUsers = useCallback(() => {
    setUsersLoading(true)
    fetch(`${API}/api/admin/users`, { headers: H() })
      .then(r => r.json())
      .then(d => setUsers(d.users || []))
      .catch(e => console.error(e))
      .finally(() => setUsersLoading(false))
  }, [])

  useEffect(() => {
    loadStats()
    loadUsers()
  }, [loadStats, loadUsers])

  const handleToggleUserStatus = (user: UserItem) => {
    if (user.rol === 'super_admin') return
    fetch(`${API}/api/admin/users/${user.id}/status`, {
      method: 'PUT',
      headers: H(),
      body: JSON.stringify({ aktif: user.aktif ? 0 : 1 })
    })
      .then(r => r.json())
      .then(d => { if (d.success) loadUsers() })
      .catch(e => console.error(e))
  }

  const handleChangeRole = (userId: number, newRole: string) => {
    fetch(`${API}/api/admin/users/${userId}/role`, {
      method: 'PUT',
      headers: H(),
      body: JSON.stringify({ rol: newRole })
    })
      .then(r => r.json())
      .then(d => { if (d.success) loadUsers() })
      .catch(e => console.error(e))
  }

  const filteredUsers = users.filter(u => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (u.email || '').toLowerCase().includes(q) ||
           (u.ad_soyad || '').toLowerCase().includes(q) ||
           (u.firma_adi || '').toLowerCase().includes(q)
  })

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Settings className="h-8 w-8 text-primary" />
        <h1 className="text-2xl font-bold">Admin Panel</h1>
      </div>

      <Tabs defaultValue="stats">
        <TabsList>
          <TabsTrigger value="stats">İstatistikler</TabsTrigger>
          <TabsTrigger value="users">Tum Kullanıcılar</TabsTrigger>
        </TabsList>

        <TabsContent value="stats" className="space-y-6 mt-4">
          {loading ? (
            <div className="text-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin inline mr-2" />
              Yükleniyor...
            </div>
          ) : (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-4 gap-4">
                <Card>
                  <CardContent className="p-4 flex items-center gap-3">
                    <Building2 className="h-10 w-10 text-blue-500" />
                    <div>
                      <div className="text-3xl font-bold">{stats?.toplam_firma || 0}</div>
                      <div className="text-sm text-muted-foreground">Toplam Firma</div>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 flex items-center gap-3">
                    <Users className="h-10 w-10 text-green-500" />
                    <div>
                      <div className="text-3xl font-bold">{stats?.toplam_kullanici || 0}</div>
                      <div className="text-sm text-muted-foreground">Toplam Kullanıcı</div>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 flex items-center gap-3">
                    <FileText className="h-10 w-10 text-purple-500" />
                    <div>
                      <div className="text-3xl font-bold">{stats?.toplam_cv || 0}</div>
                      <div className="text-sm text-muted-foreground">Toplam Aday</div>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 flex items-center gap-3">
                    <Target className="h-10 w-10 text-orange-500" />
                    <div>
                      <div className="text-3xl font-bold">{stats?.toplam_pozisyon || 0}</div>
                      <div className="text-sm text-muted-foreground">Toplam Pozisyon</div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Additional Stats */}
              <div className="grid grid-cols-3 gap-4">
                <Card>
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{stats?.aktif_firma || 0}</div>
                    <div className="text-sm text-muted-foreground">Aktif Firma</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-yellow-600">{stats?.askida_firma || 0}</div>
                    <div className="text-sm text-muted-foreground">Askıda Firma</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-blue-600">{stats?.son_30_gun_cv || 0}</div>
                    <div className="text-sm text-muted-foreground">Son 30 Gün CV</div>
                  </CardContent>
                </Card>
              </div>

              {/* Company Stats Table */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Firma Bazli İstatistikler</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Firma</TableHead>
                        <TableHead>Plan</TableHead>
                        <TableHead>Durum</TableHead>
                        <TableHead className="text-right">Aday</TableHead>
                        <TableHead className="text-right">Pozisyon</TableHead>
                        <TableHead className="text-right">Kullanıcı</TableHead>
                        <TableHead>Son CV</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {companyStats.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-4 text-muted-foreground">
                            Firma bulunamadı
                          </TableCell>
                        </TableRow>
                      ) : companyStats.map(cs => (
                        <TableRow key={cs.company_id}>
                          <TableCell className="font-medium">{cs.company_name}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{cs.plan}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={cs.aktif ? 'default' : 'secondary'}>
                              {cs.aktif ? 'Aktif' : 'Pasif'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">{cs.cv_count}</TableCell>
                          <TableCell className="text-right">{cs.position_count}</TableCell>
                          <TableCell className="text-right">{cs.user_count}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {cs.last_cv_date ? cs.last_cv_date.split(' ')[0] : '-'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="users" className="space-y-4 mt-4">
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Email, isim veya firma ara..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button variant="outline" size="sm" onClick={loadUsers} disabled={usersLoading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${usersLoading ? 'animate-spin' : ''}`} />
              Yenile
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Ad Soyad</TableHead>
                    <TableHead>Firma</TableHead>
                    <TableHead>Rol</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead>Son Giriş</TableHead>
                    <TableHead className="text-right">İşlemler</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usersLoading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8">
                        <RefreshCw className="h-5 w-5 animate-spin inline mr-2" />
                        Yükleniyor...
                      </TableCell>
                    </TableRow>
                  ) : filteredUsers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        Kullanıcı bulunamadı
                      </TableCell>
                    </TableRow>
                  ) : filteredUsers.map(u => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.email}</TableCell>
                      <TableCell>{u.ad_soyad || '-'}</TableCell>
                      <TableCell>{u.firma_adi || <span className="text-muted-foreground italic">Super Admin</span>}</TableCell>
                      <TableCell>
                        <Badge className={ROLE_COLORS[u.rol] || ROLE_COLORS.user}>
                          {ROLE_LABELS[u.rol] || u.rol}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={u.aktif ? 'default' : 'secondary'}>
                          {u.aktif ? 'Aktif' : 'Pasif'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {u.son_giris ? u.son_giris.split('.')[0].replace('T', ' ') : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {u.rol !== 'super_admin' && (
                          <div className="flex justify-end gap-2">
                            <Select
                              value={u.rol}
                              onValueChange={v => handleChangeRole(u.id, v)}
                            >
                              <SelectTrigger className="w-32 h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="user">Kullanıcı</SelectItem>
                                <SelectItem value="company_admin">Firma Yöneticisi</SelectItem>
                              </SelectContent>
                            </Select>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleToggleUserStatus(u)}
                              title={u.aktif ? 'Pasif Yap' : 'Aktif Yap'}
                            >
                              {u.aktif ? (
                                <ToggleRight className="h-4 w-4 text-green-600" />
                              ) : (
                                <ToggleLeft className="h-4 w-4 text-gray-400" />
                              )}
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
