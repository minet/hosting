import { useEffect, useState, useCallback } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'

export interface AdminRequest {
  id: number
  vm_id: number
  user_id: string
  type: 'ipv4' | 'dns'
  dns_label: string | null
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  vm_name: string | null
}

export function useAdminRequests() {
  const [requests, setRequests] = useState<AdminRequest[]>([])
  const { toast } = useToast()

  const refresh = useCallback(() => {
    apiFetch<{ items: AdminRequest[] }>('/api/requests')
      .then(data => setRequests(data.items))
      .catch(err => toast(err.message ?? 'Impossible de charger les demandes'))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  async function updateRequest(id: number, status: 'approved' | 'rejected') {
    try {
      await apiFetch(`/api/requests/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      refresh()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Échec de la mise à jour de la demande'
      toast(msg)
    }
  }

  // Map vm_id → pending requests
  const pendingByVm = new Map<number, AdminRequest[]>()
  for (const r of requests) {
    if (r.status === 'pending') {
      const list = pendingByVm.get(r.vm_id) ?? []
      list.push(r)
      pendingByVm.set(r.vm_id, list)
    }
  }

  return { requests, pendingByVm, updateRequest }
}
