import { useCallback } from 'react'
import { Loader, RefreshCw, Clock } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api'
import { usePagination } from '../../hooks/usePagination'

interface ExpiredVM {
  vm_id: number
  vm_name: string
  owner_id: string
  owner_username: string | null
  owner_email: string | null
  days_expired: number | null
  days_until_deletion: number | null
  warnings_sent: number
  last_warning_at: string | null
}

function useExpiredVMs() {
  const qc = useQueryClient()
  const { data, isLoading: loading, error } = useQuery({
    queryKey: ['admin-expired-vms'],
    queryFn: () => apiFetch<ExpiredVM[]>('/api/admin/vms/expired'),
  })
  const refresh = useCallback(() => qc.invalidateQueries({ queryKey: ['admin-expired-vms'] }), [qc])
  return { data: data ?? [], loading, error: error ? (error as Error).message : null, refresh }
}

function urgencyColor(daysUntil: number | null): string {
  if (daysUntil === null) return 'text-neutral-400 dark:text-neutral-500'
  if (daysUntil <= 30) return 'text-red-500 dark:text-red-400 font-semibold'
  if (daysUntil <= 60) return 'text-amber-500 dark:text-amber-400'
  return 'text-neutral-600 dark:text-neutral-400'
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function ExpiredVMsTab() {
  const { data, loading, error, refresh } = useExpiredVMs()
  const { shown, hasMore, remaining, showMore } = usePagination(data)

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
          <Clock size={16} className="text-red-400" />
          <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">Cotisations expirées</h1>
          <span className="text-xs text-neutral-400 dark:text-neutral-500">({data.length} VM{data.length > 1 ? 's' : ''})</span>
        </div>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-medium transition-colors cursor-pointer">
          <RefreshCw size={12} /> Actualiser
        </button>
      </div>

      <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm overflow-x-auto shrink-0">
        <table className="w-full text-sm border-collapse min-w-[900px]">
          <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">VM</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Propriétaire</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Expirée depuis</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Suppression dans</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Mails envoyés</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Dernier mail</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {data.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">Aucune VM concernée</td></tr>
            )}
            {shown.map(vm => (
              <tr key={vm.vm_id} className="hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors">
                <td className="px-3 py-2">
                  <div className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{vm.vm_name}</div>
                  <div className="text-[10px] font-mono text-neutral-400 dark:text-neutral-500">#{vm.vm_id}</div>
                </td>
                <td className="px-3 py-2">
                  <div className="text-xs text-neutral-700 dark:text-neutral-300">{vm.owner_username ?? vm.owner_id}</div>
                  {vm.owner_email && <div className="text-[10px] text-neutral-400 dark:text-neutral-500">{vm.owner_email}</div>}
                </td>
                <td className="px-3 py-2 text-xs text-neutral-600 dark:text-neutral-400">
                  {vm.days_expired !== null ? `${vm.days_expired} j` : '—'}
                </td>
                <td className={`px-3 py-2 text-xs ${urgencyColor(vm.days_until_deletion)}`}>
                  {vm.days_until_deletion !== null ? (
                    vm.days_until_deletion === 0 ? 'Éligible à la suppression' : `${vm.days_until_deletion} j`
                  ) : '—'}
                </td>
                <td className="px-3 py-2 text-xs font-mono text-neutral-600 dark:text-neutral-400">
                  {vm.warnings_sent}
                </td>
                <td className="px-3 py-2 text-xs text-neutral-500 dark:text-neutral-400">
                  {formatDate(vm.last_warning_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <button onClick={showMore} className="self-start text-xs text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 underline underline-offset-2 transition-colors">
          Voir {remaining} de plus
        </button>
      )}
    </div>
  )
}
