import { useCallback } from 'react'
import { Loader, RefreshCw, AlertTriangle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api'

interface OrphanedVM {
  vmid: number
  name: string | null
  node: string | null
  status: string | null
  tags: string
  in_db: boolean
  has_env_tag: boolean
}

function useOrphanedVMs() {
  const qc = useQueryClient()
  const { data, isLoading: loading, error } = useQuery({
    queryKey: ['admin-orphaned-vms'],
    queryFn: () => apiFetch<OrphanedVM[]>('/api/admin/vms/orphaned'),
  })
  const refresh = useCallback(() => qc.invalidateQueries({ queryKey: ['admin-orphaned-vms'] }), [qc])
  return { data: data ?? [], loading, error: error ? (error as Error).message : null, refresh }
}

export default function OrphanedVMsTab() {
  const { data, loading, error, refresh } = useOrphanedVMs()

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-neutral-400 dark:text-neutral-500 text-sm">
        <Loader size={16} className="animate-spin mr-2" /> Chargement…
      </div>
    )
  }

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
          <AlertTriangle size={16} className="text-amber-500" />
          <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">VMs orphelines</h1>
          <span className="text-xs text-neutral-400 dark:text-neutral-500">({data.length})</span>
        </div>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-medium transition-colors cursor-pointer">
          <RefreshCw size={12} /> Actualiser
        </button>
      </div>

      <p className="text-xs text-neutral-500 dark:text-neutral-400 shrink-0">
        VMs présentes sur le cluster Proxmox mais absentes de l'application ou sans tag <code className="font-mono bg-neutral-100 dark:bg-neutral-800 px-1 rounded">preprod</code>/<code className="font-mono bg-neutral-100 dark:bg-neutral-800 px-1 rounded">prod</code>.
      </p>

      <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm overflow-x-auto shrink-0">
        <table className="w-full text-sm border-collapse min-w-[700px]">
          <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">VMID</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Nom</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Nœud</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Statut</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Tags</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">En base</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Tag env</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {data.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">Aucune VM orpheline</td></tr>
            )}
            {data.map(vm => (
              <tr key={vm.vmid} className="hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors">
                <td className="px-3 py-2 font-mono text-xs text-neutral-700 dark:text-neutral-300">{vm.vmid}</td>
                <td className="px-3 py-2 text-xs font-medium text-neutral-700 dark:text-neutral-300">{vm.name ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-neutral-500 dark:text-neutral-400">{vm.node ?? '—'}</td>
                <td className="px-3 py-2 text-xs">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${vm.status === 'running' ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-700'}`}>
                    {vm.status ?? '—'}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs font-mono text-neutral-500 dark:text-neutral-400">{vm.tags || '—'}</td>
                <td className="px-3 py-2 text-xs">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${vm.in_db ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-950 text-red-500 dark:text-red-400 border border-red-200 dark:border-red-800'}`}>
                    {vm.in_db ? 'oui' : 'non'}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${vm.has_env_tag ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800'}`}>
                    {vm.has_env_tag ? 'oui' : 'non'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
