import { useState, useMemo, useContext, useRef, useEffect, useCallback } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown, Cpu, MemoryStick, HardDrive, Eye, Loader, Filter, X, Check, AlertTriangle } from 'lucide-react'
import { useAdminVMs, type AdminVM } from '../hooks/useAdminVMs'
import { useAdminRequests, type AdminRequest } from '../hooks/useAdminRequests'
import { useAdminCotiseEnded } from '../hooks/useAdminCotiseEnded'
import { useVMStatus, VMStatusContext } from '../contexts/VMStatusContext'
import { apiFetch } from '../api'

type SortKey = 'vm_id' | 'name' | 'template_name' | 'cpu_cores' | 'ipv4' | 'ipv6' | 'mac' | 'dns' | 'owner_id' | 'status'
type SortDir = 'asc' | 'desc'
type StatusMap = Map<number, { status: string; uptime: number | null }>
interface UserIdentity { username: string | null; first_name: string | null; last_name: string | null; email: string | null }

const COLS = ['vm_id', 'status', 'name', 'template_name', 'cpu_cores', 'ipv4', 'ipv6', 'mac', 'dns', 'owner_id'] as const
type ColId = typeof COLS[number]

const DEFAULT_WIDTHS: Record<ColId, number> = {
  vm_id: 60, status: 120, name: 150, template_name: 130,
  cpu_cores: 220, ipv4: 120, ipv6: 260, mac: 140, dns: 200, owner_id: 340,
}

function getStatusOrder(vmId: number, statuses: StatusMap): number {
  const s = statuses.get(vmId)?.status
  if (s === 'running') return 0
  if (s) return 1
  return 2
}

// ─── Request dialog ───────────────────────────────────────────────────────────

function RequestDialog({ request, onClose, onUpdate }: {
  request: AdminRequest
  onClose: () => void
  onUpdate: (id: number, status: 'approved' | 'rejected') => Promise<void>
}) {
  const [loading, setLoading] = useState(false)

  async function handle(status: 'approved' | 'rejected') {
    setLoading(true)
    try { await onUpdate(request.id, status) } finally { setLoading(false) }
    onClose()
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

function RequestBadge({ request, onUpdate }: {
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

// ─── Status cell ─────────────────────────────────────────────────────────────

function StatusCell({ vmId }: { vmId: number }) {
  const entry = useVMStatus(vmId)
  const status = entry?.status
  const dot = !status ? 'bg-neutral-300' : status === 'running' ? 'bg-emerald-500' : 'bg-red-400'
  const label = !status
    ? <span className="text-neutral-400">—</span>
    : status === 'running'
      ? <span className="text-emerald-600 font-medium">running</span>
      : <span className="text-red-500 font-medium">{status}</span>
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${dot}`} />
      {label}
    </div>
  )
}

// ─── Reveal owner ─────────────────────────────────────────────────────────────

function RevealOwner({ ownerId }: { ownerId: string }) {
  const [identity, setIdentity] = useState<UserIdentity | null>(null)
  const [loading, setLoading] = useState(false)
  const [revealed, setRevealed] = useState(false)

  async function reveal() {
    if (revealed) return
    setLoading(true)
    try {
      const data = await apiFetch<UserIdentity>(`/api/users/${encodeURIComponent(ownerId)}/identity`)
      setIdentity(data)
    } finally {
      setLoading(false)
      setRevealed(true)
    }
  }

  if (!revealed) {
    return (
      <button onClick={reveal} className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-blue-500 transition-colors" title="Révéler l'identité">
        {loading ? <Loader size={11} className="animate-spin text-blue-400" /> : <Eye size={11} />}
        <span className="font-mono">{ownerId}</span>
      </button>
    )
  }

  const name = [identity?.first_name, identity?.last_name].filter(Boolean).join(' ') || identity?.username || null
  return (
    <div className="flex flex-col gap-0.5" title={ownerId}>
      {name
        ? <span className="text-xs font-medium text-neutral-700">{name}</span>
        : <span className="font-mono text-xs text-neutral-500">{ownerId}</span>
      }
      {identity?.email && <span className="text-xs text-neutral-400">{identity.email}</span>}
    </div>
  )
}

// ─── Column filter popover ────────────────────────────────────────────────────

interface ColFilterProps {
  active: boolean; type: 'text' | 'select'; value: string
  onChange: (v: string) => void; options?: { label: string; value: string }[]; placeholder?: string
}

function ColFilter({ active, type, value, onChange, options, placeholder }: ColFilterProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  return (
    <div ref={ref} className="relative inline-block" onClick={e => e.stopPropagation()}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`p-0.5 rounded transition-colors ${active ? 'text-blue-500 bg-blue-50' : 'text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100'}`}
      >
        <Filter size={10} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-white border border-neutral-200 rounded shadow-lg p-2 min-w-[160px]">
          {type === 'select' ? (
            <select autoFocus value={value} onChange={e => { onChange(e.target.value); setOpen(false) }}
              className="w-full text-xs border border-neutral-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400 bg-white">
              {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : (
            <div className="flex items-center gap-1">
              <input autoFocus type="text" value={value} onChange={e => onChange(e.target.value)}
                placeholder={placeholder ?? 'Filtrer…'}
                className="flex-1 text-xs border border-neutral-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400" />
              {value && (
                <button onClick={() => { onChange(''); setOpen(false) }} className="text-neutral-400 hover:text-neutral-700">
                  <X size={11} />
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Th with sort + filter + resize handle ────────────────────────────────────

interface ThProps {
  col: ColId; label: string; width: number
  sortKey: SortKey; sortDir: SortDir; onSort: (col: SortKey) => void
  onResizeStart: (e: React.MouseEvent, col: ColId) => void
  filter?: ColFilterProps
}

function Th({ col, label, width, sortKey, sortDir, onSort, onResizeStart, filter }: ThProps) {
  const sorted = (col as string) === sortKey
  return (
    <th
      className="group relative px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider whitespace-nowrap bg-neutral-50 border-r border-neutral-200 last:border-r-0 select-none overflow-hidden"
      style={{ width, minWidth: width }}
    >
      <div className="flex items-center gap-1.5 overflow-hidden">
        <button className="flex items-center gap-1 hover:text-neutral-800 transition-colors overflow-hidden" onClick={() => onSort(col as SortKey)}>
          <span className="truncate">{label}</span>
          {sorted
            ? sortDir === 'asc' ? <ChevronUp size={11} className="text-blue-500 shrink-0" /> : <ChevronDown size={11} className="text-blue-500 shrink-0" />
            : <ChevronsUpDown size={11} className="text-neutral-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
          }
        </button>
        {filter && <ColFilter {...filter} />}
      </div>
      {/* Resize handle */}
      <div
        className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-blue-400 transition-colors opacity-0 group-hover:opacity-100"
        onMouseDown={e => onResizeStart(e, col)}
      />
    </th>
  )
}

// ─── Cotise ended tab ─────────────────────────────────────────────────────────

function CotiseEndedTab() {
  const { users, loading } = useAdminCotiseEnded()

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between shrink-0">
        <h1 className="text-base font-semibold text-neutral-800">Cotisations expirées</h1>
        <span className="text-xs text-neutral-400 font-mono">
          {loading ? 'Chargement…' : `${users.length} membre${users.length !== 1 ? 's' : ''}`}
        </span>
      </div>
      <div className="flex-1 min-h-0 overflow-auto rounded-sm border border-neutral-200 shadow-sm">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10 border-b border-neutral-200 bg-neutral-50">
            <tr>
              {['Identifiant', 'Prénom', 'Nom', 'Email'].map(h => (
                <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider whitespace-nowrap border-r border-neutral-200 last:border-r-0">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-neutral-100">
            {loading && (
              <tr><td colSpan={4} className="px-4 py-10 text-center text-neutral-400 text-xs"><Loader size={14} className="animate-spin inline mr-2" />Chargement…</td></tr>
            )}
            {!loading && users.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-10 text-center text-neutral-400 text-xs">Aucun membre dans ce groupe</td></tr>
            )}
            {users.map(u => (
              <tr key={u.id ?? u.username} className="hover:bg-neutral-50 transition-colors">
                <td className="px-3 py-2 font-mono text-xs text-neutral-500 border-r border-neutral-100">{u.username ?? <span className="text-neutral-300">—</span>}</td>
                <td className="px-3 py-2 text-xs text-neutral-700 border-r border-neutral-100">{u.first_name ?? <span className="text-neutral-300">—</span>}</td>
                <td className="px-3 py-2 text-xs text-neutral-700 border-r border-neutral-100">{u.last_name ?? <span className="text-neutral-300">—</span>}</td>
                <td className="px-3 py-2 text-xs text-neutral-500">{u.email ?? <span className="text-neutral-300">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

type Tab = 'vms' | 'cotise_ended'

interface Filters {
  name: string; template: string; status: string
  ipv4: string; ipv6: string; mac: string; dns: string; owner: string
}
const EMPTY_FILTERS: Filters = { name: '', template: '', status: '', ipv4: '', ipv6: '', mac: '', dns: '', owner: '' }

export default function AdminPage() {
  const { vms, loading } = useAdminVMs()
  const { pendingByVm, updateRequest } = useAdminRequests()
  const { statuses } = useContext(VMStatusContext)
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
      const newWidth = Math.max(60, dragRef.current.startWidth + delta)
      setColWidths(prev => ({ ...prev, [dragRef.current!.col]: newWidth }))
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
    if (filters.owner && !(vm.owner_id ?? '').toLowerCase().includes(filters.owner.toLowerCase())) return false
    return true
  }), [vms, filters, statuses])

  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    let cmp = 0
    if (sortKey === 'status') cmp = getStatusOrder(a.vm_id, statuses) - getStatusOrder(b.vm_id, statuses)
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

  if (tab === 'cotise_ended') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="flex items-center gap-2 shrink-0 border-b border-neutral-200 pb-2">
          {(['vms', 'cotise_ended'] as Tab[]).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${tab === t ? 'bg-neutral-900 text-white' : 'text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100'}`}>
              {t === 'vms' ? 'Machines virtuelles' : 'Cotisations expirées'}
            </button>
          ))}
        </div>
        <CotiseEndedTab />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 border-b border-neutral-200 pb-2 w-full justify-between">
          <div className="flex items-center gap-2">
            {(['vms', 'cotise_ended'] as Tab[]).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${tab === t ? 'bg-neutral-900 text-white' : 'text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100'}`}>
                {t === 'vms' ? 'Machines virtuelles' : 'Cotisations expirées'}
              </button>
            ))}
          </div>
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
        <table className="text-sm border-collapse" style={{ tableLayout: 'fixed', width: Object.values(colWidths).reduce((a, b) => a + b, 0) }}>
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
              <Th col="ipv4"         label="IPv4"         width={colWidths.ipv4}         {...thProps}
                filter={{ active: !!filters.ipv4, type: 'text', value: filters.ipv4, onChange: v => setFilter('ipv4', v), placeholder: 'x.x.x.x' }} />
              <Th col="ipv6"         label="IPv6"         width={colWidths.ipv6}         {...thProps}
                filter={{ active: !!filters.ipv6, type: 'text', value: filters.ipv6, onChange: v => setFilter('ipv6', v), placeholder: '…' }} />
              <Th col="mac"          label="MAC"          width={colWidths.mac}          {...thProps}
                filter={{ active: !!filters.mac, type: 'text', value: filters.mac, onChange: v => setFilter('mac', v), placeholder: 'xx:xx…' }} />
              <Th col="dns"          label="DNS"          width={colWidths.dns}          {...thProps}
                filter={{ active: !!filters.dns, type: 'text', value: filters.dns, onChange: v => setFilter('dns', v), placeholder: 'hostname…' }} />
              <Th col="owner_id"     label="Propriétaire" width={colWidths.owner_id}    {...thProps}
                filter={{ active: !!filters.owner, type: 'text', value: filters.owner, onChange: v => setFilter('owner', v), placeholder: 'UUID…' }} />
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-neutral-100">
            {!loading && sorted.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-10 text-center text-neutral-400 text-xs">Aucune VM</td></tr>
            )}
            {sorted.map(vm => (
              <tr key={vm.vm_id} className="hover:bg-neutral-50 transition-colors">
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
                <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden">
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
                <td className="px-3 py-2 text-xs border-r border-neutral-100 overflow-hidden">
                  {(() => {
                    const req = pendingByVm.get(vm.vm_id)?.find(r => r.type === 'dns')
                    if (req) return <RequestBadge request={req} onUpdate={updateRequest} />
                    return <span className="font-mono text-neutral-500">{vm.dns ?? <span className="text-neutral-300">—</span>}</span>
                  })()}
                </td>
                <td className="px-3 py-2 overflow-hidden">
                  {vm.owner_id
                    ? <RevealOwner ownerId={vm.owner_id} />
                    : <span className="text-neutral-300 text-xs">—</span>
                  }
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
