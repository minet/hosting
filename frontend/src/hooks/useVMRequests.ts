import { useState } from 'react'
import { apiFetch } from '../api'
import { type VMRequest } from '../types/vm'

export function useVMRequests(vmId: string | undefined) {
  const [reqModalOpen, setReqModalOpen] = useState(false)
  const [reqType, setReqType] = useState<'ipv4' | 'dns'>('ipv4')
  const [reqDnsLabel, setReqDnsLabel] = useState('')
  const [reqSaving, setReqSaving] = useState(false)
  const [requests, setRequests] = useState<VMRequest[]>([])

  async function loadRequests() {
    if (!vmId) return
    apiFetch<{ items: VMRequest[] }>(`/api/vms/${vmId}/requests`).then(r => setRequests(r.items)).catch(() => null)
  }

  async function doSubmitRequest() {
    if (!vmId || reqSaving) return
    if (reqType === 'dns' && !reqDnsLabel.trim()) return
    setReqSaving(true)
    try {
      await apiFetch(`/api/vms/${vmId}/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: reqType, dns_label: reqType === 'dns' ? reqDnsLabel.trim().toLowerCase() : null }),
      })
      await loadRequests()
      setReqDnsLabel('')
    } catch { /* ignore */ }
    setReqSaving(false)
  }

  return {
    reqModalOpen, setReqModalOpen,
    reqType, setReqType,
    reqDnsLabel, setReqDnsLabel,
    reqSaving, requests,
    loadRequests, doSubmitRequest,
  }
}
