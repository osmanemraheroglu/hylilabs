import { cn } from '@/lib/utils'

interface LogoProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const heightClasses = {
  sm: 'h-[72px]',
  md: 'h-[96px]',
  lg: 'h-[144px]',
}

export function Logo({ className = '', size = 'md' }: LogoProps) {
  return (
    <img
      src="/images/Logo_400x120.png"
      alt="HyliLabs"
      className={cn(heightClasses[size], 'w-auto object-contain', className)}
    />
  )
}

export default Logo
