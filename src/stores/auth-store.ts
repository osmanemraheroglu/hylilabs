import { create } from 'zustand'
import { getCookie, setCookie, removeCookie } from '@/lib/cookies'

const ACCESS_TOKEN = 'hylilabs_token'
const API_URL = 'http://***REMOVED***:8000'

interface AuthUser {
  accountNo: string
  email: string
  role: string[]
  exp: number
  ad_soyad?: string
  company_id?: number
}

interface AuthState {
  auth: {
    user: AuthUser | null
    setUser: (user: AuthUser | null) => void
    accessToken: string
    setAccessToken: (accessToken: string) => void
    resetAccessToken: () => void
    reset: () => void
  }
}

export const useAuthStore = create<AuthState>()((set) => {
  const cookieState = getCookie(ACCESS_TOKEN)
  const initToken = cookieState ? JSON.parse(cookieState) : ''
  return {
    auth: {
      user: null,
      setUser: (user) =>
        set((state) => ({ ...state, auth: { ...state.auth, user } })),
      accessToken: initToken,
      setAccessToken: (accessToken) =>
        set((state) => {
          setCookie(ACCESS_TOKEN, JSON.stringify(accessToken))
          localStorage.setItem('access_token', accessToken)
          return { ...state, auth: { ...state.auth, accessToken } }
        }),
      resetAccessToken: () =>
        set((state) => {
          removeCookie(ACCESS_TOKEN)
          localStorage.removeItem('access_token')
          return { ...state, auth: { ...state.auth, accessToken: '' } }
        }),
      reset: () =>
        set((state) => {
          removeCookie(ACCESS_TOKEN)
          localStorage.removeItem('access_token')
          return {
            ...state,
            auth: { ...state.auth, user: null, accessToken: '' },
          }
        }),
    },
  }
})

/**
 * Uygulama baslarken token varsa /api/auth/me ile kullanici bilgisini yukler.
 * Token gecersizse veya hata olursa logout yapar.
 * 401: Kullanici bulunamadi veya pasif
 * 403: Firma pasif
 */
// Landing page ve auth sayfaları public — token olmadan erişilebilir
const PUBLIC_PATHS = ['/', '/sign-in', '/sign-up', '/otp', '/forgot-password', '/sign-in-2']

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.includes(pathname)
}

export async function initAuth(): Promise<boolean> {
  const token = localStorage.getItem('access_token')

  if (!token) {
    // Token yoksa ve public sayfadaysa → dokunma (landing page, login vb.)
    if (!isPublicPath(window.location.pathname)) {
      window.location.href = '/sign-in'
    }
    return false
  }

  try {
    const response = await fetch(`${API_URL}/api/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      // 401 veya 403 durumunda token sil ve login'e yonlendir
      useAuthStore.getState().auth.reset()
      if (window.location.pathname !== '/sign-in') {
        window.location.href = '/sign-in'
      }
      return false
    }

    const userData = await response.json()

    // User bilgisini store'a kaydet
    const user: AuthUser = {
      accountNo: String(userData.id),
      email: userData.email,
      role: [userData.rol],
      exp: Date.now() + 24 * 60 * 60 * 1000,
      ad_soyad: userData.ad_soyad,
      company_id: userData.company_id,
    }

    useAuthStore.getState().auth.setUser(user)

    // Basarili giris ve sign-in veya landing sayfasindaysa dashboard'a yonlendir
    if (window.location.pathname === '/sign-in' || window.location.pathname === '/') {
      window.location.href = '/dashboard'
    }

    return true

  } catch (error) {
    // Network hatasi veya diger sorunlar
    console.error('Auth initialization failed:', error)
    useAuthStore.getState().auth.reset()
    if (window.location.pathname !== '/sign-in') {
      window.location.href = '/sign-in'
    }
    return false
  }
}
