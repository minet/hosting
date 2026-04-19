import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMShare(
  vmId: string | undefined,
  setLoadingAction: (action: string | null) => void,
) {
  const qc = useQueryClient()
  const [shareOpen, setShareOpen] = useState(false)
  const [shareInput, setShareInput] = useState('')

  const shareQuery = useQuery({
    queryKey: ['vm-share', vmId],
    queryFn: () =>
      apiFetch<{ users: { user_id: string; role: string }[] }>(`/api/vms/${vmId}/access`)
        .then(r => r.users.filter(u => u.role !== 'owner')),
    enabled: !!vmId && shareOpen,
  })

  const revokeMutation = useMutationWithToast<string>({
    mutationFn: (memberNumber) =>
      apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(memberNumber)}`, { method: 'DELETE' }),
    invalidate: [['vm-share', vmId ?? ''], ['vms']],
    fallbackError: "Échec de la révocation d'accès",
  })

  const shareMutation = useMutationWithToast({
    mutationFn: () =>
      apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(shareInput.trim())}`, { method: 'PUT' }),
    invalidate: [['vm-share', vmId ?? ''], ['vms']],
    onSuccess: () => setShareInput(''),
    fallbackError: 'Échec du partage',
  })

  async function doRevoke(userId: string) {
    if (!vmId) return
    const memberNumber = userId.split(':').at(-1) ?? userId
    await revokeMutation.mutateAsync(memberNumber).catch(() => {})
  }

  async function doShare() {
    if (!vmId || !shareInput.trim()) return
    setLoadingAction('share')
    await shareMutation.mutateAsync().catch(() => {})
    setLoadingAction(null)
  }

  return {
    shareOpen, setShareOpen,
    shareUsers: shareQuery.data ?? [],
    shareInput, setShareInput,
    loadShareUsers: () => { qc.invalidateQueries({ queryKey: ['vm-share', vmId] }) },
    doShare, doRevoke,
  }
}
