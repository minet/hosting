import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../api'

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
  const qc = useQueryClient()

  const { data, isLoading: loading, error } = useQuery({
    queryKey: ['proxmox-status'],
    queryFn: () => apiFetch<ProxmoxStatus>('/api/cluster/status'),
  })

  const refresh = useCallback(
    () => qc.invalidateQueries({ queryKey: ['proxmox-status'] }),
    [qc],
  )

  return {
    data: data ?? null,
    loading,
    error: error ? (error as Error).message : null,
    refresh,
  }
}
