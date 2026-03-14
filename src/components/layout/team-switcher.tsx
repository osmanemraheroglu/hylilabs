import * as React from 'react'
import {
  SidebarMenu,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { Logo } from '@/assets/logo'

type TeamSwitcherProps = {
  teams: {
    name: string
    logo: React.ElementType | null
    plan: string
  }[]
}

export function TeamSwitcher({ teams }: TeamSwitcherProps) {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <div className='flex items-center justify-center px-2 py-2'>
          <Logo size='sm' />
        </div>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
