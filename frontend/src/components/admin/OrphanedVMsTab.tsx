import { useCallback, useState } from 'react'
import { Loader, RefreshCw, AlertTriangle, Trash2 } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api'
import { usePagination } from '../../hooks/usePagination'

function ConfirmDeleteModal({ vmid, vmName, onConfirm, onClose, loading }: {
  vmid: number
  vmName: string | null
  onConfirm: () => void
  onClose: () => void
  loading: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-8 flex flex-col items-center gap-4 max-w-xs w-full mx-4" onClick={e => e.stopPropagation()}>
        <img src="/assets/pinguins/PinguinAccesRefused.svg" alt="" className="w-24 h-24" />
        <div className="text-center">
          <p className="text-base font-bold text-neutral-800 dark:text-neutral-200">
            Supprimer <span className="text-red-500">{vmName ?? `#${vmid}`}</span> ?
          </p>
          <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
            Cette VM sera supprimée définitivement de Proxmox. Aucun enregistrement en base.
          </p>
        </div>
        <div className="flex gap-3 w-full">
          <button onClick={onClose} disabled={loading}
            className="flex-1 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer disabled:opacity-40">
            Annuler
          </button>
          <button onClick={onConfirm} disabled={loading}
            className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer flex items-center justify-center gap-2">
            {loading ? <Loader size={14} className="animate-spin" /> : <Trash2 size={14} />}
            Supprimer
          </button>
        </div>
      </div>
    </div>
  )
}

interface OrphanedVM {
  vmid: number
  name: string | null
  node: string | null
  status: string | null
  tags: string
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
  const { shown, hasMore, remaining, showMore } = usePagination(data)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [confirmVm, setConfirmVm] = useState<OrphanedVM | null>(null)

  async function handleDelete() {
    if (!confirmVm) return
    setDeleting(confirmVm.vmid)
    setDeleteError(null)
    try {
      await apiFetch(`/api/admin/vms/orphaned/${confirmVm.vmid}`, { method: 'DELETE' })
      setConfirmVm(null)
      refresh()
    } catch (e) {
      setDeleteError((e as Error).message)
      setConfirmVm(null)
    } finally {
      setDeleting(null)
    }
  }

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
      {confirmVm && (
        <ConfirmDeleteModal
          vmid={confirmVm.vmid}
          vmName={confirmVm.name}
          onConfirm={handleDelete}
          onClose={() => setConfirmVm(null)}
          loading={deleting === confirmVm.vmid}
        />
      )}
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
        VMs présentes sur le cluster mais absentes de la base de données (ni VM utilisateur, ni template).
      </p>

      {deleteError && (
        <p className="text-xs text-red-500 shrink-0">{deleteError}</p>
      )}

      <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm overflow-x-auto shrink-0">
        <table className="w-full text-sm border-collapse min-w-[500px]">
          <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">VMID</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Nom</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Nœud</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Statut</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Tags</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {data.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">Aucune VM orpheline</td></tr>
            )}
            {shown.map(vm => (
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
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => setConfirmVm(vm)}
                    disabled={deleting === vm.vmid}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold text-red-500 hover:bg-red-50 dark:hover:bg-red-950 border border-red-200 dark:border-red-800 transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                  >
                    {deleting === vm.vmid
                      ? <Loader size={10} className="animate-spin" />
                      : <Trash2 size={10} />
                    }
                    Supprimer
                  </button>
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
