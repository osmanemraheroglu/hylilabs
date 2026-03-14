import { cn } from '@/lib/utils'

interface LogoProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const heightClasses = {
  sm: 'h-6',
  md: 'h-8',
  lg: 'h-12',
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
