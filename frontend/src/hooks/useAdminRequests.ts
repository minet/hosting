import { useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

export function useAdminRequests(onUpdated?: () => void) {
  const qc = useQueryClient()
  const { toast } = useToast()

  const { data: requests = [] } = useQuery({
    queryKey: ['admin-requests'],
    queryFn: async () => {
      const data = await apiFetch<{ items: AdminRequest[] }>('/api/requests')
      return data.items
    },
  })

  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'approved' | 'rejected' }) =>
      apiFetch(`/api/requests/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-requests'] })
      onUpdated?.()
    },
    onError: (err: Error) => {
      toast(err.message ?? 'Échec de la mise à jour de la demande')
    },
  })

  async function updateRequest(id: number, status: 'approved' | 'rejected') {
    await mutation.mutateAsync({ id, status })
  }

  const pendingByVm = useMemo(() => {
    const map = new Map<number, AdminRequest[]>()
    for (const r of requests) {
      if (r.status === 'pending') {
        const list = map.get(r.vm_id) ?? []
        list.push(r)
        map.set(r.vm_id, list)
      }
    }
    return map
  }, [requests])

  return { requests, pendingByVm, updateRequest }
}
