import { useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { type VMRequest } from '../types/vm'
import { validateDnsLabel } from '../validation'

export function useVMRequests(vmId: string | undefined) {
  const { toast } = useToast()
  const [reqModalOpen, setReqModalOpen] = useState(false)
  const [reqType, setReqType] = useState<'ipv4' | 'dns'>('ipv4')
  const [reqDnsLabel, setReqDnsLabel] = useState('')
  const [reqSaving, setReqSaving] = useState(false)
  const [requests, setRequests] = useState<VMRequest[]>([])
  const [reqDnsError, setReqDnsError] = useState<string | null>(null)

  async function loadRequests() {
    if (!vmId) return
    apiFetch<{ items: VMRequest[] }>(`/api/vms/${vmId}/requests`)
      .then(r => setRequests(r.items))
      .catch(err => toast(err.message ?? 'Impossible de charger les demandes'))
  }

  async function doSubmitRequest() {
    if (!vmId || reqSaving) return
    if (reqType === 'dns') {
      const err = validateDnsLabel(reqDnsLabel.trim())
      if (err) { setReqDnsError(err); return }
    }
    setReqDnsError(null)
    setReqSaving(true)
    try {
      await apiFetch(`/api/vms/${vmId}/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: reqType, dns_label: reqType === 'dns' ? reqDnsLabel.trim().toLowerCase() : null }),
      })
      await loadRequests()
      setReqDnsLabel('')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Échec de l'envoi de la demande"
      toast(msg)
    }
    setReqSaving(false)
  }

  return {
    reqModalOpen, setReqModalOpen,
    reqType, setReqType,
    reqDnsLabel, setReqDnsLabel,
    reqSaving, requests, reqDnsError,
    loadRequests, doSubmitRequest,
  }
}
