import { useEffect, useState } from 'react'
import { apiFetch } from './api'

export interface Me {
  sub: string | null
  user_id: string | null
  username: string | null
  email: string | null
  nom: string | null
  prenom: string | null
  departure_date: string | null
  groups: string[]
  is_admin: boolean
  cotise_end_ms: number | null
}

type State =
  | { status: 'loading' }
  | { status: 'authenticated'; me: Me }
  | { status: 'unauthenticated' }

export function useMe(): State {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    apiFetch<Me>('/api/auth/me')
      .then((me) => setState({ status: 'authenticated', me }))
      .catch(() => setState({ status: 'unauthenticated' }))
  }, [])

  return state
}
