import { useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api'

export interface AdminTemplate {
  template_id: number
  name: string
  version: string | null
  min_cpu_cores: number
  min_ram_gb: number
  min_disk_gb: number
  comment: string | null
  is_active: boolean
}

export interface AdminTemplateCreatePayload {
  template_id: number
  name: string
  version?: string | null
  min_cpu_cores?: number
  min_ram_gb?: number
  min_disk_gb?: number
  comment?: string | null
}

export interface AdminTemplateUpdatePayload {
  name?: string
  version?: string | null
  min_cpu_cores?: number
  min_ram_gb?: number
  min_disk_gb?: number
  comment?: string | null
  is_active?: boolean
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
    mutationFn: (payload: AdminTemplateCreatePayload) =>
      apiFetch<AdminTemplate>('/api/admin/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates-admin'] }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ template_id, ...fields }: AdminTemplateUpdatePayload & { template_id: number }) =>
      apiFetch<AdminTemplate>(`/api/admin/templates/${template_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['templates-admin'] })
      qc.invalidateQueries({ queryKey: ['templates'] })
    },
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
    (payload: AdminTemplateCreatePayload) => createMutation.mutateAsync(payload),
    [createMutation],
  )

  const update = useCallback(
    (template_id: number, fields: AdminTemplateUpdatePayload) => updateMutation.mutateAsync({ template_id, ...fields }),
    [updateMutation],
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

  return { templates, loading, create, update, remove, toggleActive, refresh }
}
