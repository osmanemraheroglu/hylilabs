import { createFileRoute } from '@tanstack/react-router'
import CvCollect from '@/features/cv-collect'

export const Route = createFileRoute('/_authenticated/cv-collect/')({
  component: CvCollect,
})
