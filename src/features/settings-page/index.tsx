import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { RefreshCw, Save, Settings } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || ""

function getHeaders() {
  const token = localStorage.getItem('access_token')
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

const SETTING_LABELS: Record<string, string> = {
  firma_adi: 'Firma Adı',
  firma_email: 'Firma Email',
  firma_telefon: 'Firma Telefon',
  firma_adres: 'Firma Adres',
  max_kullanici: 'Maksimum Kullanıcı',
  cv_parse_limit: 'Günlük CV Parse Limiti',
}

const DEFAULT_KEYS = ['firma_adi', 'firma_email', 'firma_telefon', 'firma_adres', 'max_kullanici', 'cv_parse_limit']

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [noAccess, setNoAccess] = useState(false)

  const loadSettings = useCallback(() => {
    fetch(`${API_URL}/api/settings`, { headers: getHeaders() })
      .then(r => {
        if (r.status === 403) { setNoAccess(true); return null }
        return r.json()
      })
      .then(res => {
        if (res && res.success) {
          const merged: Record<string, string> = {}
          DEFAULT_KEYS.forEach(k => { merged[k] = '' })
          Object.entries(res.data).forEach(([k, v]) => { merged[k] = String(v) })
          setSettings(merged)
        }
      })
      .catch(err => console.error('Settings hatasi:', err))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadSettings() }, [loadSettings])

  const showMsg = (msg: string) => {
    setMessage(msg)
    setTimeout(() => setMessage(''), 3000)
  }

  const handleSave = async (key: string) => {
    setSaving(key)
    try {
      const res = await fetch(`${API_URL}/api/settings`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify({ key, value: settings[key] || '' })
      })
      const data = await res.json()
      if (data.success) {
        showMsg((SETTING_LABELS[key] || key) + ' kaydedildi')
      } else {
        showMsg('Hata: ' + (data.detail || 'Bilinmeyen hata'))
      }
    } catch (err) {
      showMsg('Bağlantı hatası')
    } finally {
      setSaving(null)
    }
  }

  const updateValue = (key: string, value: string) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  if (loading) {
    return (
      <div className='flex items-center justify-center h-64'>
        <RefreshCw className='h-8 w-8 animate-spin text-muted-foreground' />
      </div>
    )
  }

  if (noAccess) {
    return (
      <div className='space-y-6'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>Ayarlar</h2>
          <p className='text-muted-foreground'>Firma ayarlarını yönetin</p>
        </div>
        <Card>
          <CardContent className='pt-6'>
            <p className='text-center text-muted-foreground'>Bu sayfayı görüntülemek için admin yetkisi gerekli.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className='space-y-6'>
      <div>
        <h2 className='text-2xl font-bold tracking-tight'>Ayarlar</h2>
        <p className='text-muted-foreground'>Firma ayarlarını yönetin</p>
      </div>

      {message && (
        <div className='rounded-md bg-green-50 p-4 text-sm text-green-800 border border-green-200'>
          {message}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className='text-base flex items-center gap-2'>
            <Settings className='h-4 w-4' />
            Firma Bilgileri
          </CardTitle>
          <CardDescription>Firma ile ilgili temel ayarlar</CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          {DEFAULT_KEYS.map(key => (
            <div key={key} className='flex items-end gap-4'>
              <div className='flex-1 space-y-1'>
                <label className='text-sm font-medium'>{SETTING_LABELS[key] || key}</label>
                <Input
                  value={settings[key] || ''}
                  onChange={e => updateValue(key, e.target.value)}
                  placeholder={SETTING_LABELS[key] || key}
                />
              </div>
              <Button onClick={() => handleSave(key)} disabled={saving === key} variant='outline' size='sm'>
                {saving === key ? <RefreshCw className='h-4 w-4 animate-spin' /> : <Save className='h-4 w-4' />}
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
