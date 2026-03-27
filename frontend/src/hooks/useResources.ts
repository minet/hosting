import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { ResourcesSchema } from '../schemas'

export function useResources() {
  const { data } = useQuery({
    queryKey: ['resources'],
    queryFn: () => apiFetch('/api/users/me/resources', undefined, ResourcesSchema),
  })

  return data ?? null
}
