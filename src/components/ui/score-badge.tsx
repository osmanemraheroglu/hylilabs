import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface ScoreBadgeProps {
  score: number          // 0-100
  showLabel?: boolean    // Etiket göster (varsayılan: true)
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

interface ScoreConfig {
  label: string
  color: string
  icon: string
}

/**
 * Puan aralıklarına göre renk ve etiket döndürür
 * 85-100: Mükemmel (koyu yeşil)
 * 70-84:  İyi (açık yeşil)
 * 55-69:  Orta (sarı)
 * 40-54:  Zayıf (turuncu)
 * 0-39:   Uyumsuz (kırmızı)
 */
export const getScoreConfig = (score: number): ScoreConfig => {
  if (score >= 85) return {
    label: 'Mükemmel',
    color: 'bg-green-600 text-white',
    icon: '🟢'
  }
  if (score >= 70) return {
    label: 'İyi',
    color: 'bg-green-500 text-white',
    icon: '🟢'
  }
  if (score >= 55) return {
    label: 'Orta',
    color: 'bg-yellow-500 text-white',
    icon: '🟡'
  }
  if (score >= 40) return {
    label: 'Zayıf',
    color: 'bg-orange-500 text-white',
    icon: '🟠'
  }
  return {
    label: 'Uyumsuz',
    color: 'bg-red-500 text-white',
    icon: '🔴'
  }
}

// Size variants
const sizeClasses = {
  sm: 'text-xs px-2 py-0.5',
  md: 'text-sm px-2.5 py-1',
  lg: 'text-base px-3 py-1.5 font-semibold'
}

/**
 * ScoreBadge - Tek skor gösterim bileşeni
 *
 * Kullanım:
 * <ScoreBadge score={78} />                    // 78 İyi
 * <ScoreBadge score={78} showLabel={false} />  // 78
 * <ScoreBadge score={78} size="lg" />          // Büyük badge
 */
export function ScoreBadge({
  score,
  showLabel = true,
  size = 'sm',
  className
}: ScoreBadgeProps) {
  const config = getScoreConfig(score)

  return (
    <Badge
      className={cn(
        config.color,
        sizeClasses[size],
        'font-medium whitespace-nowrap',
        className
      )}
    >
      {Math.round(score)}
      {showLabel && <span className="ml-1">{config.label}</span>}
    </Badge>
  )
}

export default ScoreBadge
