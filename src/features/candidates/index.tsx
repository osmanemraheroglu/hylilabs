import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RefreshCw, Search, Users, ChevronLeft, ChevronRight, Eye, X, Download, Archive, CheckCircle, XCircle, Ban } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from 'sonner'

const API_URL = import.meta.env.VITE_API_URL || ""

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
  const [offset, setOffset] = useState(0)
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateItem | null>(null)
  const [detailData, setDetailData] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [blacklistInfo, setBlacklistInfo] = useState<{reason?: string; blacklisted_by_name?: string; blacklisted_at?: string} | null>(null)
  const [removeBlacklistDialogOpen, setRemoveBlacklistDialogOpen] = useState(false)
  const [removeBlacklistReason, setRemoveBlacklistReason] = useState('')
  const [removeBlacklistLoading, setRemoveBlacklistLoading] = useState(false)
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
  }, [offset, arama, durum])

  useEffect(() => { loadCandidates() }, [loadCandidates])

  const handleSearch = () => { setOffset(0); loadCandidates() }

  const handleDownloadCVs = async () => {
    setDownloading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`${API_URL}/api/candidates/export/download-cvs?all=true`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'İndirme hatası')
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
      toast.success('CV dosyaları indirildi')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Bilinmeyen hata'
      toast.error(message)
    } finally {
      setDownloading(false)
    }
  }

  const loadDetail = async (candidate: CandidateItem) => {
    setSelectedCandidate(candidate)
    setDetailLoading(true)
    setDetailData(null)
    setBlacklistInfo(null)
    try {
      const res = await fetch(`${API_URL}/api/candidates/${candidate.id}`, { headers: getHeaders() })
      const data = await res.json()
      if (data.success) {
        const candidateData = data.data.candidate || data.data
        setDetailData(candidateData)
        // Kara liste bilgisini yükle
        if (candidateData.is_blacklisted === 1 || candidateData.durum === 'blacklist') {
          try {
            const blRes = await fetch(`${API_URL}/api/candidates/${candidate.id}/blacklist`, { headers: getHeaders() })
            const blData = await blRes.json()
            if (blData.is_blacklisted) {
              setBlacklistInfo(blData.data || blData)
            }
          } catch (e) {
            console.error('Blacklist info yüklenemedi:', e)
          }
        }
      }
    } catch (err) {
      console.error('Detail hatasi:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleStatusChange = async (candidateId: number, action: 'elen' | 'arsivle' | 'ise-al') => {
    try {
      const response = await fetch(`${API_URL}/api/candidates/${candidateId}/${action}`, {
        method: 'PATCH',
        headers: getHeaders()
      })
      const res = await response.json()
      if (res.success) {
        toast.success(res.message)
        setSelectedCandidate(null)
        loadCandidates()
      } else {
        toast.error(res.detail || 'İşlem başarısız')
      }
    } catch (err) {
      toast.error('Bir hata oluştu')
      console.error('Status change error:', err)
    }
  }

  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  const durumLabel = (d: string) => {
    const map: Record<string, string> = {
      yeni: 'Yeni',
      degerlendirmede: 'Değerlendirmede',
      pozisyona_atandi: 'Pozisyon Havuzunda',
      mulakat: 'Mülakat',
      kabul: 'Kabul',
      ise_alindi: 'İşe Alındı',
      red: 'Red',
      arsiv: 'Arşiv',
      blacklist: 'Kara Liste'
    }
    return map[d] || d
  }

  const durumVariant = (d: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    if (d === 'kabul' || d === 'ise_alindi') return 'default'
    if (d === 'red' || d === 'arsiv' || d === 'blacklist') return 'destructive'
    if (d === 'mulakat' || d === 'pozisyona_atandi') return 'outline'
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
              CV İndir
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
                <SelectItem value='all'>Tüm Durumlar</SelectItem>
                <SelectItem value='yeni'>Yeni</SelectItem>
                <SelectItem value='pozisyona_atandi'>Pozisyon Havuzunda</SelectItem>
                <SelectItem value='mulakat'>Mülakat</SelectItem>
                <SelectItem value='ise_alindi'>İşe Alındı</SelectItem>
                <SelectItem value='arsiv'>Arşiv</SelectItem>
                <SelectItem value='blacklist'>Kara Liste</SelectItem>
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
                    <TableHead>CV'de Belirtilen Unvan</TableHead>
                    <TableHead>Lokasyon</TableHead>
                    <TableHead>Deneyim</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead>CV Yükleme Tarihi</TableHead>
                    <TableHead className='text-right'>Detay</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {candidates.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className='text-center text-muted-foreground py-8'>
                        Aday bulunamadı
                      </TableCell>
                    </TableRow>
                  ) : (
                    candidates.map(c => (
                      <TableRow key={c.id} className={`cursor-pointer hover:bg-muted/50 ${c.durum === 'blacklist' ? 'bg-red-50' : ''}`} onClick={() => loadDetail(c)}>
                        <TableCell>
                          <div className='font-medium'>{c.ad_soyad}</div>
                          <div className='text-xs text-muted-foreground'>{c.email}</div>
                        </TableCell>
                        <TableCell className='text-sm'>{c.mevcut_pozisyon || '-'}</TableCell>
                        <TableCell className='text-sm'>{c.lokasyon || '-'}</TableCell>
                        <TableCell className='text-sm'>{c.toplam_deneyim_yil ? c.toplam_deneyim_yil + ' yıl' : '-'}</TableCell>
                        <TableCell>
                          <Badge variant={durumVariant(c.durum)}>{durumLabel(c.durum)}</Badge>
                        </TableCell>
                        <TableCell className='text-sm text-muted-foreground'>
                          {c.olusturma_tarihi ? <span title={new Date(c.olusturma_tarihi).toLocaleString('tr-TR')} style={{cursor: 'default'}}>{getRelativeTime(c.olusturma_tarihi)}</span> : '-'}
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
                  <div><span className='text-sm text-muted-foreground'>Deneyim:</span> <span className='font-medium'>{detailData.toplam_deneyim_yil ? detailData.toplam_deneyim_yil + ' yıl' : '-'}</span></div>
                  <div><span className='text-sm text-muted-foreground'>CV'deki Unvan:</span> <span className='font-medium'>{String(detailData.mevcut_pozisyon || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Şirket:</span> <span className='font-medium'>{String(detailData.mevcut_sirket || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Eğitim:</span> <span className='font-medium'>{String(detailData.egitim || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Üniversite:</span> <span className='font-medium'>{String(detailData.universite || '-')}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Bölüm:</span> <span className='font-medium'>{String(detailData.bolum || '-')}</span></div>
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

                {/* Kara Liste Bilgisi */}
                {(detailData.durum === 'blacklist' || detailData.is_blacklisted === 1) && blacklistInfo && (
                  <div className='border-t pt-4 mt-4'>
                    <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                      <p className="text-sm font-medium text-red-800 flex items-center gap-1">
                        <Ban className="h-4 w-4" /> Kara Listede
                      </p>
                      <p className="text-xs text-red-700 mt-1">Neden: {blacklistInfo.reason || '-'}</p>
                      <p className="text-xs text-red-600">Ekleyen: {blacklistInfo.blacklisted_by_name || '-'}</p>
                      <p className="text-xs text-red-600">Tarih: {blacklistInfo.blacklisted_at ? new Date(blacklistInfo.blacklisted_at).toLocaleDateString('tr-TR') : '-'}</p>
                    </div>
                    <Button
                      variant='outline'
                      size='sm'
                      onClick={() => setRemoveBlacklistDialogOpen(true)}
                      className='mt-3 text-green-600 hover:text-green-700 hover:bg-green-50'
                    >
                      <CheckCircle className='h-4 w-4 mr-1' />
                      Kara Listeden Çıkar
                    </Button>
                  </div>
                )}

                {/* Durum Değiştirme Butonları */}
                {detailData.durum !== 'ise_alindi' && detailData.durum !== 'arsiv' && detailData.durum !== 'blacklist' && detailData.is_blacklisted !== 1 && (
                  <div className='border-t pt-4 mt-4'>
                    <p className='text-sm text-muted-foreground mb-3'>Durum Değiştir:</p>
                    <div className='flex flex-wrap gap-2'>
                      {(detailData.durum === 'mulakat' || detailData.durum === 'pozisyona_atandi') && (
                        <Button
                          variant='outline'
                          size='sm'
                          onClick={() => handleStatusChange(selectedCandidate!.id, 'elen')}
                          className='text-orange-600 hover:text-orange-700 hover:bg-orange-50'
                        >
                          <XCircle className='h-4 w-4 mr-1' />
                          Elen
                        </Button>
                      )}
                      <Button
                        variant='outline'
                        size='sm'
                        onClick={() => handleStatusChange(selectedCandidate!.id, 'ise-al')}
                        className='text-green-600 hover:text-green-700 hover:bg-green-50'
                      >
                        <CheckCircle className='h-4 w-4 mr-1' />
                        İşe Al
                      </Button>
                      <Button
                        variant='outline'
                        size='sm'
                        onClick={() => handleStatusChange(selectedCandidate!.id, 'arsivle')}
                        className='text-gray-600 hover:text-gray-700 hover:bg-gray-50'
                      >
                        <Archive className='h-4 w-4 mr-1' />
                        Arşivle
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className='text-center text-muted-foreground'>Veri yüklenemedi</p>
            )}
          </div>
        </div>
      )}

      {/* Kara Listeden Çıkar Dialog */}
      <Dialog open={removeBlacklistDialogOpen} onOpenChange={(o) => { setRemoveBlacklistDialogOpen(o); if (!o) setRemoveBlacklistReason(''); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Kara Listeden Çıkar
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <p className="text-sm text-green-800">Aday kara listeden çıkarılacak ve tekrar değerlendirmeye alınabilecektir.</p>
            </div>
            <div>
              <label className="text-sm font-medium">Çıkarma Nedeni (Opsiyonel)</label>
              <textarea
                className="w-full mt-1 p-2 border rounded-md text-sm min-h-[60px]"
                placeholder="Örn: Yanlışlıkla eklenmişti, durumu değişti..."
                value={removeBlacklistReason}
                onChange={(e) => setRemoveBlacklistReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoveBlacklistDialogOpen(false)}>İptal</Button>
            <Button
              variant="default"
              className="bg-green-600 hover:bg-green-700"
              onClick={async () => {
                if (!selectedCandidate?.id) return;
                setRemoveBlacklistLoading(true);
                try {
                  const reasonParam = removeBlacklistReason.trim() ? `?removal_reason=${encodeURIComponent(removeBlacklistReason.trim())}` : '';
                  const res = await fetch(`${API_URL}/api/candidates/${selectedCandidate.id}/blacklist${reasonParam}`, {
                    method: 'DELETE',
                    headers: getHeaders()
                  });
                  const data = await res.json();
                  if (data.success) {
                    toast.success('Aday kara listeden çıkarıldı');
                    setRemoveBlacklistDialogOpen(false);
                    setRemoveBlacklistReason('');
                    setBlacklistInfo(null);
                    setSelectedCandidate(null);
                    loadCandidates();
                  } else {
                    toast.error(data.error || data.detail || 'Kara listeden çıkarma başarısız');
                  }
                } catch (err) {
                  toast.error('Bir hata oluştu');
                } finally {
                  setRemoveBlacklistLoading(false);
                }
              }}
              disabled={removeBlacklistLoading}
            >
              {removeBlacklistLoading ? 'İşleniyor...' : 'Kara Listeden Çıkar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
