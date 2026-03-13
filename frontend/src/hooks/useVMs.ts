import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { VMListSchema } from '../schemas'

export interface VM {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
}

export function useVMs() {
  const [vms, setVMs] = useState<VM[]>([])
  const [loading, setLoading] = useState(true)
  const { toast } = useToast()

  useEffect(() => {
    apiFetch('/api/vms', undefined, VMListSchema)
      .then(data => setVMs(data.items as VM[]))
      .catch(err => toast(err.message ?? 'Impossible de charger les VMs'))
      .finally(() => setLoading(false))
  }, [])

  return { vms, loading }
}
