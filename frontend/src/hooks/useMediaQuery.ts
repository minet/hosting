import { useSyncExternalStore } from 'react'

export function useMediaQuery(query: string): boolean {
  const mql = typeof window !== 'undefined' ? window.matchMedia(query) : null

  const subscribe = (cb: () => void) => {
    mql?.addEventListener('change', cb)
    return () => mql?.removeEventListener('change', cb)
  }

  return useSyncExternalStore(subscribe, () => mql?.matches ?? false)
}
