import { createFileRoute } from '@tanstack/react-router'
import SettingsPage from '@/features/settings-page'

export const Route = createFileRoute('/_authenticated/settings-page/')({
  component: SettingsPage,
})
