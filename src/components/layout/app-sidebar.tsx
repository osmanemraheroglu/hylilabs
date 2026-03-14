import { useLayout } from '@/context/layout-provider'
import { useAuthStore } from '@/stores/auth-store'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { getSidebarData } from './data/sidebar-data'
import { NavGroup } from './nav-group'
import { NavUser } from './nav-user'
import { TeamSwitcher } from './team-switcher'

export function AppSidebar() {
  const { collapsible, variant } = useLayout()
  const { auth } = useAuthStore()

  // Kullanıcı bilgilerini al
  const userRole = auth.user?.role?.[0] || 'user'
  const userName = auth.user?.ad_soyad || auth.user?.email || 'Kullanici'
  const userEmail = auth.user?.email || ''

  // Rol bazlı sidebar data oluştur
  const data = getSidebarData(userRole, userName, userEmail)

  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      <SidebarHeader>
        <div className='flex items-center justify-between'>
          <TeamSwitcher teams={data.teams} />
          <SidebarTrigger className='mr-2' />
        </div>
      </SidebarHeader>
      <SidebarContent>
        {data.navGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))}
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
