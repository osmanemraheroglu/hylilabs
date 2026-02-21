import {
  Building2,
  Cog,
  LayoutDashboard,
  CalendarClock,
  Mail,
  FolderTree,
  Settings,
  Users,
  UserCog,
  FileUp,
  AudioWaveform,
  Command,
  GalleryVerticalEnd,
} from 'lucide-react'
import { type SidebarData } from '../types'

// Menü öğeleri tanımları
const MENU_ITEMS: Record<string, { title: string; url: string; icon: React.ElementType }> = {
  dashboard: { title: 'Dashboard', url: '/', icon: LayoutDashboard },
  cvTopla: { title: 'CV Topla', url: '/cv-collect', icon: FileUp },
  adaylar: { title: 'Adaylar', url: '/candidates', icon: Users },
  havuzlar: { title: 'Havuzlar', url: '/havuzlar', icon: FolderTree },
  mulakatTakvimi: { title: 'Mulakat Takvimi', url: '/mulakat-takvimi', icon: CalendarClock },
  emailHesaplari: { title: 'Email Hesaplari', url: '/email-hesaplari', icon: Mail },
  kullaniciYonetimi: { title: 'Kullanici Yonetimi', url: '/user-management', icon: UserCog },
  firmaYonetimi: { title: 'Firma Yonetimi', url: '/firma-yonetimi', icon: Building2 },
  adminPanel: { title: 'Admin Panel', url: '/admin-panel', icon: Cog },
  ayarlar: { title: 'Ayarlar', url: '/settings', icon: Settings },
}

// Rol bazlı menü tanımları
const ROLE_MENUS: Record<string, string[]> = {
  super_admin: ['dashboard', 'firmaYonetimi', 'adminPanel', 'ayarlar'],
  company_admin: ['dashboard', 'cvTopla', 'adaylar', 'havuzlar', 'mulakatTakvimi', 'emailHesaplari', 'kullaniciYonetimi', 'ayarlar'],
  user: ['dashboard', 'cvTopla', 'adaylar', 'havuzlar', 'mulakatTakvimi'],
}

// Varsayılan teams
const defaultTeams = [
  {
    name: 'HyliLabs',
    logo: Command,
    plan: 'AI HR Platform',
  },
  {
    name: 'Acme Inc',
    logo: GalleryVerticalEnd,
    plan: 'Enterprise',
  },
  {
    name: 'Acme Corp.',
    logo: AudioWaveform,
    plan: 'Startup',
  },
]

// Dinamik sidebar data fonksiyonu
export function getSidebarData(role: string, userName?: string, userEmail?: string): SidebarData {
  const menuKeys = ROLE_MENUS[role] || ROLE_MENUS['user']
  const items = menuKeys.map(key => MENU_ITEMS[key]).filter(Boolean)

  return {
    user: {
      name: userName || 'Kullanici',
      email: userEmail || '',
      avatar: '',
    },
    teams: defaultTeams,
    navGroups: [
      {
        title: 'Menu',
        items: items,
      },
    ],
  }
}

// Geriye uyumluluk için varsayılan export
export const sidebarData = getSidebarData('user')
