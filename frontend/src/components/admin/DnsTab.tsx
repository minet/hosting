import { useEffect, useState, useCallback } from 'react'
import { Loader, Trash2 } from 'lucide-react'
import { apiFetch } from '../../api'
import { useToast } from '../../contexts/ToastContext'

interface DnsRecord {
  id: number
  vm_id: number
  vm_name: string | null
  dns_label: string | null
  user_id: string
  created_at: string
}

export default function DnsTab() {
  const [records, setRecords] = useState<DnsRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [revoking, setRevoking] = useState<number | null>(null)
  const { toast } = useToast()

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<{ items: DnsRecord[] }>('/api/dns')
      setRecords(data.items)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Impossible de charger les DNS')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  async function handleRevoke(id: number) {
    setRevoking(id)
    try {
      await apiFetch(`/api/dns/${id}`, { method: 'DELETE' })
      await refresh()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Échec de la révocation')
    } finally {
      setRevoking(null)
    }
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between shrink-0">
        <h1 className="text-base font-semibold text-neutral-800">Enregistrements DNS</h1>
        <span className="text-xs text-neutral-400 font-mono">
          {loading ? 'Chargement…' : `${records.length} enregistrement${records.length !== 1 ? 's' : ''}`}
        </span>
      </div>

      <div className="flex-1 min-h-0 overflow-auto rounded-sm border border-neutral-200 shadow-sm">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10 border-b border-neutral-200 bg-neutral-50">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider w-20 border-r border-neutral-200">VM</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider border-r border-neutral-200">Nom VM</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider border-r border-neutral-200">Label DNS</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider border-r border-neutral-200">Créé le</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-neutral-500 uppercase tracking-wider w-20"></th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-neutral-100">
            {loading && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-neutral-400 text-xs"><Loader size={14} className="animate-spin inline mr-2" />Chargement…</td></tr>
            )}
            {!loading && records.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-neutral-400 text-xs">Aucun DNS custom approuvé</td></tr>
            )}
            {records.map(r => (
              <tr key={r.id} className="hover:bg-neutral-50 transition-colors">
                <td className="px-3 py-2 font-mono text-xs text-neutral-500 border-r border-neutral-100">{r.vm_id}</td>
                <td className="px-3 py-2 text-neutral-700 border-r border-neutral-100">{r.vm_name ?? '—'}</td>
                <td className="px-3 py-2 font-mono text-neutral-800 font-semibold border-r border-neutral-100">{r.dns_label ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-neutral-400 border-r border-neutral-100">
                  {new Date(r.created_at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => handleRevoke(r.id)}
                    disabled={revoking === r.id}
                    className="text-neutral-300 hover:text-red-500 transition-colors cursor-pointer disabled:opacity-40"
                    title="Révoquer"
                  >
                    {revoking === r.id ? <Loader size={14} className="animate-spin" /> : <Trash2 size={14} />}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
