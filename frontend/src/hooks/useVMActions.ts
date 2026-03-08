import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'

export function useVMActions(vmId: string | undefined) {
  const navigate = useNavigate()
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [showDestroyModal, setShowDestroyModal] = useState(false)

  async function doAction(action: 'start' | 'stop' | 'restart') {
    if (!vmId || loadingAction) return
    setLoadingAction(action)
    try {
      await apiFetch(`/api/vms/${vmId}/${action}`, { method: 'POST' })
    } catch { /* ignore */ }
    setLoadingAction(null)
  }

  async function doDestroy() {
    if (!vmId || loadingAction) return
    setShowDestroyModal(false)
    setLoadingAction('destroy')
    try {
      await apiFetch(`/api/vms/${vmId}`, { method: 'DELETE' })
      navigate('/')
    } catch { /* ignore */ }
    setLoadingAction(null)
  }

  return { loadingAction, setLoadingAction, doAction, doDestroy, showDestroyModal, setShowDestroyModal }
}
