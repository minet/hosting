import { useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'

export function useVMShare(
  vmId: string | undefined,
  realmPrefix: string | null,
  setLoadingAction: (action: string | null) => void,
) {
  const { toast } = useToast()
  const [shareOpen, setShareOpen] = useState(false)
  const [shareUsers, setShareUsers] = useState<{ user_id: string; role: string }[]>([])
  const [shareInput, setShareInput] = useState('')

  async function loadShareUsers() {
    if (!vmId) return
    apiFetch<{ users: { user_id: string; role: string }[] }>(`/api/vms/${vmId}/access`)
      .then(r => setShareUsers(r.users.filter(u => u.role !== 'owner')))
      .catch(err => toast(err.message ?? 'Impossible de charger les accès'))
  }

  async function doRevoke(userId: string) {
    if (!vmId) return
    try {
      await apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(userId)}`, { method: 'DELETE' })
      await loadShareUsers()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Échec de la révocation d'accès"
      toast(msg)
    }
  }

  async function doShare() {
    if (!vmId || !shareInput.trim() || !realmPrefix) return
    const fullUserId = `${realmPrefix}:${shareInput.trim()}`
    setLoadingAction('share')
    try {
      await apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(fullUserId)}`, { method: 'PUT' })
      setShareInput('')
      await loadShareUsers()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Échec du partage"
      toast(msg)
    }
    setLoadingAction(null)
  }

  return { shareOpen, setShareOpen, shareUsers, shareInput, setShareInput, loadShareUsers, doShare, doRevoke }
}
