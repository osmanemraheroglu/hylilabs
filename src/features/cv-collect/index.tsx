import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { RefreshCw, Upload, FileText, CheckCircle, XCircle, HardDrive, BarChart3 } from 'lucide-react'

const API_URL = 'http://***REMOVED***:8000'

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}` }
}

function getJsonHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

interface ParseResult {
  candidate_id: number
  ad_soyad: string
  email: string
  telefon: string | null
  lokasyon: string | null
  mevcut_pozisyon: string | null
  toplam_deneyim_yil: number | null
  cv_source: string | null
}

interface CollectionStats {
  toplam_islem: number
  toplam_taranan: number
  toplam_cv: number
  toplam_basarili: number
  toplam_hatali: number
  basari_orani: number
}

interface StorageStats {
  count: number
  total_size_mb: number
}

interface HistoryItem {
  id: number
  account_email: string
  taranan_email: number
  bulunan_cv: number
  basarili_cv: number
  mevcut_aday: number
  hatali_cv: number
  durum: string
  tarih: string
}

export default function CvCollect() {
  const [stats, setStats] = useState<{ collection: CollectionStats; storage: StorageStats } | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [parseResult, setParseResult] = useState<ParseResult | null>(null)
  const [parseError, setParseError] = useState('')
  const [message, setMessage] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadData = useCallback(() => {
    Promise.all([
      fetch(`${API_URL}/api/cv/stats`, { headers: getJsonHeaders() }).then(r => r.json()),
      fetch(`${API_URL}/api/cv/history`, { headers: getJsonHeaders() }).then(r => r.json())
    ])
      .then(([statsRes, historyRes]) => {
        if (statsRes.success) setStats(statsRes.data)
        if (historyRes.success) setHistory(historyRes.data)
      })
      .catch(err => console.error('CV data hatasi:', err))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const showMsg = (msg: string) => {
    setMessage(msg)
    setTimeout(() => setMessage(''), 5000)
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    setParseResult(null)
    setParseError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_URL}/api/cv/upload`, {
        method: 'POST',
        headers: getHeaders(),
        body: formData
      })
      const data = await res.json()
      if (data.success) {
        setParseResult(data.data)
        showMsg('CV basariyla yuklendi ve parse edildi')
        loadData()
      } else {
        setParseError(data.message || data.detail || 'CV parse edilemedi')
      }
    } catch (err) {
      setParseError('Baglanti hatasi')
    } finally {
      setUploading(false)
    }
  }

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragActive(true) }
  const onDragLeave = () => setDragActive(false)

  if (loading) {
    return (
      <div className='flex items-center justify-center h-64'>
        <RefreshCw className='h-8 w-8 animate-spin text-muted-foreground' />
      </div>
    )
  }

  return (
    <div className='space-y-6'>
      <div>
        <h2 className='text-2xl font-bold tracking-tight'>CV Topla</h2>
        <p className='text-muted-foreground'>CV yukleyin, otomatik parse edilsin</p>
      </div>

      {message && (
        <div className='rounded-md bg-green-50 p-4 text-sm text-green-800 border border-green-200'>
          {message}
        </div>
      )}

      <div className='grid gap-4 md:grid-cols-4'>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Toplam CV</CardTitle>
            <FileText className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{stats?.collection?.toplam_cv ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Basarili Parse</CardTitle>
            <CheckCircle className='h-4 w-4 text-green-500' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold text-green-600'>{stats?.collection?.toplam_basarili ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Basari Orani</CardTitle>
            <BarChart3 className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{stats?.collection?.basari_orani?.toFixed(1) ?? 0}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Depolama</CardTitle>
            <HardDrive className='h-4 w-4 text-muted-foreground' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold'>{stats?.storage?.count ?? 0} dosya</div>
            <p className='text-xs text-muted-foreground'>{stats?.storage?.total_size_mb ?? 0} MB</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className='text-base'>CV Yukle</CardTitle>
          <CardDescription>PDF, DOCX, DOC, PNG, JPG dosyalari desteklenir</CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${dragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'}`}
            onClick={() => fileInputRef.current?.click()}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
          >
            <input
              ref={fileInputRef}
              type='file'
              accept='.pdf,.docx,.doc,.png,.jpg,.jpeg'
              onChange={onFileSelect}
              className='hidden'
            />
            {uploading ? (
              <div className='flex flex-col items-center gap-2'>
                <RefreshCw className='h-8 w-8 animate-spin text-primary' />
                <p className='text-sm text-muted-foreground'>CV parse ediliyor...</p>
              </div>
            ) : (
              <div className='flex flex-col items-center gap-2'>
                <Upload className='h-8 w-8 text-muted-foreground' />
                <p className='text-sm font-medium'>Dosya secmek icin tiklayin veya surukleyin</p>
                <p className='text-xs text-muted-foreground'>PDF, DOCX, DOC, PNG, JPG (Maks 10MB)</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {parseError && (
        <div className='rounded-md bg-red-50 p-4 text-sm text-red-800 border border-red-200 flex items-center gap-2'>
          <XCircle className='h-4 w-4' />
          {parseError}
        </div>
      )}

      {parseResult && (
        <Card>
          <CardHeader>
            <CardTitle className='text-base flex items-center gap-2'>
              <CheckCircle className='h-4 w-4 text-green-500' />
              Parse Sonucu
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className='grid gap-3 md:grid-cols-2'>
              <div><span className='text-sm text-muted-foreground'>Ad Soyad:</span> <span className='font-medium'>{parseResult.ad_soyad}</span></div>
              <div><span className='text-sm text-muted-foreground'>Email:</span> <span className='font-medium'>{parseResult.email}</span></div>
              <div><span className='text-sm text-muted-foreground'>Telefon:</span> <span className='font-medium'>{parseResult.telefon || '-'}</span></div>
              <div><span className='text-sm text-muted-foreground'>Lokasyon:</span> <span className='font-medium'>{parseResult.lokasyon || '-'}</span></div>
              <div><span className='text-sm text-muted-foreground'>Pozisyon:</span> <span className='font-medium'>{parseResult.mevcut_pozisyon || '-'}</span></div>
              <div><span className='text-sm text-muted-foreground'>Deneyim:</span> <span className='font-medium'>{parseResult.toplam_deneyim_yil ? parseResult.toplam_deneyim_yil + ' yil' : '-'}</span></div>
              <div><span className='text-sm text-muted-foreground'>Kaynak:</span> <Badge variant='secondary'>{parseResult.cv_source || 'genel'}</Badge></div>
              <div><span className='text-sm text-muted-foreground'>Aday ID:</span> <span className='font-medium'>#{parseResult.candidate_id}</span></div>
            </div>
          </CardContent>
        </Card>
      )}

      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className='text-base'>Toplama Gecmisi (Son 30 Gun)</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tarih</TableHead>
                  <TableHead>Hesap</TableHead>
                  <TableHead>Taranan</TableHead>
                  <TableHead>Bulunan CV</TableHead>
                  <TableHead>Basarili</TableHead>
                  <TableHead>Mevcut</TableHead>
                  <TableHead>Durum</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.slice(0, 20).map(item => (
                  <TableRow key={item.id}>
                    <TableCell className='text-sm'>{item.tarih}</TableCell>
                    <TableCell className='text-sm'>{item.account_email}</TableCell>
                    <TableCell>{item.taranan_email}</TableCell>
                    <TableCell>{item.bulunan_cv}</TableCell>
                    <TableCell className='text-green-600'>{item.basarili_cv}</TableCell>
                    <TableCell>{item.mevcut_aday}</TableCell>
                    <TableCell>
                      <Badge variant={item.durum === 'tamamlandi' ? 'default' : 'destructive'}>
                        {item.durum}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
