import { cn } from '@/lib/utils'

interface LogoProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'h-4',
  md: 'h-6',
  lg: 'h-8',
}

const textSizeClasses = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg',
}

export function Logo({ className = '', size = 'md' }: LogoProps) {
  return (
    <div className={cn('flex items-center gap-1', sizeClasses[size], className)}>
      <svg viewBox="0 0 24 24" fill="none" className={cn('h-full w-auto', sizeClasses[size])}>
        <circle cx="12" cy="12" r="10" fill="#4F46E5" />
        <text x="12" y="16" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">H</text>
      </svg>
      <span className={cn('font-bold text-primary', textSizeClasses[size])}>HyliLabs</span>
    </div>
  )
}

export default Logo
