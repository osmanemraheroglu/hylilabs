import { createFileRoute } from '@tanstack/react-router'
import EmailHesaplari from '@/features/email-hesaplari'

export const Route = createFileRoute('/_authenticated/email-hesaplari/')({
  component: EmailHesaplari,
})
