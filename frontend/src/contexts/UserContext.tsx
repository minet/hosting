import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'
import type { Me } from '../useMe'

const UserContext = createContext<Me | null>(null)

export function UserProvider({ me, children }: { me: Me; children: ReactNode }) {
  return <UserContext.Provider value={me}>{children}</UserContext.Provider>
}

export function useUser(): Me {
  const ctx = useContext(UserContext)
  if (!ctx) throw new Error('useUser must be used inside UserProvider')
  return ctx
}
