import { useState } from 'react'
import { AlertTriangle, Trash2, Database, ServerCrash } from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ContentSection } from '../components/content-section'

const API = 'http://***REMOVED***:8000'

interface ResetDialogState {
  open: boolean
  level: 'candidates' | 'pools' | 'full' | null
  title: string
  description: string
}

export function SettingsAdvanced() {
  const { auth } = useAuthStore()
  const userRole = auth.user?.role?.[0] || 'user'
  const isSuperAdmin = userRole === 'super_admin'

  const [dialogState, setDialogState] = useState<ResetDialogState>({
    open: false,
    level: null,
    title: '',
    description: '',
  })
  const [password, setPassword] = useState('')
  const [confirmText, setConfirmText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const openResetDialog = (
    level: 'candidates' | 'pools' | 'full',
    title: string,
    description: string
  ) => {
    setDialogState({ open: true, level, title, description })
    setPassword('')
    setConfirmText('')
    setError('')
    setSuccess('')
  }

  const closeDialog = () => {
    setDialogState({ open: false, level: null, title: '', description: '' })
    setPassword('')
    setConfirmText('')
    setError('')
  }

  const handleReset = async () => {
    if (!dialogState.level) return
    if (confirmText !== 'SIFIRLA') {
      setError('Onay için SIFIRLA yazın')
      return
    }
    if (!password) {
      setError('Şifre gerekli')
      return
    }

    setLoading(true)
    setError('')

    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`${API}/api/admin/reset-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          level: dialogState.level,
          password: password,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'İşlem başarısız')
      }

      setSuccess(data.message || 'Veriler başarıyla sıfırlandı')
      setTimeout(() => {
        closeDialog()
        setSuccess('')
      }, 2000)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Bir hata oluştu'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const resetCards = [
    {
      level: 'candidates' as const,
      title: 'Aday Verilerini Sıfırla',
      description: 'Tüm aday kayıtlarını ve CV dosyalarını siler. Havuzlar ve pozisyonlar korunur.',
      icon: Trash2,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
    },
    {
      level: 'pools' as const,
      title: 'Havuz Verilerini Sıfırla',
      description: 'Tüm havuzları, pozisyonları ve ilişkili aday verilerini siler.',
      icon: Database,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
    },
    {
      level: 'full' as const,
      title: 'Tüm Sistemi Sıfırla',
      description: 'Tüm verileri siler: adaylar, havuzlar, pozisyonlar, email hesapları. DİKKAT: Bu işlem geri alınamaz!',
      icon: ServerCrash,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      superAdminOnly: true,
    },
  ]

  return (
    <ContentSection
      title='Gelişmiş Ayarlar'
      desc='Sistem verilerini yönetme ve sıfırlama işlemleri. Bu işlemler geri alınamaz.'
    >
      <div className='space-y-4'>
        {resetCards.map((card) => {
          if (card.superAdminOnly && !isSuperAdmin) return null
          
          return (
            <Card key={card.level} className='border-dashed'>
              <CardHeader className='pb-3'>
                <div className='flex items-start gap-4'>
                  <div className={`p-2 rounded-lg ${card.bgColor}`}>
                    <card.icon className={`h-5 w-5 ${card.color}`} />
                  </div>
                  <div className='flex-1'>
                    <CardTitle className='text-base'>{card.title}</CardTitle>
                    <CardDescription className='mt-1'>
                      {card.description}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className='pt-0'>
                <Button
                  variant='outline'
                  size='sm'
                  className={`${card.color} border-current hover:bg-current/10`}
                  onClick={() => openResetDialog(card.level, card.title, card.description)}
                >
                  <AlertTriangle className='h-4 w-4 mr-2' />
                  Sıfırla
                </Button>
              </CardContent>
            </Card>
          )
        })}

        <Dialog open={dialogState.open} onOpenChange={(open) => !open && closeDialog()}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className='flex items-center gap-2 text-red-600'>
                <AlertTriangle className='h-5 w-5' />
                {dialogState.title}
              </DialogTitle>
              <DialogDescription>
                {dialogState.description}
              </DialogDescription>
            </DialogHeader>

            <div className='space-y-4 py-4'>
              {success ? (
                <div className='p-3 bg-green-50 text-green-700 rounded-lg text-center'>
                  {success}
                </div>
              ) : (
                <>
                  <div className='space-y-2'>
                    <Label htmlFor='password'>Şifreniz</Label>
                    <Input
                      id='password'
                      type='password'
                      placeholder='Mevcut şifrenizi girin'
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>

                  <div className='space-y-2'>
                    <Label htmlFor='confirm'>
                      Onaylamak için <strong>SIFIRLA</strong> yazın
                    </Label>
                    <Input
                      id='confirm'
                      placeholder='SIFIRLA'
                      value={confirmText}
                      onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
                    />
                  </div>

                  {error && (
                    <div className='p-3 bg-red-50 text-red-600 rounded-lg text-sm'>
                      {error}
                    </div>
                  )}
                </>
              )}
            </div>

            <DialogFooter>
              <Button variant='outline' onClick={closeDialog} disabled={loading}>
                İptal
              </Button>
              {!success && (
                <Button
                  variant='destructive'
                  onClick={handleReset}
                  disabled={loading || confirmText !== 'SIFIRLA' || !password}
                >
                  {loading ? 'Siliniyor...' : 'Verileri Sil'}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </ContentSection>
  )
}
