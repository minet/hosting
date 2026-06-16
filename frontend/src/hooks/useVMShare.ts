import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch, ApiError } from '../api'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMShare(
  vmId: string | undefined,
  setLoadingAction: (action: string | null) => void,
) {
  const { t } = useTranslation('vm')
  const qc = useQueryClient()
  const [shareOpen, setShareOpen] = useState(false)
  const [shareInput, setShareInput] = useState('')
  const [shareError, setShareError] = useState<string | null>(null)

  const shareQuery = useQuery({
    queryKey: ['vm-share', vmId],
    queryFn: () =>
      apiFetch<{ users: { user_id: string; role: string; display_name: string | null }[]; max_shared_users: number }>(`/api/vms/${vmId}/access`),
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
    onSuccess: () => {
      setShareInput('')
      setShareError(null)
    },
    fallbackError: 'Échec du partage',
    suppressErrorToast: (err) => err instanceof ApiError && err.status === 400,
  })

  async function doRevoke(userId: string) {
    if (!vmId) return
    const memberNumber = userId.split(':').at(-1) ?? userId
    await revokeMutation.mutateAsync(memberNumber).catch(() => {})
  }

  async function doShare() {
    if (!vmId || !shareInput.trim()) return
    setLoadingAction('share')
    setShareError(null)
    try {
      await shareMutation.mutateAsync()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        if (err.message === "Maximum number of shared users reached") {
          setShareError(t('share.maxSharedUsersReached'))
        } else {
          setShareError(err.message)
        }
      }
    } finally {
      setLoadingAction(null)
    }
  }

  return {
    shareOpen,
    setShareOpen: (open: boolean) => {
      setShareOpen(open)
      setShareError(null)
    },
    shareUsers: shareQuery.data?.users.filter(u => u.role !== 'owner') ?? [],
    maxSharedUsers: shareQuery.data?.max_shared_users ?? 5,
    shareInput, setShareInput,
    shareError,
    loadShareUsers: () => { qc.invalidateQueries({ queryKey: ['vm-share', vmId] }) },
    doShare, doRevoke,
  }
}
