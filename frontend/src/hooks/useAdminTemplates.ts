import { useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api'

export interface AdminTemplate {
  template_id: number
  name: string
}

export function useAdminTemplates() {
  const qc = useQueryClient()

  const { data: templates = [], isLoading: loading } = useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const r = await apiFetch<{ items: AdminTemplate[] }>('/api/templates')
      return r.items
    },
  })

  const createMutation = useMutation({
    mutationFn: ({ template_id, name }: { template_id: number; name: string }) =>
      apiFetch<AdminTemplate>('/api/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id, name }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })

  const removeMutation = useMutation({
    mutationFn: (template_id: number) =>
      apiFetch<void>(`/api/templates/${template_id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })

  const create = useCallback(
    (template_id: number, name: string) => createMutation.mutateAsync({ template_id, name }),
    [createMutation],
  )

  const remove = useCallback(
    (template_id: number) => removeMutation.mutateAsync(template_id),
    [removeMutation],
  )

  const refresh = useCallback(
    () => qc.invalidateQueries({ queryKey: ['templates'] }),
    [qc],
  )

  return { templates, loading, create, remove, refresh }
}
