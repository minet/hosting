import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'

export function useVMActions(vmId: string | undefined) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [showDestroyModal, setShowDestroyModal] = useState(false)

  async function doAction(action: 'start' | 'stop' | 'restart') {
    if (!vmId || loadingAction) return
    setLoadingAction(action)
    try {
      await apiFetch(`/api/vms/${vmId}/${action}`, { method: 'POST' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `Échec de l'action ${action}`
      toast(msg)
    }
    setLoadingAction(null)
  }

  async function doDestroy() {
    if (!vmId || loadingAction) return
    setShowDestroyModal(false)
    setLoadingAction('destroy')
    try {
      await apiFetch(`/api/vms/${vmId}`, { method: 'DELETE' })
      navigate('/')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Échec de la suppression'
      toast(msg)
    }
    setLoadingAction(null)
  }

  return { loadingAction, setLoadingAction, doAction, doDestroy, showDestroyModal, setShowDestroyModal }
}
