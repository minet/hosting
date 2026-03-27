import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { VMListSchema } from '../schemas'

export interface VM {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
}

export function useVMs() {
  const { data, isLoading } = useQuery({
    queryKey: ['vms'],
    queryFn: () => apiFetch('/api/vms', undefined, VMListSchema),
  })

  return { vms: (data?.items ?? []) as VM[], loading: isLoading }
}
