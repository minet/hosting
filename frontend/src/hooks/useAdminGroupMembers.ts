import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export interface GroupMember {
  id: string | null
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
}

export function useAdminGroupMembers(endpoint: string) {
  const [users, setUsers] = useState<GroupMember[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<GroupMember[]>(endpoint)
      .then(setUsers)
      .catch(() => setUsers([]))
      .finally(() => setLoading(false))
  }, [endpoint])

  return { users, loading }
}
