import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import { useMutationWithToast } from './useMutationWithToast'
import { useVMStatus } from '../contexts/VMStatusContext'

// Expected final status after each action
const TARGET_STATUS: Record<string, string> = {
  start: 'running',
  stop: 'stopped',
  restart: 'running',
}

// Safety timeout: clear pending state if SSE never confirms (ms)
const PENDING_TIMEOUT_MS = 120_000

interface PendingAction {
  targetStatus: string
  /** Set to true once the API has responded OK — only then do we watch the SSE */
  apiResolved: boolean
}

export function useVMActions(vmId: string | undefined) {
  const navigate = useNavigate()
  const [loadingAction, setLoadingAction] = useState<string | null>(null)
  const [showDestroyModal, setShowDestroyModal] = useState(false)

  const pendingRef = useRef<PendingAction | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const vmStatus = useVMStatus(vmId ? Number(vmId) : 0)

  // Watch SSE: clear loadingAction only when the stream confirms the expected state
  useEffect(() => {
    const p = pendingRef.current
    if (!p || !p.apiResolved || !vmStatus) return
    if (vmStatus.status === p.targetStatus) {
      pendingRef.current = null
      clearSafetyTimeout()
      setLoadingAction(null)
    }
    // For restart: if status isn't yet the target (e.g. still stopping),
    // keep waiting — the next SSE event will fire this effect again.
  }, [vmStatus])

  function clearSafetyTimeout() {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }

  function armSafetyTimeout() {
    clearSafetyTimeout()
    timeoutRef.current = setTimeout(() => {
      pendingRef.current = null
      timeoutRef.current = null
      setLoadingAction(null)
    }, PENDING_TIMEOUT_MS)
  }

  const actionMutation = useMutationWithToast<string>({
    mutationFn: (action) =>
      apiFetch(`/api/vms/${vmId}/${action}`, { method: 'POST' }),
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
    // Register pending BEFORE the API call so the effect doesn't fire early
    pendingRef.current = { targetStatus: TARGET_STATUS[action], apiResolved: false }
    try {
      await actionMutation.mutateAsync(action)
      // API responded OK — now wait for SSE confirmation
      pendingRef.current = { targetStatus: TARGET_STATUS[action], apiResolved: true }
      armSafetyTimeout()
    } catch {
      // API failed — clear immediately
      pendingRef.current = null
      clearSafetyTimeout()
      setLoadingAction(null)
    }
  }

  async function doDestroy() {
    if (!vmId || loadingAction) return
    setShowDestroyModal(false)
    setLoadingAction('destroy')
    await destroyMutation.mutateAsync().catch(() => {})
    setLoadingAction(null)
  }

  // Cleanup timeout on unmount
  useEffect(() => () => clearSafetyTimeout(), [])

  return { loadingAction, setLoadingAction, doAction, doDestroy, showDestroyModal, setShowDestroyModal }
}
