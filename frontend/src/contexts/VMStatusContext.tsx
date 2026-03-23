import { createContext, useContext, useEffect, useRef, useState, useSyncExternalStore, useCallback } from 'react'
import type { ReactNode } from 'react'
import { apiFetch, API_BASE } from '../api'
import { useToast } from './ToastContext'
import { VMListSchema } from '../schemas'

interface VMStatusEntry {
  status: string
  uptime: number | null
  node: string | null
}

export interface VMListItem {
  vm_id: number
  name: string
  role: 'owner' | 'shared' | 'admin'
}

type StatusMap = Map<number, VMStatusEntry>
type Listener = () => void

/** Mutable store for VM statuses — avoids cloning the Map on every SSE event */
class VMStatusStore {
  private map: StatusMap = new Map()
  private listeners = new Set<Listener>()
  private version = 0

  getMap(): StatusMap { return this.map }
  getVersion(): number { return this.version }

  set(vmId: number, entry: VMStatusEntry) {
    const prev = this.map.get(vmId)
    if (prev && prev.status === entry.status && prev.uptime === entry.uptime && prev.node === entry.node) return
    this.map.set(vmId, entry)
    this.version++
    this.notify()
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify() {
    for (const l of this.listeners) l()
  }
}

interface VMStatusCtx {
  store: VMStatusStore
  vms: VMListItem[]
}

export const VMStatusContext = createContext<VMStatusCtx>({
  store: new VMStatusStore(),
  vms: [],
})

export function useVMStatus(vmId: number): VMStatusEntry | undefined {
  const { store } = useContext(VMStatusContext)
  const subscribe = useCallback((cb: () => void) => store.subscribe(cb), [store])
  const getSnapshot = useCallback(() => store.getMap().get(vmId), [store, vmId])
  return useSyncExternalStore(subscribe, getSnapshot)
}

/** Returns the full statuses Map (for AdminPage). Re-renders on any status change. */
export function useAllStatuses(): StatusMap {
  const { store } = useContext(VMStatusContext)
  const subscribe = useCallback((cb: () => void) => store.subscribe(cb), [store])
  // Return version as snapshot to trigger re-render, but the consumer reads the map
  const getSnapshot = useCallback(() => store.getVersion(), [store])
  useSyncExternalStore(subscribe, getSnapshot)
  return store.getMap()
}

export function useVMList(): VMListItem[] {
  return useContext(VMStatusContext).vms
}

export function VMStatusProvider({ children }: { children: ReactNode }) {
  const [store] = useState(() => new VMStatusStore())
  const [vms, setVms] = useState<VMListItem[]>([])
  const knownIdsRef = useRef<Set<number>>(new Set())
  const esRef = useRef<EventSource | null>(null)
  const { toast } = useToast()

  async function refreshVMs() {
    try {
      const data = await apiFetch('/api/vms', undefined, VMListSchema)
      const items = data.items as VMListItem[]
      setVms(items)
      knownIdsRef.current = new Set(items.map(v => v.vm_id))
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Impossible de rafraîchir la liste des VMs'
      toast(msg)
      return false
    }
  }

  function openStream() {
    if (esRef.current) return
    const es = new EventSource(`${API_BASE}/api/vms/status/stream`, { withCredentials: true })
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const { vm_id, status, uptime, node } = JSON.parse(e.data) as { vm_id: number; status: string; uptime: number | null; node: string | null }
        store.set(vm_id, { status, uptime, node: node ?? null })
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

    es.onerror = () => {
      es.close()
      esRef.current = null
      setTimeout(() => {
        refreshVMs().then(ok => { if (ok) openStream() })
      }, 3000)
    }
  }

  useEffect(() => {
    refreshVMs().then(ok => { if (ok) openStream() })
    return () => {
      esRef.current?.close()
      esRef.current = null
    }
  }, [])

  return (
    <VMStatusContext.Provider value={{ store, vms }}>
      {children}
    </VMStatusContext.Provider>
  )
}
