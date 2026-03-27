import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { TemplateListSchema } from '../schemas'

export interface Template {
  template_id: number
  name: string
}

export function useTemplates() {
  const { data } = useQuery({
    queryKey: ['templates'],
    queryFn: () => apiFetch('/api/templates', undefined, TemplateListSchema),
  })

  return data?.items ?? []
}
