import logoPng from './logo.png'
import { cn } from '@/lib/utils'

interface LogoProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
}

export function Logo({ className = '', size = 'md' }: LogoProps) {
  return (
    <img
      src={logoPng}
      alt="HyliLabs Logo"
      className={cn('object-contain', sizeClasses[size], className)}
    />
  )
}

export default Logo
