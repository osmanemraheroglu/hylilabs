import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RefreshCw, Search, Users, ChevronLeft, ChevronRight, Eye, X, Download } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from 'sonner'

const API_URL = 'http://***REMOVED***:8000'

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

interface CandidateItem {
  id: number
  ad_soyad: string
  email: string
  telefon: string | null
  lokasyon: string | null
  egitim: string | null
  universite: string | null
  bolum: string | null
  toplam_deneyim_yil: number | null
  mevcut_pozisyon: string | null
  mevcut_sirket: string | null
  teknik_beceriler: string | null
  diller: string | null
  sertifikalar: string | null
  havuz: string
  durum: string
  olusturma_tarihi: string | null
}

export default function Candidates() {
  const [candidates, setCandidates] = useState<CandidateItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [arama, setArama] = useState('')
  const [durum, setDurum] = useState('all')
  const [havuz, setHavuz] = useState('all')
  const [offset, setOffset] = useState(0)
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateItem | null>(null)
  const [detailData, setDetailData] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const limit = 20

  const { auth } = useAuthStore()
  
  const userRole = auth.user?.role?.[0] || 'user'
  const canDownload = userRole === 'super_admin' || userRole === 'company_admin'

  const loadCandidates = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams()
    params.append('limit', String(limit))
    params.append('offset', String(offset))
    if (arama) params.append('arama', arama)
    if (durum !== 'all') params.append('durum', durum)
    if (havuz !== 'all') params.append('havuz', havuz)

    fetch(`${API_URL}/api/candidates?${params}`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setCandidates(res.data.candidates)
          setTotal(res.data.total)
        }
      })
      .catch(err => console.error('Candidates hatasi:', err))
      .finally(() => setLoading(false))
  }, [offset, arama, durum, havuz])

  useEffect(() => { loadCandidates() }, [loadCandidates])

  const handleSearch = () => { setOffset(0); loadCandidates() }

  const handleDownloadCVs = async () => {
    setDownloading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`${API_URL}/api/candidates/export/download-cvs${havuz !== 'all' ? '?havuz=' + havuz : '?all=true'}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Indirme hatasi')
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'cvler.zip'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      toast.success('CV dosyalari indirildi')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Bilinmeyen hata'
      toast.error(message)
    } finally {
      setDownloading(false)
    }
  }

  const loadDetail = (candidate: CandidateItem) => {
    setSelectedCandidate(candidate)
    setDetailLoading(true)
    setDetailData(null)
    fetch(`${API_URL}/api/candidates/${candidate.id}`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) setDetailData(res.data.candidate || res.data)
      })
      .catch(err => console.error('Detail hatasi:', err))
      .finally(() => setDetailLoading(false))
  }

  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  const durumLabel = (d: string) => {
    const map: Record<string, string> = { yeni: 'Yeni', degerlendirmede: 'Degerlendirmede', mulakat: 'Mulakat', kabul: 'Kabul', red: 'Red', arsiv: 'Arsiv' }
    return map[d] || d
  }

  const durumVariant = (d: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    if (d === 'kabul') return 'default'
    if (d === 'red' || d === 'arsiv') return 'destructive'
    if (d === 'mulakat') return 'outline'
    return 'secondary'
  }

  return (
    <div className='space-y-6'>
      <div className='flex items-center justify-between'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>Adaylar</h2>
          <p className='text-muted-foreground'>Toplam {total} aday</p>
        </div>
        <div className='flex items-center gap-3'>
          {canDownload && (
            <Button 
              variant='outline' 
              size='sm' 
              onClick={handleDownloadCVs} 
              disabled={downloading || total === 0}
            >
              {downloading ? (
                <RefreshCw className='h-4 w-4 mr-2 animate-spin' />
              ) : (
                <Download className='h-4 w-4 mr-2' />
              )}
              CV Indir
            </Button>
          )}
          <div className='flex items-center gap-2'>
            <Users className='h-5 w-5 text-muted-foreground' />
            <span className='text-lg font-semibold'>{total}</span>
          </div>
        </div>
      </div>

      <Card>
        <CardContent className='pt-6'>
          <div className='flex gap-3 flex-wrap items-end'>
            <div className='flex-1 min-w-[200px]'>
              <Input
                placeholder='Ad, email veya pozisyon ara...'
                value={arama}
                onChange={e => setArama(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <Select value={durum} onValueChange={v => { setDurum(v); setOffset(0) }}>
              <SelectTrigger className='w-[160px]'>
                <SelectValue placeholder='Durum' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>Tum Durumlar</SelectItem>
                <SelectItem value='yeni'>Yeni</SelectItem>
                <SelectItem value='degerlendirmede'>Degerlendirmede</SelectItem>
                <SelectItem value='mulakat'>Mulakat</SelectItem>
                <SelectItem value='kabul'>Kabul</SelectItem>
                <SelectItem value='red'>Red</SelectItem>
                <SelectItem value='arsiv'>Arsiv</SelectItem>
              </SelectContent>
            </Select>
            <Select value={havuz} onValueChange={v => { setHavuz(v); setOffset(0) }}>
              <SelectTrigger className='w-[160px]'>
                <SelectValue placeholder='Havuz' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>Tum Havuzlar</SelectItem>
                <SelectItem value='genel_havuz'>Genel Havuz</SelectItem>
                <SelectItem value='departman_havuzu'>Departman</SelectItem>
                <SelectItem value='pozisyon_havuzu'>Pozisyon</SelectItem>
                <SelectItem value='arsiv'>Arsiv</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleSearch} variant='outline'>
              <Search className='h-4 w-4' />
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className='pt-6'>
          {loading ? (
            <div className='flex items-center justify-center h-32'>
              <RefreshCw className='h-6 w-6 animate-spin text-muted-foreground' />
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Ad Soyad</TableHead>
                    <TableHead>Pozisyon</TableHead>
                    <TableHead>Lokasyon</TableHead>
                    <TableHead>Deneyim</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead>Tarih</TableHead>
                    <TableHead className='text-right'>Detay</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {candidates.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className='text-center text-muted-foreground py-8'>
                        Aday bulunamadi
                      </TableCell>
                    </TableRow>
                  ) : (
                    candidates.map(c => (
                      <TableRow key={c.id} className='cursor-pointer hover:bg-muted/50' onClick={() => loadDetail(c)}>
                        <TableCell>
                          <div className='font-medium'>{c.ad_soyad}</div>
                          <div className='text-xs text-muted-foreground'>{c.email}</div>
                        </TableCell>
                        <TableCell className='text-sm'>{c.mevcut_pozisyon || '-'}</TableCell>
                        <TableCell className='text-sm'>{c.lokasyon || '-'}</TableCell>
                        <TableCell className='text-sm'>{c.toplam_deneyim_yil ? c.toplam_deneyim_yil + ' yil' : '-'}</TableCell>
                        <TableCell>
                          <Badge variant={durumVariant(c.durum)}>{durumLabel(c.durum)}</Badge>
                        </TableCell>
                        <TableCell className='text-sm text-muted-foreground'>
                          {c.olusturma_tarihi ? new Date(c.olusturma_tarihi).toLocaleDateString('tr-TR') : '-'}
                        </TableCell>
                        <TableCell className='text-right'>
                          <Button variant='ghost' size='sm' onClick={e => { e.stopPropagation(); loadDetail(c) }}>
                            <Eye className='h-4 w-4' />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              {totalPages > 1 && (
                <div className='flex items-center justify-between mt-4'>
                  <p className='text-sm text-muted-foreground'>
                    {offset + 1}-{Math.min(offset + limit, total)} / {total} aday
                  </p>
                  <div className='flex items-center gap-2'>
                    <Button variant='outline' size='sm' disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
                      <ChevronLeft className='h-4 w-4' />
                    </Button>
                    <span className='text-sm'>{currentPage} / {totalPages}</span>
                    <Button variant='outline' size='sm' disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>
                      <ChevronRight className='h-4 w-4' />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {selectedCandidate && (
        <div className='fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4' onClick={() => setSelectedCandidate(null)}>
          <div className='bg-background rounded-lg shadow-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6' onClick={e => e.stopPropagation()}>
            <div className='flex items-center justify-between mb-4'>
              <h3 className='text-lg font-bold'>{selectedCandidate.ad_soyad}</h3>
              <Button variant='ghost' size='sm' onClick={() => setSelectedCandidate(null)}>
                <X className='h-4 w-4' />
              </Button>
            </div>

            {detailLoading ? (
              <div className='flex items-center justify-center h-32'>
                <RefreshCw className='h-6 w-6 animate-spin text-muted-foreground' />
              </div>
            ) : detailData ? (
              <div className='space-y-4'>
                <div className='grid gap-3 md:grid-cols-2'>
                  <div><span className='text-sm text-muted-foreground'>Email:</span> <span className='font-medium'>{String(detailData.email || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Telefon:</span> <span className='font-medium'>{String(detailData.telefon || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Lokasyon:</span> <span className='font-medium'>{String(detailData.lokasyon || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Deneyim:</span> <span className='font-medium'>{detailData.toplam_deneyim_yil ? detailData.toplam_deneyim_yil + ' yil' : '-'}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Pozisyon:</span> <span className='font-medium'>{String(detailData.mevcut_pozisyon || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Sirket:</span> <span className='font-medium'>{String(detailData.mevcut_sirket || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Egitim:</span> <span className='font-medium'>{String(detailData.egitim || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Universite:</span> <span className='font-medium'>{String(detailData.universite || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Bolum:</span> <span className='font-medium'>{String(detailData.bolum || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Durum:</span> <Badge variant={durumVariant(String(detailData.durum || 'yeni'))}>{durumLabel(String(detailData.durum || 'yeni'))}</Badge></div>
                </div>

                {detailData.teknik_beceriler ? (
                  <div>
                    <p className='text-sm text-muted-foreground mb-1'>Teknik Beceriler:</p>
                    <p className='text-sm'>{String(detailData.teknik_beceriler)}</p>
                  </div>
                ) : null}

                {detailData.diller ? (
                  <div>
                    <p className='text-sm text-muted-foreground mb-1'>Diller:</p>
                    <p className='text-sm'>{String(detailData.diller)}</p>
                  </div>
                ) : null}

                {detailData.sertifikalar ? (
                  <div>
                    <p className='text-sm text-muted-foreground mb-1'>Sertifikalar:</p>
                    <p className='text-sm'>{String(detailData.sertifikalar)}</p>
                  </div>
                ) : null}

                {detailData.deneyim_detay ? (
                  <div>
                    <p className='text-sm text-muted-foreground mb-1'>Deneyim Detay:</p>
                    <p className='text-sm whitespace-pre-wrap'>{String(detailData.deneyim_detay)}</p>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className='text-center text-muted-foreground'>Veri yuklenemedi</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
