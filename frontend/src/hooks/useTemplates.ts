import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { TemplateListSchema } from '../schemas'

export interface Template {
  template_id: number
  name: string
  version?: string | null
  min_cpu_cores: number
  min_ram_gb: number
  min_disk_gb: number
  comment?: string | null
}

export function useTemplates() {
  const { data } = useQuery({
    queryKey: ['templates'],
    queryFn: () => apiFetch('/api/templates', undefined, TemplateListSchema),
  })

  return data?.items ?? []
}
