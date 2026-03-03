import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface LocationBadgeProps {
  status: 'green' | 'yellow' | 'red'
  candidateLocation: string
  positionLocation: string
  matchType: string
}

const statusColors = {
  green: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  red: 'bg-red-500'
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
        <div className="flex items-center gap-2 cursor-default">
          <div className={`w-3 h-3 rounded-full ${statusColors[status]}`} />
          <span className="text-sm">{candidateLocation || '-'}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs">
        <div className="space-y-1">
          <div><span className="text-muted-foreground">Aday:</span> {candidateLocation || '-'}</div>
          <div><span className="text-muted-foreground">Pozisyon:</span> {positionLocation || '-'}</div>
          <div><span className="text-muted-foreground">Durum:</span> {matchType}</div>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
