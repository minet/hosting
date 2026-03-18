import { Crown, Pencil, Share2 } from 'lucide-react'
import Tooltip from './Tooltip'
import { type VMDetail } from '../types/vm'

export function vmFqdn(vm: { dns: string | null; name: string; vm_id: number }): string {
  if (vm.dns) return vm.dns
  const zone = import.meta.env.VITE_DNS_ZONE || 'h.lan'
  const label = vm.name.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '') || 'vm'
  return `${label}-${vm.vm_id}.${zone}`
}

function formatUptime(seconds: number | null): string {
  if (!seconds) return '0d 0h 0m'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${d}d ${h}h ${m}m`
}

interface Props {
  vm: VMDetail
  status: string | null
  loadingAction: string | null
  running: boolean
  isOwner: boolean
  uptime: number | null
  onOpenDnsRequest: () => void
  onOpenIpRequest: () => void
}

export default function VMInfoCard({ vm, status, loadingAction, running, isOwner, uptime, onOpenDnsRequest, onOpenIpRequest }: Props) {
  return (
    <div className="md:col-span-2 xl:col-span-2 border border-neutral-100 shadow-md rounded-sm bg-white px-5 py-4 flex flex-col gap-4 min-w-0 overflow-hidden">
      <div className="flex items-center gap-2 pb-3 border-b border-neutral-100 min-w-0">
        {loadingAction ? (
          <span className="w-2.5 h-2.5 shrink-0 rounded-full border-2 border-neutral-300 border-t-neutral-600 animate-spin" />
        ) : (
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${running ? 'bg-emerald-400' : 'bg-red-400'}`} />
        )}
        <h1 className="text-base font-bold text-neutral-800 tracking-tight truncate">{vm.name}</h1>
        <span className="text-sm text-neutral-400 font-medium shrink-0">#{vm.vm_id}</span>
        {isOwner ? (
          <Crown size={13} className="text-amber-400 shrink-0" fill="currentColor" strokeWidth={0} />
        ) : (
          <Tooltip tip="Cette VM vous a été partagée" className="shrink-0">
            <Share2 size={13} className="text-blue-400" />
          </Tooltip>
        )}
        <span className={`ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${running ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>
          {status ?? '…'}
        </span>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-6 gap-y-4 w-full flex-1">
        <div className="min-w-0 overflow-hidden">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400">DNS</p>
            {isOwner && (
              <button onClick={onOpenDnsRequest} className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-600 text-[10px] font-semibold transition-colors cursor-pointer">
                <Pencil size={9} />
                Demander
              </button>
            )}
          </div>
          <p className="text-sm font-mono font-semibold text-neutral-800 leading-snug break-all">{vmFqdn(vm)}</p>
        </div>
        <div className="min-w-0 overflow-hidden">
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-1">Template</p>
          <p className="text-sm font-semibold text-neutral-700 break-all">{vm.template.name}</p>
        </div>
        <div className="min-w-0 overflow-hidden">
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-1">Uptime</p>
          <p className="text-sm font-semibold text-neutral-700">{formatUptime(uptime)}</p>
        </div>
        <div className="min-w-0 overflow-hidden">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400">IP</p>
            {isOwner && (
              <button onClick={onOpenIpRequest} className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-600 text-[10px] font-semibold transition-colors cursor-pointer">
                <Pencil size={9} />
                Demander
              </button>
            )}
          </div>
          <p className="text-sm font-mono font-semibold text-neutral-700 leading-snug break-all">{vm.network.ipv6 ?? '—'}</p>
          {vm.network.ipv4 && <p className="text-sm font-mono font-semibold text-neutral-700 leading-snug break-all">{vm.network.ipv4}</p>}
        </div>
      </div>
    </div>
  )
}
