import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'

export interface CotiseEndedUser {
  id: string | null
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
}

export function useAdminCotiseEnded() {
  const [users, setUsers] = useState<CotiseEndedUser[]>([])
  const [loading, setLoading] = useState(true)
  const { toast } = useToast()

  useEffect(() => {
    apiFetch<CotiseEndedUser[]>('/api/users/cotise-ended')
      .then(setUsers)
      .catch(err => {
        toast(err.message ?? 'Impossible de charger les cotisations expirées')
        setUsers([])
      })
      .finally(() => setLoading(false))
  }, [])

  return { users, loading }
}
