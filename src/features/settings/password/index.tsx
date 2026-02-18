import { useState } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { ContentSection } from '../components/content-section'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const passwordFormSchema = z.object({
  currentPassword: z.string().min(1, 'Mevcut sifre gerekli'),
  newPassword: z.string().min(8, 'Yeni sifre en az 8 karakter olmali'),
  confirmPassword: z.string().min(1, 'Sifre tekrari gerekli'),
}).refine((data) => data.newPassword === data.confirmPassword, {
  message: 'Sifreler eslesmiyor',
  path: ['confirmPassword'],
})

type PasswordFormValues = z.infer<typeof passwordFormSchema>

export function SettingsPassword() {
  const [loading, setLoading] = useState(false)

  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordFormSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
  })

  async function onSubmit(data: PasswordFormValues) {
    setLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`${API_URL}/api/auth/change-password`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: data.currentPassword,
          new_password: data.newPassword,
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Sifre degistirilemedi')
      }

      toast.success('Sifre basariyla degistirildi')
      form.reset()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Bir hata olustu'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <ContentSection
      title='Sifre Degistir'
      desc='Hesabinizin sifresini guncelleyin.'
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-6 max-w-md'>
          <FormField
            control={form.control}
            name='currentPassword'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Mevcut Sifre</FormLabel>
                <FormControl>
                  <Input type='password' placeholder='Mevcut sifreniz' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='newPassword'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Yeni Sifre</FormLabel>
                <FormControl>
                  <Input type='password' placeholder='En az 8 karakter' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name='confirmPassword'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Yeni Sifre (Tekrar)</FormLabel>
                <FormControl>
                  <Input type='password' placeholder='Yeni sifrenizi tekrar girin' {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type='submit' disabled={loading}>
            {loading ? 'Kaydediliyor...' : 'Sifreyi Degistir'}
          </Button>
        </form>
      </Form>
    </ContentSection>
  )
}
