import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMShare(
  vmId: string | undefined,
  realmPrefix: string | null,
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
    mutationFn: (userId) =>
      apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(userId)}`, { method: 'DELETE' }),
    invalidate: [['vm-share', vmId ?? ''], ['vms']],
    fallbackError: "Échec de la révocation d'accès",
  })

  const shareMutation = useMutationWithToast({
    mutationFn: () => {
      const fullUserId = `${realmPrefix}:${shareInput.trim()}`
      return apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(fullUserId)}`, { method: 'PUT' })
    },
    invalidate: [['vm-share', vmId ?? ''], ['vms']],
    onSuccess: () => setShareInput(''),
    fallbackError: 'Échec du partage',
  })

  async function doRevoke(userId: string) {
    if (!vmId) return
    await revokeMutation.mutateAsync(userId).catch(() => {})
  }

  async function doShare() {
    if (!vmId || !shareInput.trim() || !realmPrefix) return
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
