import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'

export interface ProxmoxNode {
  node: string
  status: string
  maxcpu: number
  cpu: number
  maxmem: number
  mem: number
  maxdisk: number
  disk: number
  uptime: number
}

export interface ProxmoxStorage {
  storage: string
  node: string
  status: string
  maxdisk: number
  disk: number
  plugintype: string
  content: string
}

export interface ProxmoxVersion {
  version: string
  release: string
  repoid: string
}

export interface ProxmoxStatus {
  nodes: ProxmoxNode[]
  storages: ProxmoxStorage[]
  version: ProxmoxVersion
}

export function useProxmoxStatus() {
  const [data, setData] = useState<ProxmoxStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

  function refresh() {
    setLoading(true)
    setError(null)
    apiFetch<ProxmoxStatus>('/api/cluster/status')
      .then(setData)
      .catch(err => {
        const msg = err.message ?? 'Impossible de charger le statut Proxmox'
        setError(msg)
        toast(msg)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  return { data, loading, error, refresh }
}
