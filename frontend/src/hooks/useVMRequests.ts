import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { type VMRequest } from '../types/vm'
import { validateDnsLabel } from '../validation'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMRequests(vmId: string | undefined) {
  const [reqModalOpen, setReqModalOpen] = useState(false)
  const [reqType, setReqType] = useState<'ipv4' | 'dns'>('ipv4')
  const [reqDnsLabel, setReqDnsLabel] = useState('')
  const [reqDnsError, setReqDnsError] = useState<string | null>(null)

  const requestsQuery = useQuery({
    queryKey: ['vm-requests', vmId],
    queryFn: () => apiFetch<{ items: VMRequest[] }>(`/api/vms/${vmId}/requests`).then(r => r.items),
    enabled: !!vmId,
  })

  const submitMutation = useMutationWithToast({
    mutationFn: () =>
      apiFetch(`/api/vms/${vmId}/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: reqType, dns_label: reqType === 'dns' ? reqDnsLabel.trim().toLowerCase() : null }),
      }),
    invalidate: [['vm-requests', vmId ?? ''], ['admin-requests']],
    onSuccess: () => setReqDnsLabel(''),
    fallbackError: "Échec de l'envoi de la demande",
  })

  async function doSubmitRequest() {
    if (!vmId || submitMutation.isPending) return
    if (reqType === 'dns') {
      const err = validateDnsLabel(reqDnsLabel.trim())
      if (err) { setReqDnsError(err); return }
    }
    setReqDnsError(null)
    await submitMutation.mutateAsync().catch(() => {})
  }

  return {
    reqModalOpen, setReqModalOpen,
    reqType, setReqType,
    reqDnsLabel, setReqDnsLabel,
    reqSaving: submitMutation.isPending,
    requests: requestsQuery.data ?? [],
    reqDnsError,
    loadRequests: () => requestsQuery.refetch(),
    doSubmitRequest,
  }
}
