import { createFileRoute } from '@tanstack/react-router'
import FirmaYonetimi from '@/features/firma-yonetimi'

export const Route = createFileRoute('/_authenticated/firma-yonetimi/')({
  component: FirmaYonetimi,
})
