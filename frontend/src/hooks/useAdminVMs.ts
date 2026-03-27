import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { apiFetch } from '../api'
import { VMListSchema } from '../schemas'

export interface AdminVM {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
  cpu_cores: number
  ram_mb: number
  disk_gb: number
  template_id: number
  template_name: string
  ipv4: string | null
  ipv6: string | null
  mac: string | null
  owner_id: string | null
  dns: string | null
}

export function useAdminVMs() {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['vms'],
    queryFn: () => apiFetch('/api/vms', undefined, VMListSchema),
  })

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['vms'] })
  }, [qc])

  return { vms: (data?.items ?? []) as AdminVM[], loading: isLoading, refresh }
}
