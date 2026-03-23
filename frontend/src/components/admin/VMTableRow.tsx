import { memo } from 'react'
import { Cpu, MemoryStick, HardDrive } from 'lucide-react'
import type { AdminVM } from '../../hooks/useAdminVMs'
import type { AdminRequest } from '../../hooks/useAdminRequests'
import StatusCell from './StatusCell'
import RequestBadge from './RequestBadge'
import RevealOwner from './RevealOwner'

interface Props {
  vm: AdminVM
  pendingRequests: AdminRequest[] | undefined
  owner: { name: string; email: string | null } | undefined
  expired: boolean
  node: string | null
  onNavigate: (vmId: number) => void
  onUpdateRequest: (id: number, status: 'approved' | 'rejected') => Promise<void>
}

function VMTableRow({ vm, pendingRequests, owner, expired, node, onNavigate, onUpdateRequest }: Props) {
  const ipv4Req = pendingRequests?.find(r => r.type === 'ipv4')
  const dnsReq = pendingRequests?.find(r => r.type === 'dns')

  return (
    <tr onClick={() => onNavigate(vm.vm_id)} className="hover:bg-neutral-50 transition-colors cursor-pointer">
      <td className="px-3 py-2 font-mono text-xs text-neutral-400 border-r border-neutral-100 overflow-hidden">{vm.vm_id}</td>
      <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden">
        <StatusCell vmId={vm.vm_id} />
      </td>
      <td className="px-3 py-2 font-medium text-neutral-800 border-r border-neutral-100 overflow-hidden">
        <span className="block truncate">{vm.name}</span>
      </td>
      <td className="px-3 py-2 text-neutral-500 text-xs border-r border-neutral-100 overflow-hidden">
        <span className="block truncate">{vm.template_name}</span>
      </td>
      <td className="px-3 py-2 border-r border-neutral-100 overflow-hidden">
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 text-violet-600">
            <Cpu size={12} />
            <span className="font-mono font-semibold">{vm.cpu_cores}</span>
            <span className="text-violet-400">core{vm.cpu_cores !== 1 ? 's' : ''}</span>
          </span>
          <span className="flex items-center gap-1 text-blue-600">
            <MemoryStick size={12} />
            <span className="font-mono font-semibold">{Math.round(vm.ram_mb / 1024)}</span>
            <span className="text-blue-400">Go</span>
          </span>
          <span className="flex items-center gap-1 text-emerald-600">
            <HardDrive size={12} />
            <span className="font-mono font-semibold">{vm.disk_gb}</span>
            <span className="text-emerald-400">Go</span>
          </span>
        </div>
      </td>
      <td className="px-3 py-2 font-mono text-xs text-neutral-500 border-r border-neutral-100 overflow-hidden">
        <span className="block truncate">{node ?? <span className="text-neutral-300">—</span>}</span>
      </td>
      <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden" onClick={e => e.stopPropagation()}>
        {ipv4Req
          ? <RequestBadge request={ipv4Req} onUpdate={onUpdateRequest} />
          : <span className="font-mono text-neutral-700">{vm.ipv4 ?? <span className="text-neutral-300">—</span>}</span>
        }
      </td>
      <td className="px-3 py-2 font-mono text-xs text-neutral-500 border-r border-neutral-100 overflow-hidden">
        <span className="block truncate" title={vm.ipv6 ?? undefined}>{vm.ipv6 ?? <span className="text-neutral-300">—</span>}</span>
      </td>
      <td className="px-3 py-2 font-mono text-xs text-neutral-400 border-r border-neutral-100 overflow-hidden">
        <span className="block truncate">{vm.mac ?? <span className="text-neutral-300">—</span>}</span>
      </td>
      <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden" onClick={e => e.stopPropagation()}>
        {dnsReq
          ? <RequestBadge request={dnsReq} onUpdate={onUpdateRequest} />
          : <span className="font-mono text-neutral-500">{vm.dns ?? <span className="text-neutral-300">—</span>}</span>
        }
      </td>
      <td className="px-3 py-2 overflow-hidden border-r border-neutral-100" onClick={e => e.stopPropagation()}>
        {vm.owner_id ? (
          owner ? (
            <div className="flex flex-col gap-0.5" title={vm.owner_id}>
              <span className="text-xs font-medium text-neutral-700">{owner.name}</span>
              {owner.email && <span className="text-xs text-neutral-400">{owner.email}</span>}
            </div>
          ) : <RevealOwner ownerId={vm.owner_id} />
        ) : <span className="text-neutral-300 text-xs">—</span>}
      </td>
      <td className="px-3 py-2 overflow-hidden text-center">
        {vm.owner_id ? (
          expired
            ? <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-500 border border-red-200">Expiré</span>
            : <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200">OK</span>
        ) : <span className="text-neutral-300 text-xs">—</span>}
      </td>
    </tr>
  )
}

export default memo(VMTableRow)
