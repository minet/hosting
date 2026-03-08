import { useState } from 'react'
import { apiFetch } from '../api'

export function useVMShare(
  vmId: string | undefined,
  realmPrefix: string | null,
  setLoadingAction: (action: string | null) => void,
) {
  const [shareOpen, setShareOpen] = useState(false)
  const [shareUsers, setShareUsers] = useState<{ user_id: string; role: string }[]>([])
  const [shareInput, setShareInput] = useState('')

  async function loadShareUsers() {
    if (!vmId) return
    apiFetch<{ users: { user_id: string; role: string }[] }>(`/api/vms/${vmId}/access`)
      .then(r => setShareUsers(r.users.filter(u => u.role !== 'owner')))
      .catch(() => null)
  }

  async function doRevoke(userId: string) {
    if (!vmId) return
    try {
      await apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(userId)}`, { method: 'DELETE' })
      await loadShareUsers()
    } catch { /* ignore */ }
  }

  async function doShare() {
    if (!vmId || !shareInput.trim() || !realmPrefix) return
    const fullUserId = `${realmPrefix}:${shareInput.trim()}`
    setLoadingAction('share')
    try {
      await apiFetch(`/api/vms/${vmId}/access/${encodeURIComponent(fullUserId)}`, { method: 'PUT' })
      setShareInput('')
      await loadShareUsers()
    } catch { /* ignore */ }
    setLoadingAction(null)
  }

  return { shareOpen, setShareOpen, shareUsers, shareInput, setShareInput, loadShareUsers, doShare, doRevoke }
}
