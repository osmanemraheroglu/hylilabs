import { createFileRoute } from '@tanstack/react-router'
import Synonyms from '@/features/synonyms'

export const Route = createFileRoute('/_authenticated/synonyms/')({
  component: Synonyms,
})
