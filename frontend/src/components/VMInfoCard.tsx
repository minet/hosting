import { Crown, Pencil, Share2 } from 'lucide-react'
import Tooltip from './Tooltip'
import { type VMDetail } from '../types/vm'

function sanitizeDnsLabel(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '') || 'vm'
}

export function vmFqdn(vmName: string, vmId: number): string {
  const zone = import.meta.env.VITE_DNS_ZONE || 'h.lan'
  return `${sanitizeDnsLabel(vmName)}-${vmId}.${zone}`
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
    <div className="md:col-span-2 xl:col-span-2 border border-neutral-100 shadow-md rounded-sm bg-white px-5 py-4 flex flex-col gap-3 h-auto md:h-48 xl:h-auto">
      <div className="flex items-center gap-2 pb-3 border-b border-neutral-100">
        {loadingAction ? (
          <span className="w-2.5 h-2.5 shrink-0 rounded-full border-2 border-neutral-300 border-t-neutral-600 animate-spin" />
        ) : (
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${running ? 'bg-emerald-400' : 'bg-red-400'}`} />
        )}
        <h1 className="text-base font-bold text-neutral-800 tracking-tight">{vm.name}</h1>
        <span className="text-sm text-neutral-400 font-medium">#{vm.vm_id}</span>
        {isOwner ? (
          <Crown size={13} className="text-amber-400 shrink-0" fill="currentColor" strokeWidth={0} />
        ) : (
          <Tooltip tip="Cette VM vous a été partagée" className="shrink-0">
            <Share2 size={13} className="text-blue-400" />
          </Tooltip>
        )}
        <span className={`ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full ${running ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>
          {status ?? '…'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-3">
        <div>
          <div className="flex items-center gap-1 mb-0.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">DNS</p>
            {isOwner && <button onClick={onOpenDnsRequest} className="text-neutral-300 hover:text-neutral-500 cursor-pointer transition-colors"><Pencil size={9} /></button>}
          </div>
          <p className="text-[11px] font-mono font-semibold text-neutral-800 break-all leading-snug">{vmFqdn(vm.name, vm.vm_id)}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">Template</p>
          <p className="text-[11px] font-semibold text-neutral-700">{vm.template.name}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">Uptime</p>
          <p className="text-[11px] font-semibold text-neutral-700">{formatUptime(uptime)}</p>
        </div>
        <div>
          <div className="flex items-center gap-1 mb-0.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">IP</p>
            {isOwner && <button onClick={onOpenIpRequest} className="text-neutral-300 hover:text-neutral-500 cursor-pointer transition-colors"><Pencil size={9} /></button>}
          </div>
          <p className="text-[11px] font-mono font-semibold text-neutral-700 break-all leading-snug">{vm.network.ipv6 ?? '—'}</p>
          {vm.network.ipv4 && <p className="text-[11px] font-mono font-semibold text-neutral-700 leading-snug">{vm.network.ipv4}</p>}
        </div>
      </div>
    </div>
  )
}
