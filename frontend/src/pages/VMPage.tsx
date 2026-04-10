import { lazy, Suspense, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Play, TerminalSquare } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { apiFetch, ApiError } from '../api'

const VMTerminal = lazy(() => import('../components/VMTerminal'))
const MetricChart = lazy(() => import('../components/MetricChart'))
import { useVMStatus } from '../contexts/VMStatusContext'
import { useResources } from '../hooks/useResources'
import { useUser } from '../contexts/UserContext'
import { useVMActions } from '../hooks/useVMActions'
import { useVMCredentials } from '../hooks/useVMCredentials'
import { useVMShare } from '../hooks/useVMShare'
import { useVMRequests } from '../hooks/useVMRequests'
import { useVMResources } from '../hooks/useVMResources'
import { useMediaQuery } from '../hooks/useMediaQuery'
import DestroyModal from '../components/DestroyModal'
import ShareModal from '../components/ShareModal'
import RequestModal from '../components/RequestModal'
import ResourcesModal from '../components/ResourcesModal'
import VMInfoCard from '../components/VMInfoCard'
import VMActionsCard from '../components/VMActionsCard'
import VMResourcesCard from '../components/VMResourcesCard'
import VMHistoryCard from '../components/VMHistoryCard'
import VMAccessCard from '../components/VMAccessCard'
const VMTerminalOverlay = lazy(() => import('../components/VMTerminalOverlay'))
import { CardSkeleton } from '../components/Skeleton'
import { type VMDetail, type VMTask } from '../types/vm'

export default function VMPage() {
  const { vmId } = useParams<{ vmId: string }>()
  const navigate = useNavigate()
  const resources = useResources()
  const me = useUser()
  const { t } = useTranslation('vm')
  const vmStatusEntry = useVMStatus(Number(vmId))
  const isDesktop = useMediaQuery('(min-width: 768px)')

  const [vm, setVm] = useState<VMDetail | null>(null)
  const [tasks, setTasks] = useState<VMTask[]>([])
  const [mobileTermOpen, setMobileTermOpen] = useState(false)
  const [overlayHeight, setOverlayHeight] = useState(0)
  const [onboot, setOnboot] = useState<boolean | null>(null)
  const [deprecatedBannerDismissed, setDeprecatedBannerDismissed] = useState(false)

  const running = vmStatusEntry?.status === 'running'
  const isOwner = !vm || vm.current_user_role === 'owner' || vm.current_user_role === 'admin'
  const canAccessConsole = !me.is_admin || (vm?.current_user_role === 'owner')
  const templateDeprecated = vm !== null && vm.template.is_active === false
  const hasPendingChanges = vm !== null && Array.isArray(vm.pending_changes) && vm.pending_changes.length > 0
  const uptime = vmStatusEntry?.uptime ?? null
  const realmPrefix = me.user_id ? me.user_id.split(':').slice(0, 2).join(':') : null

  const { loadingAction, setLoadingAction, doAction, doDestroy, showDestroyModal, setShowDestroyModal } = useVMActions(vmId)
  const creds = useVMCredentials(vmId, vm)
  const share = useVMShare(vmId, realmPrefix, setLoadingAction)
  const req = useVMRequests(vmId)
  const res = useVMResources(vmId, vm, resources, (updated) => setVm(v => v ? { ...v, ...updated } : v))

  // Fetch VM detail + onboot in parallel on mount
  useEffect(() => {
    if (!vmId) return
    Promise.all([
      apiFetch<VMDetail>(`/api/vms/${vmId}`),
      apiFetch<{ onboot: boolean }>(`/api/vms/${vmId}/onboot`).catch(() => null),
      apiFetch<{ items: VMTask[] }>(`/api/vms/${vmId}/tasks`).catch(() => ({ items: [] })),
    ]).then(([vmData, onbootData, tasksData]) => {
      setVm(vmData)
      if (onbootData) setOnboot(onbootData.onboot)
      setTasks(tasksData.items)
    }).catch((err) => {
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) navigate('/')
    })
  }, [vmId])

  // Refresh tasks + VM detail when status changes
  useEffect(() => {
    if (!vmId || !vmStatusEntry?.status) return
    apiFetch<VMDetail>(`/api/vms/${vmId}`)
      .then(vmData => setVm(vmData))
      .catch(() => {})
    apiFetch<{ items: VMTask[] }>(`/api/vms/${vmId}/tasks`)
      .then(r => setTasks(r.items))
      .catch(() => { /* tasks are non-critical, keep previous state */ })
  }, [vmStatusEntry?.status])

  async function toggleOnboot() {
    if (!vmId) return
    try {
      const r = await apiFetch<{ onboot: boolean }>(`/api/vms/${vmId}/onboot`, { method: 'PUT' })
      setOnboot(r.onboot)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    if (!running) setMobileTermOpen(false)
  }, [running])

  return (
    <>
    {templateDeprecated && !deprecatedBannerDismissed && (
      <div className="fixed top-14 left-0 md:left-16 right-2 z-30 flex items-center gap-3 px-6 py-2.5 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200 text-xs font-medium rounded-b-xl shadow-sm">
        <AlertTriangle size={13} className="shrink-0 text-amber-500" />
        <span className="flex-1">{t('deprecated.banner')}</span>
        <button
          onClick={() => setDeprecatedBannerDismissed(true)}
          className="shrink-0 px-3 py-1 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-[11px] font-semibold transition-colors cursor-pointer"
        >
          OK
        </button>
      </div>
    )}
    {hasPendingChanges && (
      <div className={`fixed ${templateDeprecated && !deprecatedBannerDismissed ? 'top-24' : 'top-14'} left-0 md:left-16 right-2 z-30 flex items-center gap-3 px-6 py-2.5 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200 text-xs font-medium rounded-b-xl shadow-sm`}>
        <AlertTriangle size={13} className="shrink-0 text-blue-500" />
        <span className="flex-1">
          {t('pendingChanges.banner', { changes: vm!.pending_changes!.map(c => t(`pendingChanges.${c}`)).join(', ') })}
        </span>
      </div>
    )}
    {showDestroyModal && (
      <DestroyModal
        vmName={vm?.name}
        loadingAction={loadingAction}
        onClose={() => setShowDestroyModal(false)}
        onConfirm={doDestroy}
      />
    )}
    {share.shareOpen && (
      <ShareModal
        shareUsers={share.shareUsers}
        shareInput={share.shareInput}
        setShareInput={share.setShareInput}
        loadingAction={loadingAction}
        onClose={() => share.setShareOpen(false)}
        onShare={share.doShare}
        onRevoke={share.doRevoke}
      />
    )}
    {req.reqModalOpen && (
      <RequestModal
        vmNetwork={vm?.network ?? null}
        requests={req.requests}
        reqType={req.reqType}
        setReqType={req.setReqType}
        reqDnsLabel={req.reqDnsLabel}
        setReqDnsLabel={req.setReqDnsLabel}
        reqSaving={req.reqSaving}
        onClose={() => req.setReqModalOpen(false)}
        onSubmit={req.doSubmitRequest}
      />
    )}
    {res.resModalOpen && vm && (
      <ResourcesModal
        newCpu={res.newCpu}
        setNewCpu={res.setNewCpu}
        newRam={res.newRam}
        setNewRam={res.setNewRam}
        newDisk={res.newDisk}
        setNewDisk={res.setNewDisk}
        resSaving={res.resSaving}
        maxCpu={res.maxCpu}
        maxRam={res.maxRam}
        maxDisk={res.maxDisk}
        minCpu={res.minCpu}
        minRam={res.minRam}
        minDisk={res.minDisk}
        onClose={() => res.setResModalOpen(false)}
        onSave={res.doSaveResources}
      />
    )}

    {me.is_admin && (
      <button
        onClick={() => navigate('/admin')}
        className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors mb-1 cursor-pointer"
      >
        <ArrowLeft size={13} />
        {t('actions.backToAdmin')}
      </button>
    )}

    <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 xl:grid-rows-4 gap-3 xl:h-full [&>*]:min-w-0">

      {vm ? (
        <VMInfoCard
          vm={vm}
          status={vmStatusEntry?.status ?? null}
          loadingAction={loadingAction}
          running={running}
          isOwner={isOwner}
          uptime={uptime}
          onOpenDnsRequest={() => { req.setReqType('dns'); req.loadRequests(); req.setReqModalOpen(true) }}
          onOpenIpRequest={() => { req.setReqType('ipv4'); req.loadRequests(); req.setReqModalOpen(true) }}
        />
      ) : (
        <CardSkeleton className="md:col-span-2 xl:col-span-2 min-h-[10rem]" />
      )}

      <VMActionsCard
        running={running}
        isOwner={isOwner}
        loadingAction={loadingAction}
        onboot={onboot}
        onToggleOnboot={toggleOnboot}
        onAction={doAction}
        onOpenDestroyModal={() => setShowDestroyModal(true)}
        onOpenShareModal={() => { share.setShareOpen(true); share.loadShareUsers() }}
      />

      {/* Bouton terminal mobile */}
      {vmId && running && canAccessConsole && !templateDeprecated && (
        <button
          onClick={() => { setOverlayHeight(window.innerHeight); setMobileTermOpen(true) }}
          className="md:hidden flex items-center justify-center gap-2 rounded-sm bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-800 dark:hover:bg-neutral-200 border border-neutral-700 dark:border-neutral-300 text-white dark:text-neutral-900 text-sm font-semibold transition-colors cursor-pointer h-12"
        >
          <TerminalSquare size={15} className="shrink-0" />
          {t('actions.launchTerminal')}
        </button>
      )}

      {/* Terminal — tablette & desktop uniquement */}
      {vmId && isDesktop && (
        <div className="hidden md:block md:col-span-3 md:row-span-5 xl:col-start-1 xl:col-span-3 xl:row-start-2 xl:row-span-3 border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm overflow-hidden h-80 md:h-[500px] xl:h-auto relative">
          {running && canAccessConsole && !templateDeprecated && <Suspense fallback={null}><VMTerminal vmId={vmId} /></Suspense>}
          {templateDeprecated && (
            <div className="absolute inset-0 bg-neutral-950 flex flex-col items-center justify-center gap-3 rounded-sm">
              <AlertTriangle size={24} className="text-amber-500" />
              <p className="text-sm text-white/70 font-medium">{t('deprecated.title')}</p>
              <p className="text-xs text-neutral-500 text-center px-6">{t('deprecated.terminalDisabled')}</p>
            </div>
          )}
          {!templateDeprecated && running && !canAccessConsole && (
            <div className="absolute inset-0 bg-neutral-950 flex flex-col items-center justify-center gap-3 rounded-sm">
              <TerminalSquare size={24} className="text-neutral-500" />
              <p className="text-sm text-white/70 font-medium">{t('console.notAvailable')}</p>
              <p className="text-xs text-neutral-500 text-center px-6">{t('console.adminRestriction')}</p>
            </div>
          )}
          {!templateDeprecated && !running && (
            <div className="absolute inset-0 bg-neutral-950 flex flex-col items-center justify-center gap-3 rounded-sm">
              <p className="text-sm text-white/70 font-medium">{t('console.vmStopped')}</p>
              <button
                onClick={() => doAction('start')}
                disabled={!!loadingAction}
                className="flex items-center gap-2 px-4 py-2 rounded-md bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 text-emerald-700 text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
              >
                <Play size={14} />
                {t('actions.startVM')}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="md:col-span-3 xl:col-span-3 flex gap-2 overflow-hidden [&>*]:flex-1 [&>*]:min-w-0">
        <VMResourcesCard
          vm={vm}
          running={running}
          isOwner={isOwner}
          templateDeprecated={templateDeprecated}
          onOpenResModal={() => res.setResModalOpen(true)}
        />
        <VMHistoryCard tasks={tasks} />
      </div>

      <VMAccessCard
        vm={vm}
        running={running}
        isOwner={isOwner}
        creds={creds}
      />

      <Suspense fallback={null}>
        <MetricChart vmId={vmId ?? ''} className="md:col-span-3 md:row-span-2 xl:col-span-3 xl:row-span-2 h-64 md:h-[calc(2*12rem+0.5rem)] xl:h-auto" />
      </Suspense>

    </div>

    {mobileTermOpen && vmId && (
      <Suspense fallback={null}>
        <VMTerminalOverlay
          vmId={vmId}
          vmName={vm?.name}
          overlayHeight={overlayHeight}
          onClose={() => setMobileTermOpen(false)}
        />
      </Suspense>
    )}
    </>
  )
}
