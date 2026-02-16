import { createFileRoute } from '@tanstack/react-router'
import MulakatTakvimi from '@/features/mulakat-takvimi'

export const Route = createFileRoute('/_authenticated/mulakat-takvimi/')({
  component: MulakatTakvimi,
})
