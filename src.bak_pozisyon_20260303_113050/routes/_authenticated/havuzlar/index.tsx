import { createFileRoute } from '@tanstack/react-router'
import Havuzlar from '@/features/havuzlar'

export const Route = createFileRoute('/_authenticated/havuzlar/')({
  component: Havuzlar,
})
