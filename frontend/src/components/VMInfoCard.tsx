import { Crown, Pencil, Share2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation('vm')
  return (
    <div className="md:col-span-2 xl:col-span-2 border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 px-4 py-2.5 flex flex-col gap-2 min-w-0 overflow-hidden">
      <div className="flex items-center gap-2 pb-1.5 border-b border-neutral-100 dark:border-neutral-800 min-w-0">
        {loadingAction ? (
          <span className="w-2.5 h-2.5 shrink-0 rounded-full border-2 border-neutral-300 dark:border-neutral-600 border-t-neutral-600 dark:border-t-neutral-300 animate-spin" />
        ) : (
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${running ? 'bg-emerald-400' : 'bg-red-400'}`} />
        )}
        <h1 className="text-sm font-bold text-neutral-800 dark:text-neutral-200 tracking-tight truncate">{vm.name}</h1>
        <span className="text-xs text-neutral-400 dark:text-neutral-500 font-medium shrink-0">#{vm.vm_id}</span>
        {isOwner ? (
          <Crown size={13} className="text-amber-400 shrink-0" fill="currentColor" strokeWidth={0} />
        ) : (
          <Tooltip tip={t('info.sharedVM')} className="shrink-0">
            <Share2 size={13} className="text-blue-400" />
          </Tooltip>
        )}
        <span className={`ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${running ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400' : 'bg-red-50 dark:bg-red-950 text-red-500 dark:text-red-400'}`}>
          {status ?? '…'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 w-full flex-1 min-w-0 content-start">
        <div className="min-w-0 flex items-baseline gap-1.5 flex-wrap">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500 shrink-0">DNS</p>
          {isOwner && (
            <button onClick={onOpenDnsRequest} className="flex items-center gap-0.5 px-1 py-px rounded bg-blue-50 dark:bg-blue-950 hover:bg-blue-100 dark:hover:bg-blue-900 border border-blue-200 dark:border-blue-700 text-blue-600 dark:text-blue-400 text-[9px] font-semibold transition-colors cursor-pointer shrink-0">
              <Pencil size={8} />
              {t('info.request')}
            </button>
          )}
        </div>
        <div className="min-w-0">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Template</p>
        </div>
        <p className="text-[11px] font-mono font-semibold text-neutral-700 dark:text-neutral-200 leading-tight truncate col-span-1 min-w-0">{vmFqdn(vm)}</p>
        <p className="text-[11px] font-semibold text-neutral-700 dark:text-neutral-300 truncate min-w-0">{vm.template.name}</p>

        <div className="min-w-0">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Uptime</p>
        </div>
        <div className="min-w-0 flex items-baseline gap-1.5 flex-wrap">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500 shrink-0">IP</p>
          {isOwner && (
            <button onClick={onOpenIpRequest} className="flex items-center gap-0.5 px-1 py-px rounded bg-blue-50 dark:bg-blue-950 hover:bg-blue-100 dark:hover:bg-blue-900 border border-blue-200 dark:border-blue-700 text-blue-600 dark:text-blue-400 text-[9px] font-semibold transition-colors cursor-pointer shrink-0">
              <Pencil size={8} />
              {t('info.request')}
            </button>
          )}
        </div>
        <p className="text-[11px] font-semibold text-neutral-700 dark:text-neutral-300">{formatUptime(uptime)}</p>
        <div className="min-w-0">
          <p className="text-[11px] font-mono font-semibold text-neutral-700 dark:text-neutral-300 leading-tight truncate">{vm.network.ipv6 ?? '—'}</p>
          {vm.network.ipv4 && <p className="text-[11px] font-mono font-semibold text-neutral-700 dark:text-neutral-300 leading-tight truncate">{vm.network.ipv4}</p>}
        </div>
      </div>
    </div>
  )
}
