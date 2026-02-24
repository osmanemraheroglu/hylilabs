import { useEffect, useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import { Users, Briefcase, FileText, Clock, Calendar, UserCheck } from 'lucide-react'

const API_URL = 'http://***REMOVED***:8000'

function getRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (minutes < 1) return 'Az önce'
  if (minutes < 60) return `${minutes} dakika önce`
  if (hours < 24) return `${hours} saat önce`
  if (days < 30) return `${days} gün önce`
  return new Date(dateStr).toLocaleDateString('tr-TR')
}

interface DashboardStats {
  toplam_aday: number
  aktif_pozisyon: number
  bugun_basvuru: number
  bekleyen: number
  mulakat_bekleyen: number
  bu_ay_ise_alinan: number
  toplam_basvuru: number
}

interface PoolDistribution {
  distribution: Array<{
    durum: string
    label: string
    count: number
  }>
}

interface RecentActivity {
  recent_applications: Array<{
    id: number
    ad_soyad: string
    email: string
    basvuru_tarihi: string
    kaynak: string
    pozisyon: string | null
  }>
  recent_evaluations: Array<{
    id: number
    ad_soyad: string
    pozisyon: string
    durum: string
  }>
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d']

const DURUM_LABELS: Record<string, string> = {
  'yeni': 'Yeni',
  'pozisyona_atandi': 'Pozisyona Atandı',
  'mulakatta': 'Mülakata Çağrıldı',
  'arsiv': 'Arşiv',
  'reddedildi': 'Reddedildi',
  'ise_alindi': 'İşe Alındı'
}

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [poolData, setPoolData] = useState<PoolDistribution | null>(null)
  const [activities, setActivities] = useState<RecentActivity | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchDashboardData = () => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    const headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }

    Promise.all([
      fetch(`${API_URL}/api/dashboard/stats`, { headers }).then(r => r.json()),
      fetch(`${API_URL}/api/dashboard/pool-distribution`, { headers }).then(r => r.json()),
      fetch(`${API_URL}/api/dashboard/recent-activities`, { headers }).then(r => r.json())
    ])
      .then(([statsData, poolData, activitiesData]) => {
        setStats(statsData)
        setPoolData(poolData)
        setActivities(activitiesData)
        setLoading(false)
      })
      .catch(err => {
        console.error('Dashboard API error:', err)
        setLoading(false)
      })
  }

  useEffect(() => {
    fetchDashboardData()
  }, [])

  // Sayfa görünür olunca verileri yenile
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchDashboardData()
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [])

  if (loading) {
    return (
      <>
        <Header>
          <div className='ms-auto flex items-center space-x-4'>
            <ThemeSwitch />
            <ProfileDropdown />
          </div>
        </Header>
        <Main>
          <div className='flex items-center justify-center h-64'>
            <div className='text-muted-foreground'>Yükleniyor...</div>
          </div>
        </Main>
      </>
    )
  }

  const pieData = poolData?.distribution.map(item => ({
    name: DURUM_LABELS[item.durum] || item.label,
    value: item.count
  })) || []

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center space-x-4'>
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>

      <Main>
        <div className='mb-4'>
          <h1 className='text-2xl font-bold tracking-tight'>Kontrol Paneli</h1>
          <p className='text-muted-foreground'>Genel bakış ve istatistikler</p>
        </div>

        {/* Metrik Kartlari */}
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-6'>
          <Card>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>Toplam Aday</CardTitle>
              <Users className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{stats?.toplam_aday || 0}</div>
              <p className='text-xs text-muted-foreground'>Sistemdeki tüm adaylar</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>Aktif Pozisyon</CardTitle>
              <Briefcase className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{stats?.aktif_pozisyon || 0}</div>
              <p className='text-xs text-muted-foreground'>Açık pozisyon sayısı</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>Bugün Başvuru</CardTitle>
              <FileText className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{stats?.bugun_basvuru || 0}</div>
              <p className='text-xs text-muted-foreground'>Bugün gelen başvurular</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>Bekleyen</CardTitle>
              <Clock className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{stats?.bekleyen || 0}</div>
              <p className='text-xs text-muted-foreground'>Değerlendirme bekleyen</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>Mülakat Bekleyen</CardTitle>
              <Calendar className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{stats?.mulakat_bekleyen || 0}</div>
              <p className='text-xs text-muted-foreground'>Mülakat aşamasında</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
              <CardTitle className='text-sm font-medium'>Bu Ay İşe Alınan</CardTitle>
              <UserCheck className='h-4 w-4 text-muted-foreground' />
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{stats?.bu_ay_ise_alinan || 0}</div>
              <p className='text-xs text-muted-foreground'>Bu ay işe alınan adaylar</p>
            </CardContent>
          </Card>
        </div>

        {/* Alt Kisim - Grafik ve Aktiviteler */}
        <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
          {/* Havuz Dağılımı */}
          <Card>
            <CardHeader>
              <CardTitle>Aday Havuz Dağılımı</CardTitle>
              <CardDescription>Durumlara göre aday dağılımı</CardDescription>
            </CardHeader>
            <CardContent>
              {pieData.length > 0 ? (
                <ResponsiveContainer width='100%' height={300}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx='50%'
                      cy='50%'
                      labelLine={false}
                      outerRadius={100}
                      fill='#8884d8'
                      dataKey='value'
                      label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                    >
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className='flex items-center justify-center h-64 text-muted-foreground'>
                  Veri bulunamadı
                </div>
              )}
            </CardContent>
          </Card>

          {/* Son Aktiviteler */}
          <Card>
            <CardHeader>
              <CardTitle>Son Eklenen Adaylar</CardTitle>
              <CardDescription>Son eklenen adaylar</CardDescription>
            </CardHeader>
            <CardContent>
              <div className='space-y-4 max-h-[300px] overflow-y-auto'>
                {activities?.recent_applications.length ? (
                  activities.recent_applications.map((app) => (
                    <div key={app.id} className='flex items-center justify-between border-b pb-2'>
                      <div>
                        <p className='font-medium text-sm'>{app.ad_soyad}</p>
                        <p className='text-xs text-muted-foreground'>{app.email}</p>
                      </div>
                      <div className='text-right'>
                        <p className='text-xs'>{app.pozisyon || 'Genel Başvuru'}</p>
                        <p className='text-xs text-muted-foreground'>
                          <span
                            title={new Date(app.basvuru_tarihi).toLocaleString('tr-TR')}
                            style={{cursor: 'default'}}
                          >
                            {getRelativeTime(app.basvuru_tarihi)}
                          </span>
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className='text-muted-foreground text-center'>Henüz başvuru yok</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </Main>
    </>
  )
}
