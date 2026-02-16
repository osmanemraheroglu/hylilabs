import { createFileRoute } from '@tanstack/react-router'
import AdminPanel from '@/features/admin-panel'

export const Route = createFileRoute('/_authenticated/admin-panel/')({
  component: AdminPanel,
})
