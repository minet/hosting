import { useState } from 'react'
import { X, Check, AlertTriangle } from 'lucide-react'
import type { AdminRequest } from '../../hooks/useAdminRequests'

function RequestDialog({ request, onClose, onUpdate }: {
  request: AdminRequest
  onClose: () => void
  onUpdate: (id: number, status: 'approved' | 'rejected') => Promise<void>
}) {
  const [loading, setLoading] = useState(false)

  async function handle(status: 'approved' | 'rejected') {
    setLoading(true)
    try {
      await onUpdate(request.id, status)
      onClose()
    } catch {
      // toast already shown by useAdminRequests — keep dialog open
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl p-6 flex flex-col gap-4 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>

        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-neutral-800">
            Requête {request.type === 'ipv4' ? 'IPv4' : 'DNS'}
          </p>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer">
            <X size={16} />
          </button>
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-neutral-50 border border-neutral-100 text-xs">
            <span className="text-neutral-400">VM</span>
            <span className="font-medium text-neutral-700">{request.vm_name ?? request.vm_id}</span>
          </div>
          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-neutral-50 border border-neutral-100 text-xs">
            <span className="text-neutral-400">Type</span>
            <span className="font-mono text-neutral-700">{request.type}</span>
          </div>
          {request.dns_label && (
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-neutral-50 border border-neutral-100 text-xs">
              <span className="text-neutral-400">Label DNS</span>
              <span className="font-mono text-neutral-700">{request.dns_label}</span>
            </div>
          )}
          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-neutral-50 border border-neutral-100 text-xs">
            <span className="text-neutral-400">Soumise le</span>
            <span className="text-neutral-700">{new Date(request.created_at).toLocaleString('fr-FR')}</span>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button
            onClick={() => handle('approved')}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
          >
            <Check size={14} /> Approuver
          </button>
          <button
            onClick={() => handle('rejected')}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
          >
            <X size={14} /> Rejeter
          </button>
        </div>
      </div>
    </div>
  )
}

export default function RequestBadge({ request, onUpdate }: {
  request: AdminRequest
  onUpdate: (id: number, status: 'approved' | 'rejected') => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const isIpv4 = request.type === 'ipv4'

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded-md border transition-colors cursor-pointer whitespace-nowrap ${
          isIpv4
            ? 'bg-blue-50 text-blue-600 border-blue-200 hover:bg-blue-100'
            : 'bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100'
        }`}
      >
        {!isIpv4 && <AlertTriangle size={11} />}
        {isIpv4 ? 'Demande IPv4' : `DNS : ${request.dns_label}`}
      </button>
      {open && <RequestDialog request={request} onClose={() => setOpen(false)} onUpdate={onUpdate} />}
    </>
  )
}
