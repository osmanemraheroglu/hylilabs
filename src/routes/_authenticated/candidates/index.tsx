import { createFileRoute } from '@tanstack/react-router'
import Candidates from '@/features/candidates'

export const Route = createFileRoute('/_authenticated/candidates/')({
  component: Candidates,
})
