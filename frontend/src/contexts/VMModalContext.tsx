import { createContext, useContext } from 'react'

export const VMModalContext = createContext<() => void>(() => {})

export function useOpenVMModal() {
  return useContext(VMModalContext)
}
