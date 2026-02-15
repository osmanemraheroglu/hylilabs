import { createFileRoute } from '@tanstack/react-router'
import KeywordStats from '@/features/keywords'

export const Route = createFileRoute('/_authenticated/keywords/')({
  component: KeywordStats,
})
