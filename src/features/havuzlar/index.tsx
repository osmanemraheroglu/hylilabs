import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import {
  FolderTree, Plus, Edit, Trash2, RefreshCw, ChevronRight, ChevronDown,
  Archive, Inbox, Building2, Target, UserPlus, ArrowRightLeft, Search
} from 'lucide-react'

const API_URL = 'http://***REMOVED***:8000'

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

interface SystemPool {
  id: number
  name: string
  icon: string
  is_system: boolean
  candidate_count: number
}

interface Position {
  id: number
  name: string
  icon: string
  keywords: string | null
  description: string | null
  candidate_count: number
}

interface Department {
  id: number
  name: string
  icon: string
  candidate_count: number
  positions: Position[]
  total_position_candidates: number
}

interface HierarchicalData {
  system_pools: SystemPool[]
  departments: Department[]
}

interface Candidate {
  id: number
  ad_soyad: string
  email: string | null
  telefon: string | null
  mevcut_pozisyon: string | null
  toplam_deneyim_yil: number | null
  lokasyon: string | null
  match_score?: number
  match_reason?: string
  remaining_days?: number
  assignment_type?: string
  status?: string
}

interface PoolInfo {
  id: number
  name: string
  icon: string
  pool_type: string
  is_system: number
  keywords: string | null
  description: string | null
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  aktif: { label: 'Aktif', color: 'bg-blue-100 text-blue-800' },
  beklemede: { label: 'Beklemede', color: 'bg-yellow-100 text-yellow-800' },
  inceleniyor: { label: 'Inceleniyor', color: 'bg-purple-100 text-purple-800' },
  mulakat: { label: 'Mulakat', color: 'bg-cyan-100 text-cyan-800' },
  teklif: { label: 'Teklif', color: 'bg-green-100 text-green-800' },
  red: { label: 'Red', color: 'bg-red-100 text-red-800' },
}

export default function Havuzlar() {
  const [tree, setTree] = useState<HierarchicalData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPoolId, setSelectedPoolId] = useState<number | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [poolInfo, setPoolInfo] = useState<PoolInfo | null>(null)
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [expandedDepts, setExpandedDepts] = useState<Set<number>>(new Set())
  const [selectedCandidates, setSelectedCandidates] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // Dialogs
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [assignDialogOpen, setAssignDialogOpen] = useState(false)
  const [transferDialogOpen, setTransferDialogOpen] = useState(false)
  const [statusDialogOpen, setStatusDialogOpen] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [pulling, setPulling] = useState(false)

  // Forms
  const [poolForm, setPoolForm] = useState({
    name: '', pool_type: 'department' as string, parent_id: '' as string,
    icon: '', keywords: '', description: '',
    gerekli_deneyim_yil: '0', gerekli_egitim: '', lokasyon: '',
  })
  const [assignCandidateId, setAssignCandidateId] = useState('')
  const [transferTargetId, setTransferTargetId] = useState('')
  const [statusValue, setStatusValue] = useState('')
  const [allPools, setAllPools] = useState<Array<{ id: number; name: string; pool_type: string }>>([])

  const loadTree = useCallback(() => {
    setLoading(true)
    fetch(`${API_URL}/api/pools/hierarchical`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setTree(res.data)
          // Tum departmanlari otomatik ac
          const ids = new Set<number>()
          res.data.departments?.forEach((d: Department) => ids.add(d.id))
          setExpandedDepts(ids)
        }
      })
      .catch(err => console.error('Tree hatasi:', err))
      .finally(() => setLoading(false))
  }, [])

  const loadAllPools = useCallback(() => {
    fetch(`${API_URL}/api/pools`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) setAllPools(res.data)
      })
      .catch(err => console.error('Pools hatasi:', err))
  }, [])

  const loadCandidates = useCallback((poolId: number) => {
    setCandidatesLoading(true)
    setSelectedCandidates(new Set())
    fetch(`${API_URL}/api/pools/${poolId}/candidates`, { headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setCandidates(res.data)
          setPoolInfo(res.pool)
        }
      })
      .catch(err => console.error('Candidates hatasi:', err))
      .finally(() => setCandidatesLoading(false))
  }, [])

  useEffect(() => { loadTree(); loadAllPools() }, [loadTree, loadAllPools])

  useEffect(() => {
    if (selectedPoolId) loadCandidates(selectedPoolId)
  }, [selectedPoolId, loadCandidates])

  const selectPool = (id: number) => setSelectedPoolId(id)

  const toggleDept = (id: number) => {
    setExpandedDepts(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleCandidate = (id: number) => {
    setSelectedCandidates(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleAllCandidates = () => {
    if (selectedCandidates.size === filteredCandidates.length) {
      setSelectedCandidates(new Set())
    } else {
      setSelectedCandidates(new Set(filteredCandidates.map(c => c.id)))
    }
  }

  // CRUD
  const resetPoolForm = () => setPoolForm({
    name: '', pool_type: 'department', parent_id: '', icon: '',
    keywords: '', description: '', gerekli_deneyim_yil: '0', gerekli_egitim: '', lokasyon: '',
  })

  const openCreate = (type: string, parentId?: number) => {
    resetPoolForm()
    setPoolForm(prev => ({
      ...prev,
      pool_type: type,
      parent_id: parentId ? String(parentId) : '',
    }))
    setCreateDialogOpen(true)
  }

  const openEdit = () => {
    if (!poolInfo) return
    const pool = allPools.find(p => p.id === poolInfo.id)
    if (!pool) return
    const fullPool = pool as Record<string, unknown>
    setPoolForm({
      name: poolInfo.name || '',
      pool_type: poolInfo.pool_type || 'department',
      parent_id: String((fullPool as Record<string, unknown>).parent_id || ''),
      icon: poolInfo.icon || '',
      keywords: poolInfo.keywords || '',
      description: poolInfo.description || '',
      gerekli_deneyim_yil: String((fullPool as Record<string, unknown>).gerekli_deneyim_yil || '0'),
      gerekli_egitim: String((fullPool as Record<string, unknown>).gerekli_egitim || ''),
      lokasyon: String((fullPool as Record<string, unknown>).lokasyon || ''),
    })
    setEditDialogOpen(true)
  }

  const handleCreatePool = () => {
    if (!poolForm.name) return
    const payload: Record<string, unknown> = {
      name: poolForm.name,
      pool_type: poolForm.pool_type,
      icon: poolForm.icon || (poolForm.pool_type === 'position' ? '\uD83C\uDFAF' : '\uD83D\uDCC1'),
      keywords: poolForm.keywords ? poolForm.keywords.split(',').map(k => k.trim()).filter(Boolean) : [],
      description: poolForm.description,
      gerekli_deneyim_yil: Number(poolForm.gerekli_deneyim_yil) || 0,
      gerekli_egitim: poolForm.gerekli_egitim,
      lokasyon: poolForm.lokasyon,
    }
    if (poolForm.parent_id) payload.parent_id = Number(poolForm.parent_id)

    fetch(`${API_URL}/api/pools`, { method: 'POST', headers: getHeaders(), body: JSON.stringify(payload) })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setCreateDialogOpen(false); resetPoolForm(); loadTree(); loadAllPools() }
        else alert(res.detail || 'Hata')
      })
  }

  const handleUpdatePool = () => {
    if (!selectedPoolId || !poolForm.name) return
    const payload: Record<string, unknown> = {
      name: poolForm.name,
      icon: poolForm.icon,
      keywords: poolForm.keywords ? poolForm.keywords.split(',').map(k => k.trim()).filter(Boolean) : [],
      description: poolForm.description,
      gerekli_deneyim_yil: Number(poolForm.gerekli_deneyim_yil) || 0,
      gerekli_egitim: poolForm.gerekli_egitim,
      lokasyon: poolForm.lokasyon,
    }
    fetch(`${API_URL}/api/pools/${selectedPoolId}`, { method: 'PUT', headers: getHeaders(), body: JSON.stringify(payload) })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setEditDialogOpen(false); loadTree(); loadAllPools(); loadCandidates(selectedPoolId) }
        else alert(res.detail || 'Hata')
      })
  }

  const handleDeletePool = () => {
    if (!deleteConfirm) return
    fetch(`${API_URL}/api/pools/${deleteConfirm}`, { method: 'DELETE', headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setDeleteConfirm(null)
          if (selectedPoolId === deleteConfirm) { setSelectedPoolId(null); setCandidates([]); setPoolInfo(null) }
          loadTree(); loadAllPools()
        } else alert(res.detail || 'Hata')
      })
  }

  const handleAssignCandidate = () => {
    if (!selectedPoolId || !assignCandidateId) return
    fetch(`${API_URL}/api/pools/${selectedPoolId}/candidates`, {
      method: 'POST', headers: getHeaders(),
      body: JSON.stringify({ candidate_id: Number(assignCandidateId), reason: 'Manuel atama' })
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) { setAssignDialogOpen(false); setAssignCandidateId(''); loadCandidates(selectedPoolId); loadTree() }
        else alert(res.detail || 'Hata')
      })
  }

  const handleRemoveCandidate = (candidateId: number) => {
    if (!selectedPoolId) return
    fetch(`${API_URL}/api/pools/${selectedPoolId}/candidates/${candidateId}`, { method: 'DELETE', headers: getHeaders() })
      .then(r => r.json())
      .then(res => { if (res.success) { loadCandidates(selectedPoolId); loadTree() } })
  }

  const handleTransfer = () => {
    if (!selectedPoolId || !transferTargetId || selectedCandidates.size === 0) return
    fetch(`${API_URL}/api/pools/transfer`, {
      method: 'POST', headers: getHeaders(),
      body: JSON.stringify({
        candidate_ids: Array.from(selectedCandidates),
        source_pool_id: selectedPoolId,
        target_pool_id: Number(transferTargetId),
      })
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setTransferDialogOpen(false); setTransferTargetId(''); setSelectedCandidates(new Set())
          loadCandidates(selectedPoolId); loadTree()
        } else alert(res.detail || 'Hata')
      })
  }

  const handleStatusUpdate = () => {
    if (!selectedPoolId || !statusValue || selectedCandidates.size === 0) return
    fetch(`${API_URL}/api/pools/${selectedPoolId}/candidates/status`, {
      method: 'PUT', headers: getHeaders(),
      body: JSON.stringify({ candidate_ids: Array.from(selectedCandidates), durum: statusValue })
    })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          setStatusDialogOpen(false); setStatusValue(''); setSelectedCandidates(new Set())
          loadCandidates(selectedPoolId)
        } else alert(res.detail || 'Hata')
      })
  }

  const handleSyncAll = () => {
    setSyncing(true)
    fetch(`${API_URL}/api/pools/sync-all`, { method: "POST", headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          const d = res.data
          alert(`${d.positions_scanned} pozisyon tarandi, ${d.total_transferred} aday aktarildi`)
          loadTree(); loadAllPools(); if (selectedPoolId) loadCandidates(selectedPoolId)
        } else alert(res.detail || "Hata")
      })
      .catch(err => console.error("Sync hatasi:", err))
      .finally(() => setSyncing(false))
  }

  const handlePullCandidates = () => {
    if (!selectedPoolId) return
    setPulling(true)
    fetch(`${API_URL}/api/pools/${selectedPoolId}/pull-candidates`, { method: "POST", headers: getHeaders() })
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          const d = res.data
          alert(`${d.total_scanned} aday tarandi, ${d.matched} eslesti, ${d.transferred} aktarildi`)
          loadCandidates(selectedPoolId); loadTree()
        } else alert(res.detail || "Hata")
      })
      .catch(err => console.error("Pull hatasi:", err))
      .finally(() => setPulling(false))
  }

  // Filtered candidates
  const filteredCandidates = candidates.filter(c => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (c.ad_soyad || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q) ||
      (c.mevcut_pozisyon || '').toLowerCase().includes(q)
  })

  // Toplam aday sayisi
  const totalCandidates = tree
    ? (tree.system_pools?.reduce((s, p) => s + p.candidate_count, 0) || 0) +
      (tree.departments?.reduce((s, d) => s + d.total_position_candidates, 0) || 0)
    : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FolderTree className="h-6 w-6" /> Havuzlar
          </h2>
          <p className="text-muted-foreground text-sm">Departman ve pozisyon havuzlarini yonetin</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { loadTree(); loadAllPools(); if (selectedPoolId) loadCandidates(selectedPoolId) }} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Yenile
          </Button>
          <Button size="sm" variant="outline" onClick={handleSyncAll} disabled={syncing}>{syncing ? <RefreshCw className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}Eslestir</Button>
          <Button size="sm" onClick={() => openCreate('department')}>
            <Plus className="h-4 w-4 mr-1" /> Departman
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold">{totalCandidates}</div><div className="text-xs text-muted-foreground">Toplam Aday</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-blue-600">{tree?.system_pools?.find(s => s.name === 'Genel Havuz')?.candidate_count || 0}</div><div className="text-xs text-muted-foreground">Genel Havuz</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-orange-600">{tree?.system_pools?.find(s => s.name === 'Ar\u015Fiv')?.candidate_count || 0}</div><div className="text-xs text-muted-foreground">Arsiv</div></CardContent></Card>
        <Card><CardContent className="p-3 text-center"><div className="text-2xl font-bold text-green-600">{tree?.departments?.length || 0}</div><div className="text-xs text-muted-foreground">Departman</div></CardContent></Card>
      </div>

      {/* Main Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: Tree */}
        <div className="col-span-4">
          <Card>
            <CardContent className="p-3 space-y-1">
              <div className="text-sm font-medium text-muted-foreground mb-2">Havuz Agaci</div>

              {/* System Pools */}
              {tree?.system_pools?.map(sp => (
                <div
                  key={sp.id}
                  className={`flex items-center justify-between p-2 rounded cursor-pointer hover:bg-muted ${selectedPoolId === sp.id ? 'bg-muted border border-primary' : ''}`}
                  onClick={() => selectPool(sp.id)}
                >
                  <div className="flex items-center gap-2">
                    {sp.name === 'Ar\u015Fiv' ? <Archive className="h-4 w-4 text-orange-500" /> : <Inbox className="h-4 w-4 text-blue-500" />}
                    <span className="text-sm font-medium">{sp.name}</span>
                  </div>
                  <Badge variant="secondary" className="text-xs">{sp.candidate_count}</Badge>
                </div>
              ))}

              {tree?.system_pools && tree.system_pools.length > 0 && <div className="border-t my-2" />}

              {/* Departments */}
              {tree?.departments?.map(dept => (
                <div key={dept.id}>
                  <div
                    className={`flex items-center justify-between p-2 rounded cursor-pointer hover:bg-muted ${selectedPoolId === dept.id ? 'bg-muted border border-primary' : ''}`}
                  >
                    <div className="flex items-center gap-2 flex-1" onClick={() => toggleDept(dept.id)}>
                      {expandedDepts.has(dept.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      <Building2 className="h-4 w-4 text-indigo-500" />
                      <span className="text-sm font-medium">{dept.name}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge variant="secondary" className="text-xs">{dept.total_position_candidates}</Badge>
                      <button onClick={(e) => { e.stopPropagation(); openCreate('position', dept.id) }} className="p-0.5 hover:bg-muted-foreground/10 rounded" title="Pozisyon Ekle">
                        <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </div>
                  </div>

                  {/* Positions */}
                  {expandedDepts.has(dept.id) && dept.positions.map(pos => (
                    <div
                      key={pos.id}
                      className={`flex items-center justify-between p-2 pl-9 rounded cursor-pointer hover:bg-muted ${selectedPoolId === pos.id ? 'bg-muted border border-primary' : ''}`}
                      onClick={() => selectPool(pos.id)}
                    >
                      <div className="flex items-center gap-2">
                        <Target className="h-3.5 w-3.5 text-emerald-500" />
                        <span className="text-sm">{pos.name}</span>
                      </div>
                      <Badge variant="secondary" className="text-xs">{pos.candidate_count}</Badge>
                    </div>
                  ))}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Right: Candidates */}
        <div className="col-span-8">
          {!selectedPoolId ? (
            <Card><CardContent className="p-12 text-center text-muted-foreground">
              <FolderTree className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>Aday listesini gormek icin soldaki agactan bir havuz secin</p>
            </CardContent></Card>
          ) : (
            <Card>
              <CardContent className="p-4 space-y-3">
                {/* Pool Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                      {poolInfo?.name}
                      <Badge variant="outline" className="text-xs">{poolInfo?.pool_type}</Badge>
                    </h3>
                    {poolInfo?.description && <p className="text-xs text-muted-foreground">{poolInfo.description}</p>}
                  </div>
                  <div className="flex gap-1.5">
                    {poolInfo && !poolInfo.is_system && (
                      <>
                        <Button variant="outline" size="sm" onClick={openEdit}><Edit className="h-3.5 w-3.5 mr-1" />Duzenle</Button>
                        <Button variant="outline" size="sm" className="text-red-500" onClick={() => setDeleteConfirm(selectedPoolId)}><Trash2 className="h-3.5 w-3.5 mr-1" />Sil</Button>
                      </>
                    )}
                    {poolInfo && poolInfo.pool_type === "position" && !poolInfo.is_system && (
                      <Button variant="default" size="sm" onClick={handlePullCandidates} disabled={pulling}>{pulling ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Search className="h-3.5 w-3.5 mr-1" />}CV Cek</Button>
                    )}
                    <Button variant="outline" size="sm" onClick={() => setAssignDialogOpen(true)}><UserPlus className="h-3.5 w-3.5 mr-1" />Aday Ata</Button>
                  </div>
                </div>

                {/* Toolbar */}
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="h-4 w-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <Input placeholder="Aday ara..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="pl-8 h-8 text-sm" />
                  </div>
                  {selectedCandidates.size > 0 && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => setTransferDialogOpen(true)}>
                        <ArrowRightLeft className="h-3.5 w-3.5 mr-1" />Transfer ({selectedCandidates.size})
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setStatusDialogOpen(true)}>
                        Durum ({selectedCandidates.size})
                      </Button>
                    </>
                  )}
                  <Badge variant="outline">{filteredCandidates.length} aday</Badge>
                </div>

                {/* Candidates Table */}
                {candidatesLoading ? (
                  <div className="text-center py-8 text-muted-foreground"><RefreshCw className="h-5 w-5 animate-spin inline mr-2" />Yukleniyor...</div>
                ) : filteredCandidates.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">Bu havuzda aday bulunmuyor</div>
                ) : (
                  <div className="border rounded-md overflow-auto max-h-[500px]">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-8"><Checkbox checked={selectedCandidates.size === filteredCandidates.length && filteredCandidates.length > 0} onCheckedChange={toggleAllCandidates} /></TableHead>
                          <TableHead>Ad Soyad</TableHead>
                          <TableHead>Pozisyon</TableHead>
                          <TableHead>Deneyim</TableHead>
                          <TableHead>Lokasyon</TableHead>
                          <TableHead>Skor</TableHead>
                          <TableHead>Durum</TableHead>
                          <TableHead className="w-16"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredCandidates.map(c => (
                          <TableRow key={c.id} className={selectedCandidates.has(c.id) ? 'bg-muted/50' : ''}>
                            <TableCell><Checkbox checked={selectedCandidates.has(c.id)} onCheckedChange={() => toggleCandidate(c.id)} /></TableCell>
                            <TableCell>
                              <div className="font-medium text-sm">{c.ad_soyad}</div>
                              {c.email && <div className="text-xs text-muted-foreground">{c.email}</div>}
                            </TableCell>
                            <TableCell className="text-sm">{c.mevcut_pozisyon || '-'}</TableCell>
                            <TableCell className="text-sm">{c.toplam_deneyim_yil ? `${c.toplam_deneyim_yil} yil` : '-'}</TableCell>
                            <TableCell className="text-sm">{c.lokasyon || '-'}</TableCell>
                            <TableCell>
                              {c.match_score ? <Badge variant="outline" className="text-xs">{c.match_score}</Badge> : c.remaining_days !== undefined ? <Badge variant="outline" className="text-xs">{c.remaining_days}g</Badge> : '-'}
                            </TableCell>
                            <TableCell>
                              {c.status && STATUS_MAP[c.status]
                                ? <Badge className={`text-[10px] ${STATUS_MAP[c.status].color}`}>{STATUS_MAP[c.status].label}</Badge>
                                : c.assignment_type
                                  ? <Badge variant="secondary" className="text-[10px]">{c.assignment_type}</Badge>
                                  : null}
                            </TableCell>
                            <TableCell>
                              <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 h-7 w-7 p-0" onClick={() => handleRemoveCandidate(c.id)} title="Cikar">
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Create Pool Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>{poolForm.pool_type === 'position' ? 'Yeni Pozisyon' : 'Yeni Departman'}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-sm">Ad *</Label><Input value={poolForm.name} onChange={e => setPoolForm({...poolForm, name: e.target.value})} placeholder="Ornek: Yazilim Gelistirme" /></div>
            {poolForm.pool_type === 'position' && (
              <>
                <div><Label className="text-sm">Anahtar Kelimeler (virgul ile)</Label><Input value={poolForm.keywords} onChange={e => setPoolForm({...poolForm, keywords: e.target.value})} placeholder="react, typescript, node.js" /></div>
                <div className="grid grid-cols-2 gap-2">
                  <div><Label className="text-sm">Deneyim (yil)</Label><Input type="number" value={poolForm.gerekli_deneyim_yil} onChange={e => setPoolForm({...poolForm, gerekli_deneyim_yil: e.target.value})} /></div>
                  <div><Label className="text-sm">Lokasyon</Label><Input value={poolForm.lokasyon} onChange={e => setPoolForm({...poolForm, lokasyon: e.target.value})} /></div>
                </div>
                <div><Label className="text-sm">Egitim</Label><Input value={poolForm.gerekli_egitim} onChange={e => setPoolForm({...poolForm, gerekli_egitim: e.target.value})} placeholder="Lisans, Yuksek Lisans" /></div>
              </>
            )}
            <div><Label className="text-sm">Aciklama</Label><Textarea value={poolForm.description} onChange={e => setPoolForm({...poolForm, description: e.target.value})} rows={2} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>Iptal</Button>
            <Button onClick={handleCreatePool} disabled={!poolForm.name}>Olustur</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Pool Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Havuz Duzenle</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-sm">Ad *</Label><Input value={poolForm.name} onChange={e => setPoolForm({...poolForm, name: e.target.value})} /></div>
            <div><Label className="text-sm">Anahtar Kelimeler (virgul ile)</Label><Input value={poolForm.keywords} onChange={e => setPoolForm({...poolForm, keywords: e.target.value})} /></div>
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="text-sm">Deneyim (yil)</Label><Input type="number" value={poolForm.gerekli_deneyim_yil} onChange={e => setPoolForm({...poolForm, gerekli_deneyim_yil: e.target.value})} /></div>
              <div><Label className="text-sm">Lokasyon</Label><Input value={poolForm.lokasyon} onChange={e => setPoolForm({...poolForm, lokasyon: e.target.value})} /></div>
            </div>
            <div><Label className="text-sm">Aciklama</Label><Textarea value={poolForm.description} onChange={e => setPoolForm({...poolForm, description: e.target.value})} rows={2} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Iptal</Button>
            <Button onClick={handleUpdatePool} disabled={!poolForm.name}>Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <Dialog open={deleteConfirm !== null} onOpenChange={o => { if (!o) setDeleteConfirm(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Havuz Sil</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Bu havuzu silmek istediginizden emin misiniz? Icindeki adaylar Genel Havuz'a tasinacaktir.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Iptal</Button>
            <Button variant="destructive" onClick={handleDeletePool}>Sil</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign Candidate Dialog */}
      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Aday Ata</DialogTitle></DialogHeader>
          <div>
            <Label className="text-sm">Aday ID</Label>
            <Input type="number" value={assignCandidateId} onChange={e => setAssignCandidateId(e.target.value)} placeholder="Ornek: 421" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignDialogOpen(false)}>Iptal</Button>
            <Button onClick={handleAssignCandidate} disabled={!assignCandidateId}>Ata</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Transfer Dialog */}
      <Dialog open={transferDialogOpen} onOpenChange={setTransferDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Adaylari Transfer Et ({selectedCandidates.size} aday)</DialogTitle></DialogHeader>
          <div>
            <Label className="text-sm">Hedef Havuz</Label>
            <Select value={transferTargetId} onValueChange={setTransferTargetId}>
              <SelectTrigger><SelectValue placeholder="Havuz secin..." /></SelectTrigger>
              <SelectContent>
                {allPools.filter(p => p.id !== selectedPoolId).map(p => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTransferDialogOpen(false)}>Iptal</Button>
            <Button onClick={handleTransfer} disabled={!transferTargetId}>Transfer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Status Dialog */}
      <Dialog open={statusDialogOpen} onOpenChange={setStatusDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Durum Guncelle ({selectedCandidates.size} aday)</DialogTitle></DialogHeader>
          <div>
            <Label className="text-sm">Yeni Durum</Label>
            <Select value={statusValue} onValueChange={setStatusValue}>
              <SelectTrigger><SelectValue placeholder="Durum secin..." /></SelectTrigger>
              <SelectContent>
                {Object.entries(STATUS_MAP).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStatusDialogOpen(false)}>Iptal</Button>
            <Button onClick={handleStatusUpdate} disabled={!statusValue}>Guncelle</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
