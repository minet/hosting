import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { VMListSchema } from '../schemas'

export interface AdminVM {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
  cpu_cores: number
  ram_mb: number
  disk_gb: number
  template_id: number
  template_name: string
  ipv4: string | null
  ipv6: string | null
  mac: string | null
  owner_id: string | null
  dns: string | null
}

export function useAdminVMs() {
  const [vms, setVMs] = useState<AdminVM[]>([])
  const [loading, setLoading] = useState(true)
  const { toast } = useToast()

  function refresh() {
    apiFetch('/api/vms', undefined, VMListSchema)
      .then(data => setVMs(data.items as AdminVM[]))
      .catch(err => toast(err.message ?? 'Impossible de charger les VMs'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  return { vms, loading, refresh }
}
