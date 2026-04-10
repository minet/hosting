import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { useUser } from '../contexts/UserContext'
import { useAdminVMs, type AdminVM } from '../hooks/useAdminVMs'
import { useAdminRequests } from '../hooks/useAdminRequests'
import { useAdminGroupMembers } from '../hooks/useAdminGroupMembers'
import { useAllStatuses } from '../contexts/VMStatusContext'
import { useDebounce } from '../hooks/useDebounce'
import VMTableRow from '../components/admin/VMTableRow'
import Th, { type SortKey, type SortDir, type ColId, DEFAULT_WIDTHS } from '../components/admin/Th'
import TemplatesTab from '../components/admin/TemplatesTab'
import ProxmoxTab from '../components/admin/ProxmoxTab'
import OrphanedVMsTab from '../components/admin/OrphanedVMsTab'
import ExpiredVMsTab from '../components/admin/ExpiredVMsTab'
import IPHistoryTab from '../components/admin/IPHistoryTab'

type StatusMap = Map<number, { status: string; uptime: number | null; node: string | null }>
type Tab = 'vms' | 'templates' | 'proxmox' | 'orphaned' | 'expired' | 'ip-history'

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
  const { t } = useTranslation('admin')
  const tc = useTranslation().t
  const me = useUser()
  const [maintenance, setMaintenance] = useState(me.maintenance ?? false)
  const { vms, loading, refresh: refreshVMs } = useAdminVMs()
  const { pendingByVm, updateRequest } = useAdminRequests(refreshVMs)
  const statuses = useAllStatuses()
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
  const debouncedFilters = useDebounce(filters, 250)
  const [colWidths, setColWidths] = useState<Record<ColId, number>>({ ...DEFAULT_WIDTHS })
  const dragRef = useRef<{ col: ColId; startX: number; startWidth: number } | null>(null)

  // Fixed drag: attach/detach listeners via useEffect to avoid leaks on unmount
  const onResizeStart = useCallback((e: React.MouseEvent, col: ColId) => {
    e.preventDefault()
    dragRef.current = { col, startX: e.clientX, startWidth: colWidths[col] }
  }, [colWidths])

  useEffect(() => {
    function onMove(ev: MouseEvent) {
      if (!dragRef.current) return
      const delta = ev.clientX - dragRef.current.startX
      setColWidths(prev => ({ ...prev, [dragRef.current!.col]: Math.max(60, dragRef.current!.startWidth + delta) }))
    }
    function onUp() {
      dragRef.current = null
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [])

  function setFilter(key: keyof Filters, value: string) {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  function handleSort(col: SortKey) {
    if (col === sortKey) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(col); setSortDir('asc') }
  }

  const filtered = useMemo(() => vms.filter(vm => {
    const s = statuses.get(vm.vm_id)?.status ?? ''
    if (debouncedFilters.status === 'running' && s !== 'running') return false
    if (debouncedFilters.status === 'stopped' && s === 'running') return false
    if (debouncedFilters.name && !vm.name.toLowerCase().includes(debouncedFilters.name.toLowerCase())) return false
    if (debouncedFilters.template && !vm.template_name.toLowerCase().includes(debouncedFilters.template.toLowerCase())) return false
    if (debouncedFilters.ipv4 && !(vm.ipv4 ?? '').includes(debouncedFilters.ipv4)) return false
    if (debouncedFilters.ipv6 && !(vm.ipv6 ?? '').includes(debouncedFilters.ipv6)) return false
    if (debouncedFilters.mac && !(vm.mac ?? '').toLowerCase().includes(debouncedFilters.mac.toLowerCase())) return false
    if (debouncedFilters.dns && !(vm.dns ?? '').toLowerCase().includes(debouncedFilters.dns.toLowerCase())) return false
    if (debouncedFilters.owner) {
      const ownerFilter = debouncedFilters.owner.toLowerCase()
      const known = vm.owner_id ? userLookup.get(vm.owner_id) : undefined
      const matchId = (vm.owner_id ?? '').toLowerCase().includes(ownerFilter)
      const matchName = known?.name.toLowerCase().includes(ownerFilter)
      const matchEmail = known?.email?.toLowerCase().includes(ownerFilter)
      if (!matchId && !matchName && !matchEmail) return false
    }
    return true
  }), [vms, debouncedFilters, statuses, userLookup])

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
    { label: t('statusFilter.all'), value: '' }, { label: t('statusFilter.running'), value: 'running' }, { label: t('statusFilter.stopped'), value: 'stopped' },
  ]

  const handleNavigate = useCallback((vmId: number) => navigate(`/vm/${vmId}`), [navigate])

  const handleRemoveIpv4 = useCallback(async (vmId: number) => {
    await apiFetch(`/api/vms/${vmId}/ipv4`, { method: 'DELETE' })
    refreshVMs()
  }, [refreshVMs])

  const handleRemoveDns = useCallback(async (vmId: number) => {
    await apiFetch(`/api/vms/${vmId}/dns`, { method: 'DELETE' })
    refreshVMs()
  }, [refreshVMs])

  async function toggleMaintenance() {
    const res = await apiFetch<{ maintenance: boolean }>('/api/maintenance', { method: 'POST' })
    setMaintenance(res.maintenance)
  }

  // ─── Tab bar ──────────────────────────────────────────────────────────────
  const tabBar = (
    <div className="flex items-center gap-2 overflow-x-auto flex-1 min-w-0">
      {(['vms', 'templates', 'proxmox', 'orphaned', 'expired', 'ip-history'] as Tab[]).map(tb => (
        <button key={tb} onClick={() => setTab(tb)}
          className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${tab === tb ? 'bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800'}`}>
          {t(`tabs.${tb}`)}
        </button>
      ))}
      <button onClick={toggleMaintenance}
        className={`ml-4 px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer ${maintenance
          ? 'bg-red-500 text-white hover:bg-red-600'
          : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800'
        }`}>
        {maintenance ? t('maintenance.active') : t('maintenance.enable')}
      </button>
    </div>
  )

  if (tab === 'templates') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-700 pb-2">{tabBar}</div>
        <TemplatesTab />
      </div>
    )
  }

  if (tab === 'proxmox') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-700 pb-2">{tabBar}</div>
        <ProxmoxTab />
      </div>
    )
  }

  if (tab === 'orphaned') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-700 pb-2">{tabBar}</div>
        <OrphanedVMsTab />
      </div>
    )
  }

  if (tab === 'expired') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-700 pb-2">{tabBar}</div>
        <ExpiredVMsTab />
      </div>
    )
  }

  if (tab === 'ip-history') {
    return (
      <div className="flex flex-col gap-3 h-full">
        <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-700 pb-2">{tabBar}</div>
        <IPHistoryTab />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2 shrink-0 border-b border-neutral-200 dark:border-neutral-700 pb-2 min-w-0">
        {tabBar}
        <div className="flex items-center gap-3 shrink-0">
          {hasFilters && (
            <button onClick={() => setFilters(EMPTY_FILTERS)} className="flex items-center gap-1 text-xs text-red-400 hover:text-red-600 transition-colors">
              <X size={11} /> {t('clearFilters')}
            </button>
          )}
          <span className="text-xs text-neutral-400 dark:text-neutral-500 font-mono">
            {loading ? tc('loading') : `${sorted.length} / ${vms.length}`}
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto rounded-sm border border-neutral-200 dark:border-neutral-700 shadow-sm">
        <table className="text-sm border-collapse w-full" style={{ tableLayout: 'fixed', minWidth: Object.values(colWidths).reduce((a, b) => a + b, 0) }}>
          <thead className="sticky top-0 z-10 border-b border-neutral-200 dark:border-neutral-700">
            <tr>
              <Th col="vm_id"        label={t('columns.id')}       width={colWidths.vm_id}        {...thProps} />
              <Th col="status"       label={t('columns.status')}  width={colWidths.status}       {...thProps}
                filter={{ active: !!filters.status, type: 'select', value: filters.status, onChange: v => setFilter('status', v), options: statusOptions }} />
              <Th col="name"         label={t('columns.name')}     width={colWidths.name}         {...thProps}
                filter={{ active: !!filters.name, type: 'text', value: filters.name, onChange: v => setFilter('name', v), placeholder: `${t('columns.name')}…` }} />
              <Th col="template_name" label={t('columns.template')} width={colWidths.template_name} {...thProps}
                filter={{ active: !!filters.template, type: 'text', value: filters.template, onChange: v => setFilter('template', v), placeholder: `${t('columns.template')}…` }} />
              <Th col="cpu_cores"    label={t('columns.resources')} width={colWidths.cpu_cores}    {...thProps} />
              <Th col="node"         label={t('columns.node')}     width={colWidths.node}         {...thProps} />
              <Th col="ipv4"         label="IPv4"         width={colWidths.ipv4}         {...thProps}
                filter={{ active: !!filters.ipv4, type: 'text', value: filters.ipv4, onChange: v => setFilter('ipv4', v), placeholder: 'x.x.x.x' }} />
              <Th col="ipv6"         label="IPv6"         width={colWidths.ipv6}         {...thProps}
                filter={{ active: !!filters.ipv6, type: 'text', value: filters.ipv6, onChange: v => setFilter('ipv6', v), placeholder: '…' }} />
              <Th col="mac"          label="MAC"          width={colWidths.mac}          {...thProps}
                filter={{ active: !!filters.mac, type: 'text', value: filters.mac, onChange: v => setFilter('mac', v), placeholder: 'xx:xx…' }} />
              <Th col="dns"          label="DNS"          width={colWidths.dns}          {...thProps}
                filter={{ active: !!filters.dns, type: 'text', value: filters.dns, onChange: v => setFilter('dns', v), placeholder: 'hostname…' }} />
              <Th col="owner_id"     label={t('columns.owner')} width={colWidths.owner_id}    {...thProps}
                filter={{ active: !!filters.owner, type: 'text', value: filters.owner, onChange: v => setFilter('owner', v), placeholder: `${t('columns.name')}…` }} />
              <Th col="cotise"       label={t('columns.subscription')} width={colWidths.cotise}      {...thProps} />
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {!loading && sorted.length === 0 && (
              <tr><td colSpan={12} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">{t('noVM')}</td></tr>
            )}
            {sorted.map(vm => (
              <VMTableRow
                key={vm.vm_id}
                vm={vm}
                pendingRequests={pendingByVm.get(vm.vm_id)}
                owner={vm.owner_id ? userLookup.get(vm.owner_id) : undefined}
                expired={!!vm.owner_id && expiredOwners.has(vm.owner_id)}
                node={statuses.get(vm.vm_id)?.node ?? null}
                onNavigate={handleNavigate}
                onUpdateRequest={updateRequest}
                onRemoveIpv4={handleRemoveIpv4}
                onRemoveDns={handleRemoveDns}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-neutral-400 dark:text-neutral-500 text-right font-mono shrink-0">
        Rows: {sorted.length}&nbsp;&nbsp;Total Rows: {vms.length}
      </div>
    </div>
  )
}
