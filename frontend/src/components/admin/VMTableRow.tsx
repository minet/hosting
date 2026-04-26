import { memo, useState } from 'react'
import { Cpu, MemoryStick, HardDrive, X, Loader, Trash2, UserPen, FileStack } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { AdminVM } from '../../hooks/useAdminVMs'
import type { AdminRequest } from '../../hooks/useAdminRequests'
import StatusCell from './StatusCell'
import RequestBadge from './RequestBadge'
import RevealOwner from './RevealOwner'
import ConfirmModal from '../ConfirmModal'
import ChangeOwnerModal from './ChangeOwnerModal'
import ChangeTemplateModal from './ChangeTemplateModal'

interface Props {
  vm: AdminVM
  pendingRequests: AdminRequest[] | undefined
  owner: { name: string; email: string | null } | undefined
  expired: boolean
  node: string | null
  onNavigate: (vmId: number) => void
  onUpdateRequest: (id: number, status: 'approved' | 'rejected') => Promise<void>
  onRemoveIpv4: (vmId: number) => Promise<void>
  onRemoveDns: (vmId: number) => Promise<void>
  onRemoveFromDB: (vmId: number) => Promise<void>
  onChangeOwner: (vmId: number, newOwnerId: string) => Promise<void>
  onChangeTemplate: (vmId: number, templateId: number) => Promise<void>
}

function VMTableRow({ vm, pendingRequests, owner, expired, node, onNavigate, onUpdateRequest, onRemoveIpv4, onRemoveDns, onRemoveFromDB, onChangeOwner, onChangeTemplate }: Props) {
  const { t } = useTranslation('admin')
  const tc = useTranslation().t
  const ipv4Req = pendingRequests?.find(r => r.type === 'ipv4')
  const dnsReq = pendingRequests?.find(r => r.type === 'dns')
  const [removingIpv4, setRemovingIpv4] = useState(false)
  const [removingDns, setRemovingDns] = useState(false)
  const [removingFromDB, setRemovingFromDB] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [changeOwnerOpen, setChangeOwnerOpen] = useState(false)
  const [changeTemplateOpen, setChangeTemplateOpen] = useState(false)

  return (
    <tr id={`vm-${vm.vm_id}`} onClick={() => onNavigate(vm.vm_id)} className="hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer">
      <td className="px-3 py-2 font-mono text-xs text-neutral-400 dark:text-neutral-500 border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">{vm.vm_id}</td>
      <td className="px-3 py-2 text-xs border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">
        <StatusCell vmId={vm.vm_id} />
      </td>
      <td className="px-3 py-2 font-medium text-neutral-800 dark:text-neutral-200 border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">
        <span className="block truncate">{vm.name}</span>
      </td>
      <td className="px-3 py-2 text-neutral-500 dark:text-neutral-400 text-xs border-r border-neutral-100 dark:border-neutral-800 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-1 group/tpl">
          <span className="truncate">{vm.template_name}</span>
          <button
            onClick={() => setChangeTemplateOpen(true)}
            title="Changer le template"
            className="shrink-0 text-neutral-300 dark:text-neutral-600 hover:text-blue-500 transition-colors cursor-pointer opacity-0 group-hover/tpl:opacity-100"
          >
            <FileStack size={12} />
          </button>
        </div>
      </td>
      <td className="px-3 py-2 border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 text-violet-600 dark:text-violet-400">
            <Cpu size={12} />
            <span className="font-mono font-semibold">{vm.cpu_cores}</span>
            <span className="text-violet-400 dark:text-violet-500">{tc('cores', { count: vm.cpu_cores })}</span>
          </span>
          <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
            <MemoryStick size={12} />
            <span className="font-mono font-semibold">{Math.round(vm.ram_mb / 1024)}</span>
            <span className="text-blue-400 dark:text-blue-500">{tc('gb')}</span>
          </span>
          <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <HardDrive size={12} />
            <span className="font-mono font-semibold">{vm.disk_gb}</span>
            <span className="text-emerald-400 dark:text-emerald-500">{tc('gb')}</span>
          </span>
        </div>
      </td>
      <td className="px-3 py-2 font-mono text-xs text-neutral-500 dark:text-neutral-400 border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">
        <span className="block truncate">{node ?? <span className="text-neutral-300 dark:text-neutral-600">—</span>}</span>
      </td>
      <td className="px-3 py-2 text-xs border-r border-neutral-100 dark:border-neutral-800 overflow-hidden" onClick={e => e.stopPropagation()}>
        {ipv4Req
          ? <RequestBadge request={ipv4Req} onUpdate={onUpdateRequest} />
          : vm.ipv4
            ? <span className="flex items-center gap-1">
                <span className="font-mono text-neutral-700 dark:text-neutral-300">{vm.ipv4}</span>
                <button
                  onClick={async () => { setRemovingIpv4(true); try { await onRemoveIpv4(vm.vm_id) } finally { setRemovingIpv4(false) } }}
                  disabled={removingIpv4}
                  className="text-neutral-300 dark:text-neutral-600 hover:text-red-500 transition-colors cursor-pointer disabled:opacity-40 shrink-0"
                >
                  {removingIpv4 ? <Loader size={11} className="animate-spin" /> : <X size={11} />}
                </button>
              </span>
            : <span className="font-mono text-neutral-300 dark:text-neutral-600">—</span>
        }
      </td>
      <td className="px-3 py-2 font-mono text-xs text-neutral-500 dark:text-neutral-400 border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">
        <span className="block truncate" title={vm.ipv6 ?? undefined}>{vm.ipv6 ?? <span className="text-neutral-300 dark:text-neutral-600">—</span>}</span>
      </td>
      <td className="px-3 py-2 font-mono text-xs text-neutral-400 dark:text-neutral-500 border-r border-neutral-100 dark:border-neutral-800 overflow-hidden">
        <span className="block truncate">{vm.mac ?? <span className="text-neutral-300 dark:text-neutral-600">—</span>}</span>
      </td>
      <td className="px-3 py-2 text-xs border-r border-neutral-100 dark:border-neutral-800 overflow-hidden" onClick={e => e.stopPropagation()}>
        {dnsReq
          ? <RequestBadge request={dnsReq} onUpdate={onUpdateRequest} />
          : vm.dns
            ? <span className="flex items-center gap-1">
                <span className="font-mono text-neutral-500 dark:text-neutral-400">{vm.dns}</span>
                <button
                  onClick={async () => { setRemovingDns(true); try { await onRemoveDns(vm.vm_id) } finally { setRemovingDns(false) } }}
                  disabled={removingDns}
                  className="text-neutral-300 dark:text-neutral-600 hover:text-red-500 transition-colors cursor-pointer disabled:opacity-40 shrink-0"
                >
                  {removingDns ? <Loader size={11} className="animate-spin" /> : <X size={11} />}
                </button>
              </span>
            : <span className="font-mono text-neutral-300 dark:text-neutral-600">—</span>
        }
      </td>
      <td className="px-3 py-2 overflow-hidden border-r border-neutral-100 dark:border-neutral-800" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-1 group/owner">
          {vm.owner_id ? (
            owner ? (
              <div className="flex flex-col gap-0.5 min-w-0" title={vm.owner_id}>
                <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300 truncate">{owner.name}</span>
                {owner.email && <span className="text-xs text-neutral-400 dark:text-neutral-500 truncate">{owner.email}</span>}
              </div>
            ) : <RevealOwner ownerId={vm.owner_id} />
          ) : <span className="text-neutral-300 dark:text-neutral-600 text-xs">—</span>}
          <button
            onClick={() => setChangeOwnerOpen(true)}
            title={t('changeOwner.title')}
            className="shrink-0 text-neutral-300 dark:text-neutral-600 hover:text-blue-500 transition-colors cursor-pointer opacity-0 group-hover/owner:opacity-100"
          >
            <UserPen size={12} />
          </button>
        </div>
      </td>
      <td className="px-3 py-2 overflow-hidden text-center">
        {vm.owner_id ? (
          expired
            ? <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 dark:bg-red-950 text-red-500 dark:text-red-400 border border-red-200 dark:border-red-800">{t('expired')}</span>
            : <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">OK</span>
        ) : <span className="text-neutral-300 dark:text-neutral-600 text-xs">—</span>}
      </td>
      <td className="px-3 py-2 text-center overflow-hidden" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => setConfirmOpen(true)}
          disabled={removingFromDB}
          title={t('removeFromDB')}
          className="text-neutral-300 dark:text-neutral-600 hover:text-red-500 transition-colors cursor-pointer disabled:opacity-40"
        >
          {removingFromDB ? <Loader size={13} className="animate-spin" /> : <Trash2 size={13} />}
        </button>
      </td>
      {confirmOpen && (
        <ConfirmModal
          title={t('removeFromDB')}
          confirmLabel={t('removeFromDBConfirmBtn')}
          cancelLabel={tc('cancel')}
          danger
          loading={removingFromDB}
          onClose={() => setConfirmOpen(false)}
          onConfirm={async () => {
            setRemovingFromDB(true)
            try {
              await onRemoveFromDB(vm.vm_id)
              setConfirmOpen(false)
            } finally {
              setRemovingFromDB(false)
            }
          }}
        >
          {t('removeFromDBConfirm', { id: vm.vm_id, name: vm.name })}
        </ConfirmModal>
      )}
      {changeOwnerOpen && (
        <ChangeOwnerModal
          vmId={vm.vm_id}
          vmName={vm.name}
          currentOwnerId={vm.owner_id}
          onConfirm={newOwnerId => onChangeOwner(vm.vm_id, newOwnerId)}
          onClose={() => setChangeOwnerOpen(false)}
        />
      )}
      {changeTemplateOpen && (
        <ChangeTemplateModal
          vmId={vm.vm_id}
          vmName={vm.name}
          currentTemplateId={vm.template_id}
          onConfirm={templateId => onChangeTemplate(vm.vm_id, templateId)}
          onClose={() => setChangeTemplateOpen(false)}
        />
      )}
    </tr>
  )
}

export default memo(VMTableRow)
