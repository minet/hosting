import { useCallback, useState } from 'react'
import { Loader, RefreshCw, Network, Search, X } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api'
import { useDebounce } from '../../hooks/useDebounce'

interface IPHistoryEntry {
  id: number
  vm_id: number | null
  owner_id: string
  ipv4: string | null
  ipv6: string | null
  assigned_at: string | null
  released_at: string | null
}

function useIPHistory(ip: string, ownerId: string) {
  const qc = useQueryClient()
  const params = new URLSearchParams()
  if (ip) params.set('ip', ip)
  if (ownerId) params.set('owner_id', ownerId)
  const url = `/api/admin/ip-history${params.toString() ? '?' + params.toString() : ''}`

  const { data, isLoading: loading, error } = useQuery({
    queryKey: ['admin-ip-history', ip, ownerId],
    queryFn: () => apiFetch<IPHistoryEntry[]>(url),
  })
  const refresh = useCallback(
    () => qc.invalidateQueries({ queryKey: ['admin-ip-history'] }),
    [qc],
  )
  return { data: data ?? [], loading, error: error ? (error as Error).message : null, refresh }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function IPHistoryTab() {
  const [ipFilter, setIpFilter] = useState('')
  const [ownerFilter, setOwnerFilter] = useState('')
  const debouncedIp = useDebounce(ipFilter, 300)
  const debouncedOwner = useDebounce(ownerFilter, 300)
  const { data, loading, error, refresh } = useIPHistory(debouncedIp, debouncedOwner)

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <p className="text-sm text-red-500">{error}</p>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-xs font-semibold transition-colors cursor-pointer">
          <RefreshCw size={12} /> Réessayer
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 h-full overflow-auto">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Network size={16} className="text-blue-400" />
          <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">Historique IP</h1>
          {!loading && <span className="text-xs text-neutral-400 dark:text-neutral-500">({data.length})</span>}
        </div>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-medium transition-colors cursor-pointer">
          <RefreshCw size={12} /> Actualiser
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400 dark:text-neutral-500 pointer-events-none" />
          <input
            value={ipFilter}
            onChange={e => setIpFilter(e.target.value)}
            placeholder="Filtrer par IP…"
            className="pl-7 pr-7 py-1.5 text-xs border border-neutral-200 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 placeholder-neutral-400 dark:placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-blue-400 w-44"
          />
          {ipFilter && (
            <button onClick={() => setIpFilter('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200">
              <X size={11} />
            </button>
          )}
        </div>
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400 dark:text-neutral-500 pointer-events-none" />
          <input
            value={ownerFilter}
            onChange={e => setOwnerFilter(e.target.value)}
            placeholder="Filtrer par owner ID…"
            className="pl-7 pr-7 py-1.5 text-xs border border-neutral-200 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 placeholder-neutral-400 dark:placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-blue-400 w-52"
          />
          {ownerFilter && (
            <button onClick={() => setOwnerFilter('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200">
              <X size={11} />
            </button>
          )}
        </div>
      </div>

      <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm overflow-x-auto shrink-0">
        <table className="w-full text-sm border-collapse min-w-[900px]">
          <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">VM ID</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Owner</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">IPv4</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">IPv6</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Attribuée le</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Libérée le</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {loading && (
              <tr><td colSpan={6} className="px-4 py-10 text-center"><Loader size={14} className="animate-spin inline text-neutral-400" /></td></tr>
            )}
            {!loading && data.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">Aucune entrée</td></tr>
            )}
            {!loading && data.map(entry => (
              <tr key={entry.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors">
                <td className="px-3 py-2 text-xs font-mono text-neutral-500 dark:text-neutral-400">
                  {entry.vm_id !== null ? `#${entry.vm_id}` : <span className="text-neutral-300 dark:text-neutral-600">supprimée</span>}
                </td>
                <td className="px-3 py-2 text-xs font-mono text-neutral-600 dark:text-neutral-400 truncate max-w-[180px]">{entry.owner_id}</td>
                <td className="px-3 py-2 text-xs font-mono text-neutral-700 dark:text-neutral-300">{entry.ipv4 ?? '—'}</td>
                <td className="px-3 py-2 text-xs font-mono text-neutral-500 dark:text-neutral-400 truncate max-w-[200px]">{entry.ipv6 ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-neutral-500 dark:text-neutral-400">{formatDate(entry.assigned_at)}</td>
                <td className="px-3 py-2 text-xs">
                  {entry.released_at
                    ? <span className="text-neutral-500 dark:text-neutral-400">{formatDate(entry.released_at)}</span>
                    : <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">active</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
