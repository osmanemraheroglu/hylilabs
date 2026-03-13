import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { RefreshCw, Upload, FileText, CheckCircle, XCircle, HardDrive, BarChart3, Mail, FolderOpen, AlertCircle, Clock, Ban, Files } from 'lucide-react'

const API_URL = 'http://***REMOVED***:8000'
const BULK_MAX_FILES = 20
const BULK_ALLOWED_EXTENSIONS = ['.pdf', '.docx']

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

interface EmailAccount {
  id: number
  ad: string
  email: string
  aktif: number
}

interface EmailFolder {
  name: string
  display_name: string
}

interface ScanResult {
  processed: number
  cv_found: number
  success: number
  duplicate: number
  error: number
  candidates: { id: number; ad_soyad: string; email: string }[]
  errors: { file: string; error: string }[]
}

interface BulkFileResult {
  filename: string
  status: 'success' | 'error' | 'duplicate' | 'blacklisted' | 'limit' | 'pending' | 'processing'
  message: string
  candidate_id: number | null
}

const getDurumLabel = (durum: string) => {
  const labels: Record<string, string> = {
    'tamamlandi': 'Tamamlandı',
    'basarili': 'Başarılı',
    'kismi_basarili': 'Kısmi Başarılı',
    'basarisiz': 'Başarısız',
    'devam_ediyor': 'Devam Ediyor'
  }
  return labels[durum] || durum
}

function getFileExtension(filename: string): string {
  const idx = filename.lastIndexOf('.')
  return idx >= 0 ? filename.substring(idx).toLowerCase() : ''
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

  // Aday limiti state
  const [limitInfo, setLimitInfo] = useState<{ toplam_aday: number; max_aday: number } | null>(null)

  // Email toplama state'leri
  const [emailAccounts, setEmailAccounts] = useState<EmailAccount[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string>('')
  const [folders, setFolders] = useState<EmailFolder[]>([])
  const [selectedFolder, setSelectedFolder] = useState('INBOX')
  const [unseenOnly, setUnseenOnly] = useState(true)
  const [loadingFolders, setLoadingFolders] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [scanProgress, setScanProgress] = useState(0)

  // Processing tracking state
  const [processingStatus, setProcessingStatus] = useState<{
    active: any[];
    recent: any[];
    has_active: boolean;
  } | null>(null)

  // === TOPLU YÜKLEME STATE'LERİ ===
  const [bulkFiles, setBulkFiles] = useState<File[]>([])
  const [bulkUploading, setBulkUploading] = useState(false)
  const [bulkResults, setBulkResults] = useState<BulkFileResult[]>([])
  const [bulkCurrentIndex, setBulkCurrentIndex] = useState(-1)
  const bulkCancelledRef = useRef(false)
  const [bulkDone, setBulkDone] = useState(false)
  const [bulkValidationError, setBulkValidationError] = useState('')

  const loadData = useCallback(() => {
    Promise.all([
      fetch(`${API_URL}/api/cv/stats`, { headers: getJsonHeaders() }).then(r => r.json()),
      fetch(`${API_URL}/api/cv/history`, { headers: getJsonHeaders() }).then(r => r.json()),
      fetch(`${API_URL}/api/emails`, { headers: getJsonHeaders() }).then(r => r.json()),
      fetch(`${API_URL}/api/dashboard/stats`, { headers: getJsonHeaders() }).then(r => r.json()),
      fetch(`${API_URL}/api/companies/me`, { headers: getJsonHeaders() }).then(r => r.json())
    ])
      .then(([statsRes, historyRes, emailsRes, dashboardRes, companyRes]) => {
        if (statsRes.success) setStats(statsRes.data)
        if (historyRes.success) setHistory(historyRes.data)
        if (emailsRes.success) {
          const activeAccounts = emailsRes.data.filter((a: EmailAccount) => a.aktif === 1)
          setEmailAccounts(activeAccounts)
          if (activeAccounts.length > 0 && !selectedAccountId) {
            setSelectedAccountId(String(activeAccounts[0].id))
          }
        }
        // Limit bilgisini ayarla
        const toplam = dashboardRes?.toplam_aday ?? 0
        const max = companyRes?.company?.max_aday ?? 1000
        setLimitInfo({ toplam_aday: toplam, max_aday: max })
      })
      .catch(err => console.error('CV data hatasi:', err))
      .finally(() => setLoading(false))
  }, [selectedAccountId])

  useEffect(() => { loadData() }, [loadData])

  // Processing status polling (her 5 saniyede)
  useEffect(() => {
    const fetchProcessingStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/cv/processing-status`, {
          headers: getJsonHeaders()
        })
        const data = await res.json()
        if (data.success) {
          setProcessingStatus(data.data)
        }
      } catch (err) {
        console.error('Processing status fetch error:', err)
      }
    }

    // İlk yükleme
    fetchProcessingStatus()

    // 5 saniyede bir polling
    const interval = setInterval(fetchProcessingStatus, 5000)

    return () => clearInterval(interval)
  }, [])

  const showMsg = (msg: string) => {
    setMessage(msg)
    setTimeout(() => setMessage(''), 5000)
  }

  // === TEKLİ YÜKLEME (1 dosya seçildiğinde direkt çalışır) ===
  const handleSingleUpload = async (file: File) => {
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

      // 403 limit hatası özel işleme
      if (res.status === 403) {
        setParseError(`⚠️ ${data.detail || 'Aday limitinize ulaştınız!'}`)
        loadData() // Limit göstergesini güncelle
        return
      }

      if (data.success) {
        setParseResult(data.data)
        showMsg('CV başarıyla yüklendi ve parse edildi')
        loadData()
      } else {
        setParseError(data.message || data.detail || 'CV parse edilemedi')
      }
    } catch (err) {
      setParseError('Bağlantı hatası')
    } finally {
      setUploading(false)
    }
  }

  // === DOSYA SEÇİMİ (tek veya çoklu) ===
  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return

    const files = Array.from(e.target.files)

    if (files.length === 1) {
      // Tek dosya — direkt yükle
      handleSingleUpload(files[0])
    } else {
      // Çoklu dosya — toplu yükleme akışına geç
      handleMultipleFiles(files)
    }

    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // === SÜRÜKLE-BIRAK (tek veya çoklu) ===
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)

    if (!e.dataTransfer.files || e.dataTransfer.files.length === 0) return

    const files = Array.from(e.dataTransfer.files)

    if (files.length === 1) {
      handleSingleUpload(files[0])
    } else {
      handleMultipleFiles(files)
    }
  }

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragActive(true) }
  const onDragLeave = () => setDragActive(false)

  // === ÇOKLU DOSYA İŞLEME ===
  const handleMultipleFiles = (files: File[]) => {
    setBulkValidationError('')
    setParseResult(null)
    setParseError('')

    // Max dosya sayısı kontrolü
    if (files.length > BULK_MAX_FILES) {
      setBulkValidationError(`En fazla ${BULK_MAX_FILES} CV yükleyebilirsiniz. ${files.length} dosya seçildi.`)
      return
    }

    // Format kontrolü
    const invalidFiles = files.filter(f => !BULK_ALLOWED_EXTENSIONS.includes(getFileExtension(f.name)))
    if (invalidFiles.length > 0) {
      const invalidNames = invalidFiles.map(f => f.name).join(', ')
      setBulkValidationError(`Desteklenmeyen dosya formatı: ${invalidNames}. Çoklu yüklemede sadece PDF ve DOCX desteklenir.`)
      return
    }

    // Boş dosya kontrolü
    const emptyFiles = files.filter(f => f.size === 0)
    if (emptyFiles.length > 0) {
      setBulkValidationError(`Boş dosya tespit edildi: ${emptyFiles.map(f => f.name).join(', ')}`)
      return
    }

    setBulkFiles(files)
    setBulkResults([])
    setBulkDone(false)
    setBulkCurrentIndex(-1)
  }

  // === TOPLU YÜKLEME BAŞLAT ===
  const startBulkUpload = async () => {
    if (bulkFiles.length === 0) return

    setBulkUploading(true)
    setBulkDone(false)
    bulkCancelledRef.current = false

    // İlk durumları ayarla
    const initialResults: BulkFileResult[] = bulkFiles.map(f => ({
      filename: f.name,
      status: 'pending',
      message: '',
      candidate_id: null
    }))
    setBulkResults(initialResults)

    const updatedResults = [...initialResults]

    for (let i = 0; i < bulkFiles.length; i++) {
      // İptal kontrolü
      if (bulkCancelledRef.current) {
        for (let j = i; j < bulkFiles.length; j++) {
          updatedResults[j] = { ...updatedResults[j], status: 'error', message: 'İptal edildi' }
        }
        setBulkResults([...updatedResults])
        break
      }

      setBulkCurrentIndex(i)
      updatedResults[i] = { ...updatedResults[i], status: 'processing', message: 'İşleniyor...' }
      setBulkResults([...updatedResults])

      try {
        const formData = new FormData()
        formData.append('file', bulkFiles[i])

        const res = await fetch(`${API_URL}/api/cv/upload`, {
          method: 'POST',
          headers: getHeaders(),
          body: formData
        })
        const data = await res.json()

        if (res.status === 403) {
          updatedResults[i] = {
            ...updatedResults[i],
            status: 'limit',
            message: data.detail || 'Aday limitine ulaşıldı'
          }
        } else if (res.status === 429) {
          updatedResults[i] = {
            ...updatedResults[i],
            status: 'error',
            message: data.detail || 'Rate limit aşıldı'
          }
        } else if (data.success) {
          updatedResults[i] = {
            ...updatedResults[i],
            status: 'success',
            message: `${data.data?.ad_soyad || 'Aday'} eklendi`,
            candidate_id: data.data?.candidate_id || null
          }
        } else {
          // Duplicate veya diğer hatalar
          const isDuplicate = (data.message || '').toLowerCase().includes('mevcut') ||
                              (data.message || '').toLowerCase().includes('duplicate') ||
                              (data.data?.existing_id)
          const isBlacklisted = data.data?.blacklisted === true

          if (isBlacklisted) {
            updatedResults[i] = {
              ...updatedResults[i],
              status: 'blacklisted',
              message: data.message || 'Kara listede'
            }
          } else if (isDuplicate) {
            updatedResults[i] = {
              ...updatedResults[i],
              status: 'duplicate',
              message: data.message || 'Mevcut aday',
              candidate_id: data.data?.existing_id || null
            }
          } else {
            updatedResults[i] = {
              ...updatedResults[i],
              status: 'error',
              message: data.message || data.detail || 'İşlenemedi'
            }
          }
        }
      } catch (err) {
        updatedResults[i] = {
          ...updatedResults[i],
          status: 'error',
          message: 'Bağlantı hatası'
        }
      }

      setBulkResults([...updatedResults])
    }

    setBulkCurrentIndex(-1)
    setBulkUploading(false)
    setBulkDone(true)
    loadData() // İstatistikleri güncelle
  }

  const cancelBulkUpload = () => {
    bulkCancelledRef.current = true
  }

  const resetBulkUpload = () => {
    setBulkFiles([])
    setBulkResults([])
    setBulkCurrentIndex(-1)
    setBulkDone(false)
    setBulkUploading(false)
    setBulkValidationError('')
    bulkCancelledRef.current = false
  }

  // Toplu yükleme özet hesaplama
  const bulkSummary = {
    total: bulkResults.length,
    success: bulkResults.filter(r => r.status === 'success').length,
    error: bulkResults.filter(r => r.status === 'error' || r.status === 'limit').length,
    duplicate: bulkResults.filter(r => r.status === 'duplicate').length,
    blacklisted: bulkResults.filter(r => r.status === 'blacklisted').length,
  }

  // Email klasorlerini yukle
  const loadFolders = async () => {
    if (!selectedAccountId) return
    setLoadingFolders(true)
    setFolders([])
    try {
      const res = await fetch(`${API_URL}/api/emails/${selectedAccountId}/folders`, { headers: getJsonHeaders() })
      const data = await res.json()
      if (data.success && data.data) {
        setFolders(data.data)
        if (data.data.length > 0 && !data.data.find((f: EmailFolder) => f.name === selectedFolder)) {
          setSelectedFolder(data.data[0].name)
        }
      } else {
        showMsg(data.message || 'Klasörler yüklenemedi')
      }
    } catch (err) {
      showMsg('Klasör yükleme hatası')
    } finally {
      setLoadingFolders(false)
    }
  }

  // Email tarama baslat
  const startScan = async () => {
    if (!selectedAccountId) return
    setScanning(true)
    setScanResult(null)
    setScanProgress(10)

    try {
      const res = await fetch(`${API_URL}/api/cv/scan-emails`, {
        method: 'POST',
        headers: getJsonHeaders(),
        body: JSON.stringify({
          account_id: parseInt(selectedAccountId),
          folder: selectedFolder,
          unseen_only: unseenOnly,
          limit: 50
        })
      })
      setScanProgress(90)
      const data = await res.json()
      setScanProgress(100)

      if (data.success) {
        setScanResult(data.data)
        showMsg(data.message)
        loadData() // Istatistikleri ve gecmisi guncelle
      } else {
        showMsg(data.detail || data.message || 'Tarama hatası')
      }
    } catch (err) {
      showMsg('Tarama bağlantı hatası')
    } finally {
      setScanning(false)
      setTimeout(() => setScanProgress(0), 1000)
    }
  }

  if (loading) {
    return (
      <div className='flex items-center justify-center h-64'>
        <RefreshCw className='h-8 w-8 animate-spin text-muted-foreground' />
      </div>
    )
  }

  const statusIcon = (status: BulkFileResult['status']) => {
    switch (status) {
      case 'success': return <CheckCircle className='h-4 w-4 text-green-500 flex-shrink-0' />
      case 'error': return <XCircle className='h-4 w-4 text-red-500 flex-shrink-0' />
      case 'limit': return <AlertCircle className='h-4 w-4 text-orange-500 flex-shrink-0' />
      case 'duplicate': return <Files className='h-4 w-4 text-blue-500 flex-shrink-0' />
      case 'blacklisted': return <Ban className='h-4 w-4 text-red-500 flex-shrink-0' />
      case 'processing': return <RefreshCw className='h-4 w-4 text-primary animate-spin flex-shrink-0' />
      case 'pending': return <Clock className='h-4 w-4 text-muted-foreground flex-shrink-0' />
      default: return <Clock className='h-4 w-4 text-muted-foreground flex-shrink-0' />
    }
  }

  return (
    <div className='space-y-6'>
      <div className='flex items-center justify-between'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>CV Topla</h2>
          <p className='text-muted-foreground'>Manuel yükleme veya email'den otomatik CV toplama</p>
        </div>
        {limitInfo && (
          <div className='flex items-center gap-3 bg-muted/50 rounded-lg px-4 py-2'>
            <div className='text-sm'>
              <span className='font-semibold'>{limitInfo.toplam_aday}</span>
              <span className='text-muted-foreground'> / {limitInfo.max_aday === -1 ? '∞' : limitInfo.max_aday}</span>
              <span className='text-muted-foreground ml-1'>Aday</span>
            </div>
            {limitInfo.max_aday !== -1 && (
              <Progress
                value={(limitInfo.toplam_aday / limitInfo.max_aday) * 100}
                className='w-24 h-2'
              />
            )}
          </div>
        )}
      </div>

      {message && (
        <div className='rounded-md bg-green-50 p-4 text-sm text-green-800 border border-green-200'>
          {message}
        </div>
      )}

      {/* Istatistik Kartlari */}
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
            <CardTitle className='text-sm font-medium'>Başarılı Parse</CardTitle>
            <CheckCircle className='h-4 w-4 text-green-500' />
          </CardHeader>
          <CardContent>
            <div className='text-2xl font-bold text-green-600'>{stats?.collection?.toplam_basarili ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>Başarı Oranı</CardTitle>
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

      {/* 3 Sekmeli Yapı */}
      <Tabs defaultValue='manuel' className='w-full'>
        <TabsList className='grid w-full grid-cols-3'>
          <TabsTrigger value='manuel'>Manuel CV Yükle</TabsTrigger>
          <TabsTrigger value='email'>Email'den Topla</TabsTrigger>
          <TabsTrigger value='gecmis'>Toplama Geçmişi</TabsTrigger>
        </TabsList>

        {/* Tab 1: Manuel CV Yükle (tek veya çoklu) */}
        <TabsContent value='manuel' className='space-y-4'>
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>CV Yükle</CardTitle>
              <CardDescription>Tek veya birden fazla CV seçebilirsiniz. PDF, DOCX desteklenir. (Maks {BULK_MAX_FILES} dosya)</CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              {/* Dosya Seçme / Sürükle-Bırak Alanı */}
              {!bulkUploading && !bulkDone && !uploading && (
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
                    multiple
                    onChange={onFileSelect}
                    className='hidden'
                  />
                  <div className='flex flex-col items-center gap-2'>
                    <Upload className='h-8 w-8 text-muted-foreground' />
                    <p className='text-sm font-medium'>Dosya seçmek için tıklayın veya sürükleyin</p>
                    <p className='text-xs text-muted-foreground'>PDF, DOCX, DOC, PNG, JPG — Tek veya birden fazla dosya seçebilirsiniz</p>
                  </div>
                </div>
              )}

              {/* Tekli yükleme sırasında spinner */}
              {uploading && (
                <div className='border-2 border-dashed rounded-lg p-8 text-center border-primary/30 bg-primary/5'>
                  <div className='flex flex-col items-center gap-2'>
                    <RefreshCw className='h-8 w-8 animate-spin text-primary' />
                    <p className='text-sm text-muted-foreground'>CV parse ediliyor...</p>
                  </div>
                </div>
              )}

              {/* Doğrulama Hatası */}
              {bulkValidationError && (
                <div className='rounded-md bg-red-50 p-3 text-sm text-red-800 border border-red-200 flex items-center gap-2'>
                  <AlertCircle className='h-4 w-4 flex-shrink-0' />
                  {bulkValidationError}
                </div>
              )}

              {/* Seçilen Dosyalar Listesi (yükleme başlamadan) */}
              {bulkFiles.length > 0 && !bulkUploading && !bulkDone && (
                <div className='space-y-3'>
                  <div className='flex items-center justify-between'>
                    <p className='text-sm font-medium'>{bulkFiles.length} dosya seçildi</p>
                    <div className='flex gap-2'>
                      <Button variant='outline' size='sm' onClick={resetBulkUpload}>
                        Temizle
                      </Button>
                      <Button size='sm' onClick={startBulkUpload}>
                        <Upload className='h-4 w-4 mr-2' />
                        Yüklemeyi Başlat
                      </Button>
                    </div>
                  </div>
                  <div className='border rounded-lg divide-y max-h-60 overflow-y-auto'>
                    {bulkFiles.map((f, i) => (
                      <div key={i} className='flex items-center gap-3 px-3 py-2 text-sm'>
                        <FileText className='h-4 w-4 text-muted-foreground flex-shrink-0' />
                        <span className='truncate flex-1'>{f.name}</span>
                        <span className='text-muted-foreground text-xs'>{(f.size / 1024).toFixed(0)} KB</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Yükleme İlerlemesi */}
              {(bulkUploading || bulkDone) && bulkResults.length > 0 && (
                <div className='space-y-4'>
                  {/* Progress Bar */}
                  <div className='space-y-2'>
                    <div className='flex items-center justify-between text-sm'>
                      <span className='font-medium'>
                        {bulkUploading
                          ? `${bulkCurrentIndex + 1}/${bulkResults.length} CV işleniyor...`
                          : 'Tamamlandı'
                        }
                      </span>
                      {bulkUploading && (
                        <Button variant='destructive' size='sm' onClick={cancelBulkUpload}>
                          İptal Et
                        </Button>
                      )}
                      {bulkDone && (
                        <Button variant='outline' size='sm' onClick={resetBulkUpload}>
                          Yeni Yükleme
                        </Button>
                      )}
                    </div>
                    <Progress
                      value={bulkDone
                        ? 100
                        : bulkCurrentIndex >= 0
                          ? ((bulkCurrentIndex + 1) / bulkResults.length) * 100
                          : 0
                      }
                      className='w-full h-2'
                    />
                  </div>

                  {/* Özet Kartı (tamamlandığında) */}
                  {bulkDone && (
                    <div className='grid grid-cols-4 gap-3'>
                      <div className='text-center p-3 bg-green-50 rounded-lg border border-green-200'>
                        <div className='text-xl font-bold text-green-600'>{bulkSummary.success}</div>
                        <div className='text-xs text-green-700'>Başarılı</div>
                      </div>
                      <div className='text-center p-3 bg-red-50 rounded-lg border border-red-200'>
                        <div className='text-xl font-bold text-red-600'>{bulkSummary.error}</div>
                        <div className='text-xs text-red-700'>Hata</div>
                      </div>
                      <div className='text-center p-3 bg-blue-50 rounded-lg border border-blue-200'>
                        <div className='text-xl font-bold text-blue-600'>{bulkSummary.duplicate}</div>
                        <div className='text-xs text-blue-700'>Mevcut</div>
                      </div>
                      <div className='text-center p-3 bg-gray-50 rounded-lg border border-gray-200'>
                        <div className='text-xl font-bold text-gray-600'>{bulkSummary.blacklisted}</div>
                        <div className='text-xs text-gray-700'>Kara Liste</div>
                      </div>
                    </div>
                  )}

                  {/* Dosya Listesi + Durumlar */}
                  <div className='border rounded-lg divide-y max-h-80 overflow-y-auto'>
                    {bulkResults.map((r, i) => (
                      <div key={i} className={`flex items-center gap-3 px-3 py-2 text-sm ${r.status === 'processing' ? 'bg-blue-50' : ''}`}>
                        {statusIcon(r.status)}
                        <span className='truncate flex-1 font-medium'>{r.filename}</span>
                        <span className={`text-xs truncate max-w-[200px] ${
                          r.status === 'success' ? 'text-green-600' :
                          r.status === 'error' || r.status === 'limit' ? 'text-red-600' :
                          r.status === 'duplicate' ? 'text-blue-600' :
                          r.status === 'blacklisted' ? 'text-red-600' :
                          'text-muted-foreground'
                        }`}>
                          {r.message || (r.status === 'pending' ? 'Bekliyor' : '')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Tekli yükleme hata mesajı */}
          {parseError && (
            <div className='rounded-md bg-red-50 p-4 text-sm text-red-800 border border-red-200 flex items-center gap-2'>
              <XCircle className='h-4 w-4' />
              {parseError}
            </div>
          )}

          {/* Tekli yükleme parse sonucu */}
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
                  <div><span className='text-sm text-muted-foreground'>Deneyim:</span> <span className='font-medium'>{parseResult.toplam_deneyim_yil ? parseResult.toplam_deneyim_yil + ' yıl' : '-'}</span></div>
                  <div><span className='text-sm text-muted-foreground'>Kaynak:</span> <Badge variant='secondary'>{parseResult.cv_source || 'genel'}</Badge></div>
                  <div><span className='text-sm text-muted-foreground'>Aday ID:</span> <span className='font-medium'>#{parseResult.candidate_id}</span></div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Tab 2: Email'den Topla */}
        <TabsContent value='email' className='space-y-4'>
          {emailAccounts.length === 0 ? (
            <Card>
              <CardContent className='p-6'>
                <div className='flex flex-col items-center gap-3 text-center'>
                  <AlertCircle className='h-10 w-10 text-yellow-500' />
                  <div>
                    <p className='font-medium'>Aktif email hesabı bulunamadı</p>
                    <p className='text-sm text-muted-foreground'>Email Hesapları sayfasından yeni hesap ekleyebilirsiniz.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Progress Bar - Aktif İşlem Varsa */}
              {processingStatus?.has_active && processingStatus.active.length > 0 && (
                <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                    <span className="font-medium text-blue-700">
                      Email'den CV Çekiliyor
                    </span>
                  </div>
                  {processingStatus.active.map((job) => (
                    <div key={job.id} className="mt-2">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>{job.account_email}</span>
                        <span>
                          {job.basarili_cv || 0} başarılı / {job.bulunan_cv || 0} toplam CV
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                          style={{
                            width: `${job.bulunan_cv > 0
                              ? Math.round((job.basarili_cv / job.bulunan_cv) * 100)
                              : 0}%`
                          }}
                        ></div>
                      </div>
                      {job.hatali_cv > 0 && (
                        <p className="text-xs text-red-500 mt-1">
                          {job.hatali_cv} hatalı CV
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Email Hesabi Secimi */}
              <Card>
                <CardHeader>
                  <CardTitle className='text-base flex items-center gap-2'>
                    <Mail className='h-4 w-4' />
                    Email Hesabı Seçimi
                  </CardTitle>
                </CardHeader>
                <CardContent className='space-y-4'>
                  <Select value={selectedAccountId} onValueChange={setSelectedAccountId}>
                    <SelectTrigger>
                      <SelectValue placeholder='Email hesabı seçin' />
                    </SelectTrigger>
                    <SelectContent>
                      {emailAccounts.map(acc => (
                        <SelectItem key={acc.id} value={String(acc.id)}>
                          {acc.ad} ({acc.email})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </CardContent>
              </Card>

              {/* Klasor Secimi */}
              <Card>
                <CardHeader>
                  <CardTitle className='text-base flex items-center gap-2'>
                    <FolderOpen className='h-4 w-4' />
                    Klasör Seçimi
                  </CardTitle>
                </CardHeader>
                <CardContent className='space-y-4'>
                  <div className='flex gap-2'>
                    <Select value={selectedFolder} onValueChange={setSelectedFolder} disabled={folders.length === 0}>
                      <SelectTrigger className='flex-1'>
                        <SelectValue placeholder={folders.length === 0 ? 'Önce klasörleri yükleyin' : 'Klasör seçin'} />
                      </SelectTrigger>
                      <SelectContent>
                        {folders.length === 0 ? (
                          <SelectItem value='INBOX'>INBOX (varsayılan)</SelectItem>
                        ) : (
                          folders.map(f => (
                            <SelectItem key={f.name} value={f.name}>{f.display_name}</SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <Button variant='outline' onClick={loadFolders} disabled={loadingFolders || !selectedAccountId}>
                      {loadingFolders ? <RefreshCw className='h-4 w-4 animate-spin' /> : <RefreshCw className='h-4 w-4' />}
                      <span className='ml-2'>Klasörleri Yükle</span>
                    </Button>
                  </div>
                  {folders.length === 0 && (
                    <p className='text-xs text-muted-foreground'>
                      Klasör listesi yüklenmedi. Varsayılan olarak INBOX taranacak.
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Tarama Ayarlari */}
              <Card>
                <CardHeader>
                  <CardTitle className='text-base'>Tarama Ayarları</CardTitle>
                </CardHeader>
                <CardContent className='space-y-4'>
                  <div className='flex items-center space-x-2'>
                    <Checkbox
                      id='unseen'
                      checked={unseenOnly}
                      onCheckedChange={(checked) => setUnseenOnly(checked === true)}
                    />
                    <label htmlFor='unseen' className='text-sm font-medium leading-none cursor-pointer'>
                      Sadece okunmamış emailleri tara
                    </label>
                  </div>
                  <p className='text-xs text-muted-foreground'>Tek seferde maksimum 50 adet CV işlenir.</p>
                </CardContent>
              </Card>

              {/* Tarama Butonu */}
              <Button
                onClick={startScan}
                disabled={scanning || !selectedAccountId}
                className='w-full'
                size='lg'
              >
                {scanning ? (
                  <>
                    <RefreshCw className='h-4 w-4 animate-spin mr-2' />
                    Taranıyor...
                  </>
                ) : (
                  <>
                    <Mail className='h-4 w-4 mr-2' />
                    CV Topla
                  </>
                )}
              </Button>

              {/* Progress Bar */}
              {scanProgress > 0 && (
                <Progress value={scanProgress} className='w-full' />
              )}

              {/* Tarama Sonucu */}
              {scanResult && (
                <Card>
                  <CardHeader>
                    <CardTitle className='text-base'>Tarama Sonucu</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className='grid grid-cols-4 gap-4 mb-4'>
                      <div className='text-center'>
                        <div className='text-2xl font-bold'>{scanResult.processed}</div>
                        <div className='text-xs text-muted-foreground'>Taranan Email</div>
                      </div>
                      <div className='text-center'>
                        <div className='text-2xl font-bold text-green-600'>{scanResult.success}</div>
                        <div className='text-xs text-muted-foreground'>Yeni Aday</div>
                      </div>
                      <div className='text-center'>
                        <div className='text-2xl font-bold text-blue-600'>{scanResult.duplicate}</div>
                        <div className='text-xs text-muted-foreground'>Mevcut Aday</div>
                      </div>
                      <div className='text-center'>
                        <div className='text-2xl font-bold text-red-600'>{scanResult.error}</div>
                        <div className='text-xs text-muted-foreground'>Hata</div>
                      </div>
                    </div>

                    {scanResult.candidates.length > 0 && (
                      <div className='mt-4'>
                        <p className='text-sm font-medium mb-2'>Eklenen Adaylar:</p>
                        <div className='space-y-1'>
                          {scanResult.candidates.map(c => (
                            <div key={c.id} className='text-sm flex items-center gap-2'>
                              <CheckCircle className='h-3 w-3 text-green-500' />
                              {c.ad_soyad} ({c.email})
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {scanResult.errors.length > 0 && (
                      <div className='mt-4'>
                        <p className='text-sm font-medium mb-2 text-red-600'>Hatalar:</p>
                        <div className='space-y-1'>
                          {scanResult.errors.map((e, i) => (
                            <div key={i} className='text-sm flex items-center gap-2 text-red-600'>
                              <XCircle className='h-3 w-3' />
                              {e.file}: {e.error}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* Tab 3: Toplama Gecmisi */}
        <TabsContent value='gecmis'>
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>Toplama Geçmişi (Son 30 Gün)</CardTitle>
              <CardDescription>
                Bu bölüm yalnızca email üzerinden yapılan otomatik CV toplama işlemlerinin geçmişini gösterir.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {history.length === 0 ? (
                <div className='text-center py-8 text-muted-foreground'>
                  <Mail className='h-10 w-10 mx-auto mb-3 opacity-50' />
                  <p>Henüz email toplama işlemi yapılmamış.</p>
                  <p className='text-sm'>Email'den Topla sekmesinden CV toplama işlemini başlatın.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tarih</TableHead>
                      <TableHead>Hesap</TableHead>
                      <TableHead>Taranan</TableHead>
                      <TableHead>Bulunan CV</TableHead>
                      <TableHead>Başarılı</TableHead>
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
                            {getDurumLabel(item.durum)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
