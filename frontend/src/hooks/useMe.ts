import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { MeSchema, type Me } from '../schemas'

export type { Me }

type State =
  | { status: 'loading' }
  | { status: 'authenticated'; me: Me }
  | { status: 'unauthenticated' }

export function useMe(): State & { refresh: () => void } {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    setState({ status: 'loading' })
    apiFetch('/api/auth/me', undefined, MeSchema)
      .then((me) => setState({ status: 'authenticated', me }))
      .catch(() => setState({ status: 'unauthenticated' }))
  }, [tick])

  return { ...state, refresh: () => setTick((t) => t + 1) }
}
