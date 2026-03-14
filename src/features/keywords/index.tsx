import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { BarChart3, Tags, TrendingUp, RefreshCw, Briefcase, AlertTriangle, CheckCircle } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || ""

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}` }
}

interface OverviewData {
  total_keywords_in_use: number
  total_keywords_in_dictionary: number
  top_keywords: Array<{ keyword: string; usage_count: number; category: string }>
  category_distribution: Record<string, number>
  keywords_by_position: Record<string, number>
}

interface PositionItem {
  id: number
  title: string
}

interface PositionReportData {
  position_name: string
  total_keywords: number
  total_candidates: number
  keyword_match_rates: Array<{
    keyword: string
    matched_count: number
    total_candidates: number
    match_rate: number
  }>
  hardest_keywords: Array<{
    keyword: string
    matched_count: number
    total_candidates: number
    match_rate: number
  }>
  easiest_keywords: Array<{
    keyword: string
    matched_count: number
    total_candidates: number
    match_rate: number
  }>
}

interface MissingSkillsData {
  hardest_to_find: Array<{
    keyword: string
    positions_requiring: number
    candidates_having: number
    gap: string
  }>
  well_covered: Array<{
    keyword: string
    positions_requiring: number
    candidates_having: number
    coverage: number
  }>
}

export default function KeywordStats() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [positions, setPositions] = useState<PositionItem[]>([])
  const [positionReport, setPositionReport] = useState<PositionReportData | null>(null)
  const [missingSkills, setMissingSkills] = useState<MissingSkillsData | null>(null)
  const [selectedPosition, setSelectedPosition] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')

  const loadOverview = useCallback(() => {
    fetch(`${API_URL}/api/keywords/overview`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => { if (res.success) setOverview(res.data) })
      .catch(err => console.error('Overview hatası:', err))
      .finally(() => setLoading(false))
  }, [])

  const loadPositions = useCallback(() => {
    fetch(`${API_URL}/api/keywords/positions`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => { if (res.success) setPositions(res.data) })
      .catch(err => console.error('Positions hatası:', err))
  }, [])

  const loadPositionReport = useCallback((positionId: string) => {
    fetch(`${API_URL}/api/keywords/position-report?position_id=${positionId}`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => { if (res.success) setPositionReport(res.data) })
      .catch(err => console.error('Pozisyon raporu hatası:', err))
  }, [])

  const loadMissingSkills = useCallback(() => {
    fetch(`${API_URL}/api/keywords/missing-skills`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => { if (res.success) setMissingSkills(res.data) })
      .catch(err => console.error('Eksik beceriler hatası:', err))
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await fetch(`${API_URL}/api/keywords/sync`, { method: 'POST', headers: getHeaders() })
      loadOverview()
    } catch (err) {
      console.error('Sync hatası:', err)
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    loadOverview()
    loadPositions()
  }, [loadOverview, loadPositions])

  useEffect(() => {
    if (activeTab === 'missing-skills' && !missingSkills) loadMissingSkills()
  }, [activeTab, missingSkills, loadMissingSkills])

  useEffect(() => {
    if (selectedPosition) loadPositionReport(selectedPosition)
  }, [selectedPosition, loadPositionReport])

  if (loading) {
    return (
      <div className='flex items-center justify-center h-64'>
        <RefreshCw className='h-8 w-8 animate-spin text-muted-foreground' />
      </div>
    )
  }

  const positionEntries = overview?.keywords_by_position
    ? Object.entries(overview.keywords_by_position)
    : []

  return (
    <div className='space-y-6'>
      <div className='flex items-center justify-between'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>Keyword İstatistikleri</h2>
          <p className='text-muted-foreground'>Pozisyon keyword kullanım analizi ve eşleşme raporları</p>
        </div>
        <Button onClick={handleSync} disabled={syncing} variant='outline'>
          <RefreshCw className={`mr-2 h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? 'Güncelleniyor...' : 'Güncelle'}
        </Button>
      </div>

      <div className='grid gap-4 md:grid-cols-4'>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Kullanımdaki Keyword</CardTitle>
            <Tags className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{overview?.total_keywords_in_use ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Sözlükteki Keyword</CardTitle>
            <TrendingUp className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{overview?.total_keywords_in_dictionary ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Pozisyon Sayısı</CardTitle>
            <Briefcase className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{positions.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Kategori Sayısı</CardTitle>
            <BarChart3 className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>
              {overview?.category_distribution ? Object.keys(overview.category_distribution).length : 0}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value='overview'>Genel Bakış</TabsTrigger>
          <TabsTrigger value='position-report'>Pozisyon Bazlı</TabsTrigger>
          <TabsTrigger value='missing-skills'>Eksik Beceriler</TabsTrigger>
        </TabsList>

        <TabsContent value='overview' className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2'>
            <Card>
              <CardHeader>
                <CardTitle className='text-base'>En Çok Kullanılan Keywordler</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Kategori</TableHead>
                      <TableHead className='text-right'>Kullanım</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {overview?.top_keywords?.length ? (
                      overview.top_keywords.map((kw, i) => (
                        <TableRow key={i}>
                          <TableCell className='font-medium'>{kw.keyword}</TableCell>
                          <TableCell><Badge variant='secondary'>{kw.category}</Badge></TableCell>
                          <TableCell className='text-right'>{kw.usage_count}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={3} className='text-center text-muted-foreground'>Henüz veri yok</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className='text-base'>Kategori Dağılımı</CardTitle>
              </CardHeader>
              <CardContent>
                <div className='space-y-3'>
                  {overview?.category_distribution &&
                    Object.entries(overview.category_distribution).map(([cat, count]) => {
                      const total = Object.values(overview.category_distribution).reduce((a, b) => a + b, 0) || 1
                      const pct = Math.round((count / total) * 100)
                      return (
                        <div key={cat} className='space-y-1'>
                          <div className='flex items-center justify-between text-sm'>
                            <span>{cat}</span>
                            <span className='text-muted-foreground'>{count} ({pct}%)</span>
                          </div>
                          <Progress value={pct} className='h-2' />
                        </div>
                      )
                    })}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className='text-base'>Pozisyon Bazında Keyword Sayıları</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Pozisyon</TableHead>
                    <TableHead className='text-right'>Keyword Sayısı</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {positionEntries.map(([name, count], i) => (
                    <TableRow key={i}>
                      <TableCell className='font-medium'>{name}</TableCell>
                      <TableCell className='text-right'>{count}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value='position-report' className='space-y-4'>
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>Pozisyon Seçin</CardTitle>
              <CardDescription>Detaylı keyword eşleşme raporunu görmek için bir pozisyon seçin</CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={selectedPosition} onValueChange={setSelectedPosition}>
                <SelectTrigger className='w-full md:w-[400px]'>
                  <SelectValue placeholder='Pozisyon seçin...' />
                </SelectTrigger>
                <SelectContent>
                  {positions.map((pos) => (
                    <SelectItem key={pos.id} value={String(pos.id)}>
                      {pos.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {positionReport && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className='text-base'>
                    {positionReport.position_name} — Keyword Eşleşmeleri
                  </CardTitle>
                  <CardDescription>
                    {positionReport.total_keywords} keyword, {positionReport.total_candidates} aday
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Keyword</TableHead>
                        <TableHead className='text-right'>Eşleşen</TableHead>
                        <TableHead className='text-right'>Toplam Aday</TableHead>
                        <TableHead className='text-right'>Oran</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {positionReport.keyword_match_rates?.map((kw, i) => (
                        <TableRow key={i}>
                          <TableCell className='font-medium'>{kw.keyword}</TableCell>
                          <TableCell className='text-right'>{kw.matched_count}</TableCell>
                          <TableCell className='text-right'>{kw.total_candidates}</TableCell>
                          <TableCell className='text-right'>
                            <span className={
                              kw.match_rate >= 50 ? 'text-green-600' :
                              kw.match_rate >= 25 ? 'text-yellow-600' : 'text-red-600'
                            }>
                              %{Math.round(kw.match_rate)}
                            </span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <div className='grid gap-4 md:grid-cols-2'>
                <Card>
                  <CardHeader>
                    <CardTitle className='text-base flex items-center gap-2'>
                      <AlertTriangle className='h-4 w-4 text-red-500' />
                      En Zor Bulunan
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className='space-y-2'>
                      {positionReport.hardest_keywords?.map((kw, i) => (
                        <div key={i} className='flex items-center justify-between'>
                          <span className='text-sm'>{kw.keyword}</span>
                          <Badge variant='destructive'>%{Math.round(kw.match_rate)}</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className='text-base flex items-center gap-2'>
                      <CheckCircle className='h-4 w-4 text-green-500' />
                      En Kolay Bulunan
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className='space-y-2'>
                      {positionReport.easiest_keywords?.map((kw, i) => (
                        <div key={i} className='flex items-center justify-between'>
                          <span className='text-sm'>{kw.keyword}</span>
                          <Badge variant='secondary'>%{Math.round(kw.match_rate)}</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value='missing-skills' className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2'>
            <Card>
              <CardHeader>
                <CardTitle className='text-base flex items-center gap-2'>
                  <AlertTriangle className='h-4 w-4 text-red-500' />
                  En Zor Bulunan Beceriler
                </CardTitle>
                <CardDescription>Aday havuzunda en az bulunan keywordler</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead className='text-right'>İsteyen Poz.</TableHead>
                      <TableHead className='text-right'>Sahip Aday</TableHead>
                      <TableHead className='text-right'>Durum</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {missingSkills?.hardest_to_find?.length ? (
                      missingSkills.hardest_to_find.map((s, i) => (
                        <TableRow key={i}>
                          <TableCell className='font-medium'>{s.keyword}</TableCell>
                          <TableCell className='text-right'>{s.positions_requiring}</TableCell>
                          <TableCell className='text-right'>{s.candidates_having}</TableCell>
                          <TableCell className='text-right text-red-600'>{s.gap}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={4} className='text-center text-muted-foreground'>Henüz veri yok</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className='text-base flex items-center gap-2'>
                  <CheckCircle className='h-4 w-4 text-green-500' />
                  İyi Kapsanan Beceriler
                </CardTitle>
                <CardDescription>Aday havuzunda en çok bulunan keywordler</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead className='text-right'>İsteyen Poz.</TableHead>
                      <TableHead className='text-right'>Sahip Aday</TableHead>
                      <TableHead className='text-right'>Kapsam</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {missingSkills?.well_covered?.length ? (
                      missingSkills.well_covered.map((s, i) => (
                        <TableRow key={i}>
                          <TableCell className='font-medium'>{s.keyword}</TableCell>
                          <TableCell className='text-right'>{s.positions_requiring}</TableCell>
                          <TableCell className='text-right'>{s.candidates_having}</TableCell>
                          <TableCell className='text-right text-green-600'>%{Math.round(s.coverage)}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={4} className='text-center text-muted-foreground'>Henüz veri yok</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

