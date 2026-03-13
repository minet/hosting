import { useState, useMemo, useContext, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cpu, MemoryStick, HardDrive, X } from 'lucide-react'
import { useAdminVMs, type AdminVM } from '../hooks/useAdminVMs'
import { useAdminRequests } from '../hooks/useAdminRequests'
import { useAdminGroupMembers } from '../hooks/useAdminGroupMembers'
import { VMStatusContext } from '../contexts/VMStatusContext'
import RequestBadge from '../components/admin/RequestBadge'
import StatusCell from '../components/admin/StatusCell'
import RevealOwner from '../components/admin/RevealOwner'
import Th, { type SortKey, type SortDir, type ColId, DEFAULT_WIDTHS } from '../components/admin/Th'
import TemplatesTab from '../components/admin/TemplatesTab'
import ProxmoxTab from '../components/admin/ProxmoxTab'

type StatusMap = Map<number, { status: string; uptime: number | null; node: string | null }>
type Tab = 'vms' | 'templates' | 'proxmox'

function getStatusOrder(vmId: number, statuses: StatusMap): number {
  const s = statuses.get(vmId)?.status
  if (s === 'running') return 0
  if (s) return 1
  return 2
}

interface Filters {
  name: string; template: string; status: string
  ipv4: string; ipv6: string; mac: string; dns: string; owner: string
}
const EMPTY_FILTERS: Filters = { name: '', template: '', status: '', ipv4: '', ipv6: '', mac: '', dns: '', owner: '' }

export { type ColId, type SortKey, type SortDir }

export default function AdminPage() {
  const navigate = useNavigate()
  const { vms, loading, refresh: refreshVMs } = useAdminVMs()
  const { pendingByVm, updateRequest } = useAdminRequests(refreshVMs)
  const { statuses } = useContext(VMStatusContext)
  const charte = useAdminGroupMembers('/api/users/hosting-charte')
  const cotiseEnded = useAdminGroupMembers('/api/users/cotise-ended')

  const userLookup = useMemo(() => {
    const map = new Map<string, { name: string; email: string | null }>()
    for (const u of [...charte.users, ...cotiseEnded.users]) {
      if (!u.id || map.has(u.id)) continue
      const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username || u.id
      map.set(u.id, { name, email: u.email })
    }
    return map
  }, [charte.users, cotiseEnded.users])

  const expiredOwners = useMemo(() => {
    const set = new Set<string>()
    for (const u of cotiseEnded.users) {
      if (u.id) set.add(u.id)
    }
    return set
  }, [cotiseEnded.users])

  const [tab, setTab] = useState<Tab>('vms')
  const [sortKey, setSortKey] = useState<SortKey>('vm_id')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [colWidths, setColWidths] = useState<Record<ColId, number>>({ ...DEFAULT_WIDTHS })
  const dragRef = useRef<{ col: ColId; startX: number; startWidth: number } | null>(null)

  const onResizeStart = useCallback((e: React.MouseEvent, col: ColId) => {
    e.preventDefault()
    dragRef.current = { col, startX: e.clientX, startWidth: colWidths[col] }
    function onMove(ev: MouseEvent) {
      if (!dragRef.current) return
      const delta = ev.clientX - dragRef.current.startX
      setColWidths(prev => ({ ...prev, [dragRef.current!.col]: Math.max(60, dragRef.current!.startWidth + delta) }))
    }
    function onUp() {
      dragRef.current = null
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [colWidths])

  function setFilter(key: keyof Filters, value: string) {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  function handleSort(col: SortKey) {
    if (col === sortKey) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(col); setSortDir('asc') }
  }

  const filtered = useMemo(() => vms.filter(vm => {
    const s = statuses.get(vm.vm_id)?.status ?? ''
    if (filters.status === 'running' && s !== 'running') return false
    if (filters.status === 'stopped' && s === 'running') return false
    if (filters.name && !vm.name.toLowerCase().includes(filters.name.toLowerCase())) return false
    if (filters.template && !vm.template_name.toLowerCase().includes(filters.template.toLowerCase())) return false
    if (filters.ipv4 && !(vm.ipv4 ?? '').includes(filters.ipv4)) return false
    if (filters.ipv6 && !(vm.ipv6 ?? '').includes(filters.ipv6)) return false
    if (filters.mac && !(vm.mac ?? '').toLowerCase().includes(filters.mac.toLowerCase())) return false
    if (filters.dns && !(vm.dns ?? '').toLowerCase().includes(filters.dns.toLowerCase())) return false
    if (filters.owner) {
      const ownerFilter = filters.owner.toLowerCase()
      const known = vm.owner_id ? userLookup.get(vm.owner_id) : undefined
      const matchId = (vm.owner_id ?? '').toLowerCase().includes(ownerFilter)
      const matchName = known?.name.toLowerCase().includes(ownerFilter)
      const matchEmail = known?.email?.toLowerCase().includes(ownerFilter)
      if (!matchId && !matchName && !matchEmail) return false
    }
    return true
  }), [vms, filters, statuses])

  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    let cmp = 0
    if (sortKey === 'status') cmp = getStatusOrder(a.vm_id, statuses) - getStatusOrder(b.vm_id, statuses)
    else if (sortKey === 'node') cmp = (statuses.get(a.vm_id)?.node ?? '').localeCompare(statuses.get(b.vm_id)?.node ?? '')
    else if (sortKey === 'vm_id' || sortKey === 'cpu_cores') cmp = (a[sortKey] as number) - (b[sortKey] as number)
    else {
      const av = (a[sortKey as keyof AdminVM] as string | null) ?? ''
      const bv = (b[sortKey as keyof AdminVM] as string | null) ?? ''
      cmp = av.localeCompare(bv)
    }
    return sortDir === 'asc' ? cmp : -cmp
  }), [filtered, sortKey, sortDir, statuses])

  const hasFilters = Object.values(filters).some(Boolean)
  const thProps = { sortKey, sortDir, onSort: handleSort, onResizeStart }
  const statusOptions = [
    { label: 'Tous', value: '' }, { label: 'Running', value: 'running' }, { label: 'Stopped', value: 'stopped' },
  ]

  // ─── Tab bar ──────────────────────────────────────────────────────────────
  const tabBar = (
    <div className="flex items-center gap-2">
      {(['vms', 'templates', 'proxmox'] as Tab[]).map(t => (
        <button key={t} onClick={() => setTab(t)}
          className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${tab === t ? 'bg-neutral-900 text-white' : 'text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100'}`}>
          {t === 'vms' ? 'Machines virtuelles' : t === 'templates' ? 'Templates' : 'Proxmox'}
        </button>
      ))}
    </div>
  )

  if (tab === 'templates') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 pb-2">{tabBar}</div>
        <TemplatesTab />
      </div>
    )
  }

  if (tab === 'proxmox') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 pb-2">{tabBar}</div>
        <ProxmoxTab />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 border-b border-neutral-200 pb-2 w-full justify-between">
          {tabBar}
          <div className="flex items-center gap-3">
            {hasFilters && (
              <button onClick={() => setFilters(EMPTY_FILTERS)} className="flex items-center gap-1 text-xs text-red-400 hover:text-red-600 transition-colors">
                <X size={11} /> Effacer les filtres
              </button>
            )}
            <span className="text-xs text-neutral-400 font-mono">
              {loading ? 'Chargement…' : `${sorted.length} / ${vms.length}`}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto rounded-sm border border-neutral-200 shadow-sm">
        <table className="text-sm border-collapse w-full" style={{ tableLayout: 'fixed', minWidth: Object.values(colWidths).reduce((a, b) => a + b, 0) }}>
          <thead className="sticky top-0 z-10 border-b border-neutral-200">
            <tr>
              <Th col="vm_id"        label="ID"           width={colWidths.vm_id}        {...thProps} />
              <Th col="status"       label="Statut"       width={colWidths.status}       {...thProps}
                filter={{ active: !!filters.status, type: 'select', value: filters.status, onChange: v => setFilter('status', v), options: statusOptions }} />
              <Th col="name"         label="Nom"          width={colWidths.name}         {...thProps}
                filter={{ active: !!filters.name, type: 'text', value: filters.name, onChange: v => setFilter('name', v), placeholder: 'Nom…' }} />
              <Th col="template_name" label="Template"   width={colWidths.template_name} {...thProps}
                filter={{ active: !!filters.template, type: 'text', value: filters.template, onChange: v => setFilter('template', v), placeholder: 'Template…' }} />
              <Th col="cpu_cores"    label="Ressources"   width={colWidths.cpu_cores}    {...thProps} />
              <Th col="node"         label="Nœud"         width={colWidths.node}         {...thProps} />
              <Th col="ipv4"         label="IPv4"         width={colWidths.ipv4}         {...thProps}
                filter={{ active: !!filters.ipv4, type: 'text', value: filters.ipv4, onChange: v => setFilter('ipv4', v), placeholder: 'x.x.x.x' }} />
              <Th col="ipv6"         label="IPv6"         width={colWidths.ipv6}         {...thProps}
                filter={{ active: !!filters.ipv6, type: 'text', value: filters.ipv6, onChange: v => setFilter('ipv6', v), placeholder: '…' }} />
              <Th col="mac"          label="MAC"          width={colWidths.mac}          {...thProps}
                filter={{ active: !!filters.mac, type: 'text', value: filters.mac, onChange: v => setFilter('mac', v), placeholder: 'xx:xx…' }} />
              <Th col="dns"          label="DNS"          width={colWidths.dns}          {...thProps}
                filter={{ active: !!filters.dns, type: 'text', value: filters.dns, onChange: v => setFilter('dns', v), placeholder: 'hostname…' }} />
              <Th col="owner_id"     label="Propriétaire" width={colWidths.owner_id}    {...thProps}
                filter={{ active: !!filters.owner, type: 'text', value: filters.owner, onChange: v => setFilter('owner', v), placeholder: 'Nom…' }} />
              <Th col="cotise"       label="Cotisation"   width={colWidths.cotise}      {...thProps} />
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-neutral-100">
            {!loading && sorted.length === 0 && (
              <tr><td colSpan={12} className="px-4 py-10 text-center text-neutral-400 text-xs">Aucune VM</td></tr>
            )}
            {sorted.map(vm => (
              <tr key={vm.vm_id} onClick={() => navigate(`/vm/${vm.vm_id}`)} className="hover:bg-neutral-50 transition-colors cursor-pointer">
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
                  <span className="block truncate">{statuses.get(vm.vm_id)?.node ?? <span className="text-neutral-300">—</span>}</span>
                </td>
                <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden" onClick={e => e.stopPropagation()}>
                  {(() => {
                    const req = pendingByVm.get(vm.vm_id)?.find(r => r.type === 'ipv4')
                    if (req) return <RequestBadge request={req} onUpdate={updateRequest} />
                    return <span className="font-mono text-neutral-700">{vm.ipv4 ?? <span className="text-neutral-300">—</span>}</span>
                  })()}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-neutral-500 border-r border-neutral-100 overflow-hidden">
                  <span className="block truncate" title={vm.ipv6 ?? undefined}>{vm.ipv6 ?? <span className="text-neutral-300">—</span>}</span>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-neutral-400 border-r border-neutral-100 overflow-hidden">
                  <span className="block truncate">{vm.mac ?? <span className="text-neutral-300">—</span>}</span>
                </td>
                <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden" onClick={e => e.stopPropagation()}>
                  {(() => {
                    const req = pendingByVm.get(vm.vm_id)?.find(r => r.type === 'dns')
                    if (req) return <RequestBadge request={req} onUpdate={updateRequest} />
                    return <span className="font-mono text-neutral-500">{vm.dns ?? <span className="text-neutral-300">—</span>}</span>
                  })()}
                </td>
                <td className="px-3 py-2 overflow-hidden border-r border-neutral-100" onClick={e => e.stopPropagation()}>
                  {vm.owner_id ? (() => {
                    const known = userLookup.get(vm.owner_id)
                    if (known) return (
                      <div className="flex flex-col gap-0.5" title={vm.owner_id}>
                        <span className="text-xs font-medium text-neutral-700">{known.name}</span>
                        {known.email && <span className="text-xs text-neutral-400">{known.email}</span>}
                      </div>
                    )
                    return <RevealOwner ownerId={vm.owner_id} />
                  })() : <span className="text-neutral-300 text-xs">—</span>}
                </td>
                <td className="px-3 py-2 overflow-hidden text-center">
                  {vm.owner_id ? (
                    expiredOwners.has(vm.owner_id)
                      ? <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-500 border border-red-200">Expiré</span>
                      : <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200">OK</span>
                  ) : <span className="text-neutral-300 text-xs">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-neutral-400 text-right font-mono shrink-0">
        Rows: {sorted.length}&nbsp;&nbsp;Total Rows: {vms.length}
      </div>
    </div>
  )
}
