import { X } from 'lucide-react'

type Request = { id: number; type: string; dns_label: string | null; status: string; created_at: string }

interface Props {
  vmNetwork: { ipv4: string | null } | null
  requests: Request[]
  reqType: 'ipv4' | 'dns'
  setReqType: (t: 'ipv4' | 'dns') => void
  reqDnsLabel: string
  setReqDnsLabel: (v: string) => void
  reqSaving: boolean
  onClose: () => void
  onSubmit: () => void
}

export default function RequestModal({ vmNetwork, requests, reqType, setReqType, reqDnsLabel, setReqDnsLabel, reqSaving, onClose, onSubmit }: Props) {
  const hasActiveIpv4 = vmNetwork?.ipv4 !== null || requests.some(r => r.type === 'ipv4' && r.status !== 'rejected')
  const hasActiveDns = requests.some(r => r.type === 'dns' && r.status !== 'rejected')
  const canRequest = (reqType === 'ipv4' && !hasActiveIpv4) || (reqType === 'dns' && !hasActiveDns)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl p-6 flex flex-col gap-4 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-neutral-800">Faire une demande</p>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer"><X size={16} /></button>
        </div>

        {requests.length > 0 && (
          <div className="flex flex-col gap-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">Demandes précédentes</p>
            {requests.map(r => {
              const statusColor = r.status === 'approved' ? 'text-emerald-600 bg-emerald-50' : r.status === 'rejected' ? 'text-red-500 bg-red-50' : 'text-amber-600 bg-amber-50'
              return (
                <div key={r.id} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-neutral-50 border border-neutral-100 text-xs">
                  <span className="flex-1 text-neutral-600">{r.type === 'ipv4' ? 'IPv4' : `DNS : ${r.dns_label}`}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${statusColor}`}>{r.status}</span>
                </div>
              )
            })}
          </div>
        )}

        <div className="flex flex-col gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-1.5">Type de demande</p>
            <div className="flex gap-2">
              <button onClick={() => setReqType('ipv4')}
                className={`flex-1 py-2 rounded-lg border text-xs font-semibold transition-colors cursor-pointer ${reqType === 'ipv4' ? 'bg-neutral-900 border-neutral-900 text-white' : 'border-neutral-200 text-neutral-600 hover:bg-neutral-50'}`}>
                Adresse IPv4
              </button>
              <button onClick={() => setReqType('dns')}
                className={`flex-1 py-2 rounded-lg border text-xs font-semibold transition-colors cursor-pointer ${reqType === 'dns' ? 'bg-neutral-900 border-neutral-900 text-white' : 'border-neutral-200 text-neutral-600 hover:bg-neutral-50'}`}>
                Nom DNS
              </button>
            </div>
          </div>

          {!canRequest && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
              {reqType === 'ipv4'
                ? vmNetwork?.ipv4 ? 'Cette VM a déjà une adresse IPv4.' : 'Une demande IPv4 est déjà en cours.'
                : 'Une demande DNS est déjà en cours.'}
            </p>
          )}

          {canRequest && reqType === 'dns' && (
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">Sous-domaine souhaité</label>
              <div className="flex items-center border border-neutral-200 rounded-md overflow-hidden focus-within:ring-1 focus-within:ring-blue-300">
                <input
                  autoFocus
                  value={reqDnsLabel}
                  onChange={e => setReqDnsLabel(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                  placeholder="mon-serveur"
                  className="flex-1 px-3 py-1.5 text-sm font-mono focus:outline-none"
                />
                <span className="px-2 py-1.5 text-xs text-neutral-400 bg-neutral-50 border-l border-neutral-200 whitespace-nowrap">.h.minet.net</span>
              </div>
            </div>
          )}

          {canRequest && reqType === 'ipv4' && (
            <p className="text-xs text-neutral-500">Une adresse IPv4 publique sera attribuée manuellement par l'équipe MiNET suite à votre demande.</p>
          )}
        </div>

        <div className="flex gap-3 pt-1">
          <button onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-neutral-200 text-sm font-semibold text-neutral-600 hover:bg-neutral-50 transition-colors cursor-pointer">
            Fermer
          </button>
          {canRequest && (
            <button onClick={onSubmit} disabled={reqSaving || (reqType === 'dns' && !reqDnsLabel.trim())}
              className="flex-1 py-2 rounded-lg bg-neutral-900 hover:bg-neutral-700 text-white text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer">
              {reqSaving ? '…' : 'Envoyer'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
