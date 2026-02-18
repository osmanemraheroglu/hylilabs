import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { useTheme } from '@/context/theme-provider'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { ContentSection } from '../components/content-section'

const themeFormSchema = z.object({
  theme: z.enum(['light', 'dark']),
})

type ThemeFormValues = z.infer<typeof themeFormSchema>

export function SettingsTheme() {
  const { theme, setTheme } = useTheme()

  const form = useForm<ThemeFormValues>({
    resolver: zodResolver(themeFormSchema),
    defaultValues: {
      theme: (theme as 'light' | 'dark') || 'light',
    },
  })

  function onSubmit(data: ThemeFormValues) {
    setTheme(data.theme)
    toast.success('Tema tercihleri guncellendi')
  }

  return (
    <ContentSection
      title='Tema'
      desc='Kontrol paneli icin tema secin.'
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className='space-y-8'>
          <FormField
            control={form.control}
            name='theme'
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tema Secimi</FormLabel>
                <FormMessage />
                <RadioGroup
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                  className='grid max-w-md grid-cols-2 gap-8 pt-2'
                >
                  <FormItem>
                    <FormLabel className='[&:has([data-state=checked])>div]:border-primary'>
                      <FormControl>
                        <RadioGroupItem value='light' className='sr-only' />
                      </FormControl>
                      <div className='items-center rounded-md border-2 border-muted p-1 hover:border-accent cursor-pointer'>
                        <div className='space-y-2 rounded-sm bg-[#ecedef] p-2'>
                          <div className='space-y-2 rounded-md bg-white p-2 shadow-xs'>
                            <div className='h-2 w-[80px] rounded-lg bg-[#ecedef]' />
                            <div className='h-2 w-[100px] rounded-lg bg-[#ecedef]' />
                          </div>
                          <div className='flex items-center space-x-2 rounded-md bg-white p-2 shadow-xs'>
                            <div className='h-4 w-4 rounded-full bg-[#ecedef]' />
                            <div className='h-2 w-[100px] rounded-lg bg-[#ecedef]' />
                          </div>
                          <div className='flex items-center space-x-2 rounded-md bg-white p-2 shadow-xs'>
                            <div className='h-4 w-4 rounded-full bg-[#ecedef]' />
                            <div className='h-2 w-[100px] rounded-lg bg-[#ecedef]' />
                          </div>
                        </div>
                      </div>
                      <span className='block w-full p-2 text-center font-normal'>
                        Acik
                      </span>
                    </FormLabel>
                  </FormItem>
                  <FormItem>
                    <FormLabel className='[&:has([data-state=checked])>div]:border-primary'>
                      <FormControl>
                        <RadioGroupItem value='dark' className='sr-only' />
                      </FormControl>
                      <div className='items-center rounded-md border-2 border-muted bg-popover p-1 hover:bg-accent hover:text-accent-foreground cursor-pointer'>
                        <div className='space-y-2 rounded-sm bg-slate-950 p-2'>
                          <div className='space-y-2 rounded-md bg-slate-800 p-2 shadow-xs'>
                            <div className='h-2 w-[80px] rounded-lg bg-slate-400' />
                            <div className='h-2 w-[100px] rounded-lg bg-slate-400' />
                          </div>
                          <div className='flex items-center space-x-2 rounded-md bg-slate-800 p-2 shadow-xs'>
                            <div className='h-4 w-4 rounded-full bg-slate-400' />
                            <div className='h-2 w-[100px] rounded-lg bg-slate-400' />
                          </div>
                          <div className='flex items-center space-x-2 rounded-md bg-slate-800 p-2 shadow-xs'>
                            <div className='h-4 w-4 rounded-full bg-slate-400' />
                            <div className='h-2 w-[100px] rounded-lg bg-slate-400' />
                          </div>
                        </div>
                      </div>
                      <span className='block w-full p-2 text-center font-normal'>
                        Koyu
                      </span>
                    </FormLabel>
                  </FormItem>
                </RadioGroup>
              </FormItem>
            )}
          />

          <Button type='submit'>Tercihleri Guncelle</Button>
        </form>
      </Form>
    </ContentSection>
  )
}
