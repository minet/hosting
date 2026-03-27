import { useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api'

export interface AdminTemplate {
  template_id: number
  name: string
  is_active: boolean
}

export function useAdminTemplates() {
  const qc = useQueryClient()

  const { data: templates = [], isLoading: loading } = useQuery({
    queryKey: ['templates-admin'],
    queryFn: async () => {
      const r = await apiFetch<{ items: AdminTemplate[] }>('/api/admin/templates')
      return r.items
    },
  })

  const createMutation = useMutation({
    mutationFn: ({ template_id, name }: { template_id: number; name: string }) =>
      apiFetch<AdminTemplate>('/api/admin/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id, name }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates-admin'] }),
  })

  const removeMutation = useMutation({
    mutationFn: (template_id: number) =>
      apiFetch<void>(`/api/admin/templates/${template_id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates-admin'] }),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ template_id, is_active }: { template_id: number; is_active: boolean }) =>
      apiFetch<AdminTemplate>(`/api/admin/templates/${template_id}/active`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates-admin'] }),
  })

  const create = useCallback(
    (template_id: number, name: string) => createMutation.mutateAsync({ template_id, name }),
    [createMutation],
  )

  const remove = useCallback(
    (template_id: number) => removeMutation.mutateAsync(template_id),
    [removeMutation],
  )

  const toggleActive = useCallback(
    (template_id: number, is_active: boolean) => toggleActiveMutation.mutateAsync({ template_id, is_active }),
    [toggleActiveMutation],
  )

  const refresh = useCallback(
    () => qc.invalidateQueries({ queryKey: ['templates-admin'] }),
    [qc],
  )

  return { templates, loading, create, remove, toggleActive, refresh }
}
