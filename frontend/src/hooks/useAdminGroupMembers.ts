import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api'

export interface GroupMember {
  id: string | null
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
}

export function useAdminGroupMembers(endpoint: string) {
  const { data: users = [], isLoading: loading } = useQuery({
    queryKey: ['admin-group', endpoint],
    queryFn: () => apiFetch<GroupMember[]>(endpoint),
  })

  return { users, loading }
}
