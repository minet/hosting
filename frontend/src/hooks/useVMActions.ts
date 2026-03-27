import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMActions(vmId: string | undefined) {
  const navigate = useNavigate()
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [showDestroyModal, setShowDestroyModal] = useState(false)

  const actionMutation = useMutationWithToast<string>({
    mutationFn: (action) =>
      apiFetch(`/api/vms/${vmId}/${action}`, { method: action === 'destroy' ? 'DELETE' : 'POST' }),
    invalidate: [['vms']],
    fallbackError: "Échec de l'action",
  })

  const destroyMutation = useMutationWithToast({
    mutationFn: () => apiFetch(`/api/vms/${vmId}`, { method: 'DELETE' }),
    invalidate: [['vms']],
    onSuccess: () => navigate('/'),
    fallbackError: 'Échec de la suppression',
  })

  async function doAction(action: 'start' | 'stop' | 'restart') {
    if (!vmId || loadingAction) return
    setLoadingAction(action)
    await actionMutation.mutateAsync(action).catch(() => {})
    setLoadingAction(null)
  }

  async function doDestroy() {
    if (!vmId || loadingAction) return
    setShowDestroyModal(false)
    setLoadingAction('destroy')
    await destroyMutation.mutateAsync().catch(() => {})
    setLoadingAction(null)
  }

  return { loadingAction, setLoadingAction, doAction, doDestroy, showDestroyModal, setShowDestroyModal }
}
