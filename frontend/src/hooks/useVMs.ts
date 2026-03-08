import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export interface VM {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
}

export function useVMs() {
  const [vms, setVMs] = useState<VM[]>([])

  useEffect(() => {
    apiFetch<{ items: VM[] }>('/api/vms')
      .then(data => setVMs(data.items))
      .catch(() => null)
  }, [])

  return vms
}
