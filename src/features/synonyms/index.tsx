import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Loader2, Languages, Plus, Sparkles, CheckCircle, XCircle, Search, Trash2 } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// API config
const API = 'http://***REMOVED***:8000'
const H = () => ({
  'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
  'Content-Type': 'application/json'
})

// Types
interface Synonym {
  id: number
  keyword: string
  synonym: string
  synonym_type: 'turkish' | 'english' | 'abbreviation' | 'variation'
  source: 'ai' | 'manual' | 'migrated'
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  company_id: number | null
}

export default function Synonyms() {
  // Tab state
  const [activeTab, setActiveTab] = useState('pending')

  // Pending tab state
  const [pendingList, setPendingList] = useState<Synonym[]>([])
  const [pendingLoading, setPendingLoading] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  // All synonyms tab state
  const [searchKeyword, setSearchKeyword] = useState('')
  const [synonymList, setSynonymList] = useState<Synonym[]>([])
  const [searchLoading, setSearchLoading] = useState(false)

  // AI generate tab state
  const [generateKeyword, setGenerateKeyword] = useState('')
  const [generateLoading, setGenerateLoading] = useState(false)
  const [generatedSynonyms, setGeneratedSynonyms] = useState<string[]>([])

  // Manual add tab state
  const [manualKeyword, setManualKeyword] = useState('')
  const [manualSynonym, setManualSynonym] = useState('')
  const [manualType, setManualType] = useState<string>('turkish')
  const [manualLoading, setManualLoading] = useState(false)

  // Load pending count on mount
  useEffect(() => {
    loadPendingCount()
  }, [])

  // Load pending list when tab changes to pending
  useEffect(() => {
    if (activeTab === 'pending') {
      loadPendingList()
    }
  }, [activeTab])

  // ═══════════════════════════════════════════════════════════════════
  // API FONKSİYONLARI
  // ═══════════════════════════════════════════════════════════════════

  const loadPendingCount = async () => {
    try {
      const res = await fetch(`${API}/api/synonyms/pending/count`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setPendingCount(data.data.count)
      }
    } catch (err) {
      console.error('loadPendingCount error:', err)
    }
  }

  const loadPendingList = async () => {
    setPendingLoading(true)
    try {
      const res = await fetch(`${API}/api/synonyms/pending`, { headers: H() })
      const data = await res.json()
      if (data.success) {
        setPendingList(data.data.synonyms || [])
      } else {
        toast.error(data.detail || 'Liste alınamadı')
      }
    } catch (err) {
      console.error('loadPendingList error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setPendingLoading(false)
    }
  }

  const handleApprove = async () => {
    if (selectedIds.length === 0) return

    try {
      const res = await fetch(`${API}/api/synonyms/approve`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ synonym_ids: selectedIds })
      })
      const data = await res.json()

      if (data.success) {
        toast.success(`${data.data.updated || selectedIds.length} eş anlamlı onaylandı`)
        setSelectedIds([])
        loadPendingList()
        loadPendingCount()
      } else {
        toast.error(data.detail || 'Onaylama başarısız')
      }
    } catch (err) {
      console.error('handleApprove error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  const handleReject = async () => {
    if (selectedIds.length === 0) return

    try {
      const res = await fetch(`${API}/api/synonyms/reject`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ synonym_ids: selectedIds })
      })
      const data = await res.json()

      if (data.success) {
        toast.success(`${data.data.updated || selectedIds.length} eş anlamlı reddedildi`)
        setSelectedIds([])
        loadPendingList()
        loadPendingCount()
      } else {
        toast.error(data.detail || 'Reddetme başarısız')
      }
    } catch (err) {
      console.error('handleReject error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  const handleSearch = async () => {
    if (!searchKeyword.trim()) return

    setSearchLoading(true)
    try {
      const res = await fetch(
        `${API}/api/synonyms?keyword=${encodeURIComponent(searchKeyword.trim())}`,
        { headers: H() }
      )
      const data = await res.json()

      if (data.success) {
        setSynonymList(data.data.synonyms || [])
        if ((data.data.synonyms || []).length === 0) {
          toast.success('Bu keyword için eş anlamlı bulunamadı')
        }
      } else {
        toast.error(data.detail || 'Arama başarısız')
      }
    } catch (err) {
      console.error('handleSearch error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setSearchLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Bu eş anlamlıyı silmek istediğinizden emin misiniz?')) return

    try {
      const res = await fetch(`${API}/api/synonyms/${id}`, {
        method: 'DELETE',
        headers: H()
      })
      const data = await res.json()

      if (data.success) {
        toast.success('Eş anlamlı silindi')
        setSynonymList(prev => prev.filter(s => s.id !== id))
        loadPendingCount()
      } else {
        toast.error(data.detail || 'Silme başarısız')
      }
    } catch (err) {
      console.error('handleDelete error:', err)
      toast.error('Bağlantı hatası')
    }
  }

  const handleGenerate = async () => {
    if (!generateKeyword.trim()) return

    setGenerateLoading(true)
    setGeneratedSynonyms([])

    try {
      const res = await fetch(`${API}/api/synonyms/generate`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ keyword: generateKeyword.trim() })
      })
      const data = await res.json()

      if (data.success) {
        // API'den dönen synonyms array'ini göster
        const synonyms = data.data.synonyms || []
        const synonymTexts = synonyms.map((s: { synonym: string }) => s.synonym)
        setGeneratedSynonyms(synonymTexts)

        const inserted = data.data.inserted || 0
        const skipped = data.data.skipped || 0

        if (inserted > 0) {
          toast.success(`${inserted} eş anlamlı üretildi ve onay listesine eklendi`)
          // Pending count'u güncelle
          loadPendingCount()
        } else if (skipped > 0) {
          toast.success(`Tüm öneriler zaten mevcut (${skipped} atlandı)`)
        } else {
          toast.error('AI öneri üretemedi')
        }
      } else {
        // Rate limit hatası (429) veya diğer hatalar
        toast.error(data.detail || 'Üretim başarısız')
      }
    } catch (err) {
      console.error('handleGenerate error:', err)
      toast.error('Bağlantı hatası')
    } finally {
      setGenerateLoading(false)
    }
  }

  const handleManualAdd = async () => {
    // TODO: ADIM 5.6'da implement edilecek
    console.log('handleManualAdd', manualKeyword, manualSynonym, manualType)
  }

  // ═══════════════════════════════════════════════════════════════════
  // HELPER FONKSİYONLAR
  // ═══════════════════════════════════════════════════════════════════

  const toggleSelect = (id: number) => {
    setSelectedIds(prev =>
      prev.includes(id)
        ? prev.filter(i => i !== id)
        : [...prev, id]
    )
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === pendingList.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(pendingList.map(s => s.id))
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return <Badge variant="default" className="bg-green-500">Onaylı</Badge>
      case 'pending':
        return <Badge variant="secondary">Bekliyor</Badge>
      case 'rejected':
        return <Badge variant="destructive">Reddedildi</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getTypeBadge = (type: string) => {
    const labels: Record<string, string> = {
      turkish: 'Türkçe',
      english: 'İngilizce',
      abbreviation: 'Kısaltma',
      variation: 'Varyasyon'
    }
    return <Badge variant="outline">{labels[type] || type}</Badge>
  }

  // ═══════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Languages className="h-6 w-6" />
            Eş Anlamlılar Yönetimi
          </h1>
          <p className="text-muted-foreground">
            Keyword eş anlamlılarını yönetin, AI ile yeni öneriler oluşturun
          </p>
        </div>
        {pendingCount > 0 && (
          <Badge variant="destructive" className="text-lg px-3 py-1">
            {pendingCount} Onay Bekliyor
          </Badge>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="pending" className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            Onay Bekleyenler
            {pendingCount > 0 && (
              <Badge variant="secondary" className="ml-1">{pendingCount}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="all" className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            Tüm Eş Anlamlılar
          </TabsTrigger>
          <TabsTrigger value="generate" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            AI Üretimi
          </TabsTrigger>
          <TabsTrigger value="manual" className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Manuel Ekleme
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: Onay Bekleyenler */}
        <TabsContent value="pending">
          <Card>
            <CardHeader>
              <CardTitle>Onay Bekleyen Eş Anlamlılar</CardTitle>
              <CardDescription>
                AI tarafından üretilen veya manuel eklenen eş anlamlıları onaylayın veya reddedin
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Toplu işlem butonları */}
              <div className="flex gap-2 mb-4">
                <Button
                  onClick={handleApprove}
                  disabled={selectedIds.length === 0}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Seçilenleri Onayla ({selectedIds.length})
                </Button>
                <Button
                  onClick={handleReject}
                  disabled={selectedIds.length === 0}
                  variant="destructive"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Seçilenleri Reddet ({selectedIds.length})
                </Button>
              </div>

              {/* Tablo */}
              {pendingLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : pendingList.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Onay bekleyen eş anlamlı bulunmuyor
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <Checkbox
                          checked={selectedIds.length === pendingList.length && pendingList.length > 0}
                          onCheckedChange={toggleSelectAll}
                        />
                      </TableHead>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Eş Anlamlı</TableHead>
                      <TableHead>Tip</TableHead>
                      <TableHead>Kaynak</TableHead>
                      <TableHead>Tarih</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingList.map(item => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.includes(item.id)}
                            onCheckedChange={() => toggleSelect(item.id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{item.keyword}</TableCell>
                        <TableCell>{item.synonym}</TableCell>
                        <TableCell>{getTypeBadge(item.synonym_type)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {item.source === 'ai' ? 'AI' : item.source === 'manual' ? 'Manuel' : 'Migrated'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(item.created_at).toLocaleDateString('tr-TR')}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 2: Tüm Eş Anlamlılar */}
        <TabsContent value="all">
          <Card>
            <CardHeader>
              <CardTitle>Tüm Eş Anlamlılar</CardTitle>
              <CardDescription>
                Keyword'e göre arama yapın ve mevcut eş anlamlıları görüntüleyin
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Arama */}
              <div className="flex gap-2 mb-4">
                <Input
                  placeholder="Keyword ara..."
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="max-w-sm"
                />
                <Button onClick={handleSearch} disabled={searchLoading || !searchKeyword.trim()}>
                  {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  <span className="ml-2">Ara</span>
                </Button>
              </div>

              {/* Sonuçlar */}
              {searchLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : synonymList.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  {searchKeyword ? 'Sonuç bulunamadı' : 'Arama yapmak için keyword girin'}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Keyword</TableHead>
                      <TableHead>Eş Anlamlı</TableHead>
                      <TableHead>Tip</TableHead>
                      <TableHead>Durum</TableHead>
                      <TableHead>Kaynak</TableHead>
                      <TableHead className="w-20">İşlem</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {synonymList.map(item => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.keyword}</TableCell>
                        <TableCell>{item.synonym}</TableCell>
                        <TableCell>{getTypeBadge(item.synonym_type)}</TableCell>
                        <TableCell>{getStatusBadge(item.status)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {item.source === 'ai' ? 'AI' : item.source === 'manual' ? 'Manuel' : 'Migrated'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(item.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: AI Üretimi */}
        <TabsContent value="generate">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                AI ile Eş Anlamlı Üret
              </CardTitle>
              <CardDescription>
                Bir keyword girin, AI sizin için eş anlamlılar önersin
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Keyword girin (örn: yazılım geliştirme)"
                  value={generateKeyword}
                  onChange={(e) => setGenerateKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                  className="max-w-md"
                />
                <Button onClick={handleGenerate} disabled={generateLoading || !generateKeyword.trim()}>
                  {generateLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  AI ile Üret
                </Button>
              </div>

              {/* Üretilen sonuçlar */}
              {generatedSynonyms.length > 0 && (
                <div className="mt-4 p-4 border rounded-lg bg-muted/50">
                  <h4 className="font-medium mb-2">Üretilen Eş Anlamlılar:</h4>
                  <div className="flex flex-wrap gap-2">
                    {generatedSynonyms.map((s, i) => (
                      <Badge key={i} variant="secondary" className="text-sm">
                        {s}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground mt-3">
                    Bu eş anlamlılar "Onay Bekleyenler" listesine eklendi.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 4: Manuel Ekleme */}
        <TabsContent value="manual">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Manuel Eş Anlamlı Ekle
              </CardTitle>
              <CardDescription>
                Kendi eş anlamlılarınızı manuel olarak ekleyin
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 max-w-md">
                <div>
                  <label className="text-sm font-medium mb-1 block">Keyword</label>
                  <Input
                    placeholder="Keyword girin"
                    value={manualKeyword}
                    onChange={(e) => setManualKeyword(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Eş Anlamlı</label>
                  <Input
                    placeholder="Eş anlamlı girin"
                    value={manualSynonym}
                    onChange={(e) => setManualSynonym(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Tip</label>
                  <Select value={manualType} onValueChange={setManualType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Tip seçin" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="turkish">Türkçe</SelectItem>
                      <SelectItem value="english">İngilizce</SelectItem>
                      <SelectItem value="abbreviation">Kısaltma</SelectItem>
                      <SelectItem value="variation">Varyasyon</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  onClick={handleManualAdd}
                  disabled={manualLoading || !manualKeyword.trim() || !manualSynonym.trim()}
                  className="w-full"
                >
                  {manualLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Plus className="h-4 w-4 mr-2" />
                  )}
                  Eş Anlamlı Ekle
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
