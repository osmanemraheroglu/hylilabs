import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface LocationBadgeProps {
  status: 'green' | 'yellow' | 'red' | 'gray'
  candidateLocation: string
  positionLocation: string
  matchType: string
}

const statusColors = {
  green: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  red: 'bg-red-500',
  gray: 'bg-gray-400'
}

const getTooltipContent = (
  status: string,
  candidateLocation: string,
  positionLocation: string,
  matchType: string
) => {
  switch (status) {
    case 'green':
      return `✓ Aynı şehir: ${candidateLocation}`
    case 'yellow':
      return `~ Komşu şehir: ${matchType}`
    case 'red':
      return `✗ Eşleşme yok: ${candidateLocation} → ${positionLocation}`
    case 'gray':
    default:
      return 'Lokasyon verisi bulunamadı'
  }
}

export function LocationBadge({
  status,
  candidateLocation,
  positionLocation,
  matchType
}: LocationBadgeProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-2 cursor-default min-w-0">
          <div className={`w-3 h-3 rounded-full shrink-0 ${statusColors[status] || statusColors.gray}`} />
          <span className="text-sm truncate min-w-0 max-w-[150px]">
            {candidateLocation || '-'}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs max-w-[250px]">
        <div className="space-y-1">
          <div className="font-medium">
            {getTooltipContent(status, candidateLocation, positionLocation, matchType)}
          </div>
          {status !== 'gray' && (
            <>
              <div><span className="text-muted-foreground">Aday:</span> {candidateLocation || '-'}</div>
              <div><span className="text-muted-foreground">Pozisyon:</span> {positionLocation || '-'}</div>
              <div><span className="text-muted-foreground">Durum:</span> {matchType}</div>
            </>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
