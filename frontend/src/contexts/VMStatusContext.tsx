import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { apiFetch } from '../api'

const API_BASE = import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000`

interface VMStatusEntry {
  status: string
  uptime: number | null
}

export interface VMListItem {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
}

type StatusMap = Map<number, VMStatusEntry>

interface VMStatusCtx {
  statuses: StatusMap
  vms: VMListItem[]
}

const VMStatusContext = createContext<VMStatusCtx>({ statuses: new Map(), vms: [] })

export function useVMStatus(vmId: number): VMStatusEntry | undefined {
  return useContext(VMStatusContext).statuses.get(vmId)
}

export function useVMList(): VMListItem[] {
  return useContext(VMStatusContext).vms
}

export function VMStatusProvider({ children }: { children: ReactNode }) {
  const [statuses, setStatuses] = useState<StatusMap>(new Map())
  const [vms, setVms] = useState<VMListItem[]>([])
  const knownIdsRef = useRef<Set<number>>(new Set())

  async function refreshVMs() {
    try {
      const data = await apiFetch<{ items: VMListItem[] }>('/api/vms')
      setVms(data.items)
      knownIdsRef.current = new Set(data.items.map(v => v.vm_id))
    } catch { /* ignore */ }
  }

  useEffect(() => {
    refreshVMs()

    const es = new EventSource(`${API_BASE}/api/vms/status/stream`, { withCredentials: true })

    es.onmessage = (e) => {
      try {
        const { vm_id, status, uptime } = JSON.parse(e.data) as { vm_id: number; status: string; uptime: number | null }
        setStatuses(prev => {
          const next = new Map(prev)
          next.set(vm_id, { status, uptime })
          return next
        })
        if (!knownIdsRef.current.has(vm_id)) {
          refreshVMs()
        }
      } catch { /* ignore */ }
    }

    es.addEventListener('sync', (e) => {
      try {
        const { vm_ids } = JSON.parse((e as MessageEvent).data) as { vm_ids: number[] }
        const streamIds = new Set(vm_ids)
        for (const id of knownIdsRef.current) {
          if (!streamIds.has(id)) { refreshVMs(); break }
        }
      } catch { /* ignore */ }
    })

    return () => es.close()
  }, [])

  return (
    <VMStatusContext.Provider value={{ statuses, vms }}>
      {children}
    </VMStatusContext.Provider>
  )
}
