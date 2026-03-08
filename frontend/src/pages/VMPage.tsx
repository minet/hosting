import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Play, TerminalSquare } from 'lucide-react'
import { apiFetch } from '../api'
import VMTerminal from '../components/VMTerminal'
import MetricChart from '../components/MetricChart'
import { useVMStatus } from '../contexts/VMStatusContext'
import { useResources } from '../hooks/useResources'
import { useUser } from '../contexts/UserContext'
import { useVMActions } from '../hooks/useVMActions'
import { useVMCredentials } from '../hooks/useVMCredentials'
import { useVMShare } from '../hooks/useVMShare'
import { useVMRequests } from '../hooks/useVMRequests'
import { useVMResources } from '../hooks/useVMResources'
import DestroyModal from '../components/DestroyModal'
import ShareModal from '../components/ShareModal'
import RequestModal from '../components/RequestModal'
import ResourcesModal from '../components/ResourcesModal'
import VMInfoCard from '../components/VMInfoCard'
import VMActionsCard from '../components/VMActionsCard'
import VMResourcesCard from '../components/VMResourcesCard'
import VMHistoryCard from '../components/VMHistoryCard'
import VMAccessCard from '../components/VMAccessCard'
import VMTerminalOverlay from '../components/VMTerminalOverlay'
import { type VMDetail, type VMTask } from '../types/vm'

export default function VMPage() {
  const { vmId } = useParams<{ vmId: string }>()
  const navigate = useNavigate()
  const resources = useResources()
  const me = useUser()
  const vmStatusEntry = useVMStatus(Number(vmId))

  const [vm, setVm] = useState<VMDetail | null>(null)
  const [tasks, setTasks] = useState<VMTask[]>([])
  const [mobileTermOpen, setMobileTermOpen] = useState(false)
  const [overlayHeight, setOverlayHeight] = useState(0)
  const isDesktop = useState(() => window.innerWidth >= 768)[0]

  const running = vmStatusEntry?.status === 'running'
  const isOwner = !vm || vm.current_user_role === 'owner' || vm.current_user_role === 'admin'
  const uptime = vmStatusEntry?.uptime ?? null
  const realmPrefix = me.user_id ? me.user_id.split(':').slice(0, 2).join(':') : null

  const { loadingAction, setLoadingAction, doAction, doDestroy, showDestroyModal, setShowDestroyModal } = useVMActions(vmId)
  const creds = useVMCredentials(vmId, vm)
  const share = useVMShare(vmId, realmPrefix, setLoadingAction)
  const req = useVMRequests(vmId)
  const res = useVMResources(vmId, vm, resources, (updated) => setVm(v => v ? { ...v, ...updated } : v))

  useEffect(() => {
    if (!vmId) return
    apiFetch<VMDetail>(`/api/vms/${vmId}`)
      .then(setVm)
      .catch((res) => { if (res?.status === 403) navigate('/') })
  }, [vmId])

  useEffect(() => {
    if (!vmId) return
    apiFetch<{ items: VMTask[] }>(`/api/vms/${vmId}/tasks`).then(r => setTasks(r.items)).catch(() => null)
  }, [vmId, vmStatusEntry?.status])

  useEffect(() => {
    if (!running) setMobileTermOpen(false)
  }, [running])

  return (
    <>
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
        onClose={() => res.setResModalOpen(false)}
        onSave={res.doSaveResources}
      />
    )}

    <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 xl:grid-rows-4 gap-2 xl:h-full">

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
        <div className="md:col-span-2 xl:col-span-2 border border-neutral-100 shadow-md rounded-sm bg-white px-5 py-4 flex items-center justify-center text-neutral-300 text-sm h-auto md:h-48 xl:h-auto">
          Chargement...
        </div>
      )}

      <VMActionsCard
        running={running}
        isOwner={isOwner}
        loadingAction={loadingAction}
        onAction={doAction}
        onOpenDestroyModal={() => setShowDestroyModal(true)}
        onOpenShareModal={() => { share.setShareOpen(true); share.loadShareUsers() }}
      />

      {/* Bouton terminal mobile */}
      {vmId && running && (
        <button
          onClick={() => { setOverlayHeight(window.innerHeight); setMobileTermOpen(true) }}
          className="md:hidden flex items-center justify-center gap-2 rounded-sm bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-white text-sm font-semibold transition-colors cursor-pointer h-12"
        >
          <TerminalSquare size={15} className="shrink-0" />
          Lancer le terminal
        </button>
      )}

      {/* Terminal — tablette & desktop uniquement */}
      {vmId && isDesktop && (
        <div className="hidden md:block md:col-span-3 md:row-span-5 xl:col-start-1 xl:col-span-3 xl:row-start-2 xl:row-span-3 border border-neutral-100 shadow-md rounded-sm overflow-hidden h-80 md:h-[500px] xl:h-auto relative">
          {running && <VMTerminal vmId={vmId} />}
          {!running && (
            <div className="absolute inset-0 bg-neutral-950 flex flex-col items-center justify-center gap-3 rounded-sm">
              <p className="text-sm text-white/70 font-medium">La VM est éteinte</p>
              <button
                onClick={() => doAction('start')}
                disabled={!!loadingAction}
                className="flex items-center gap-2 px-4 py-2 rounded-md bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 text-emerald-700 text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
              >
                <Play size={14} />
                Allumer la VM
              </button>
            </div>
          )}
        </div>
      )}

      <VMResourcesCard
        vm={vm}
        running={running}
        isOwner={isOwner}
        onOpenResModal={() => res.setResModalOpen(true)}
      />

      <VMHistoryCard tasks={tasks} />

      <VMAccessCard
        vm={vm}
        running={running}
        isOwner={isOwner}
        credUsername={creds.credUsername}
        setCredUsername={creds.setCredUsername}
        credPassword={creds.credPassword}
        setCredPassword={creds.setCredPassword}
        credSshKey={creds.credSshKey}
        setCredSshKey={creds.setCredSshKey}
        showPassword={creds.showPassword}
        setShowPassword={creds.setShowPassword}
        credSaving={creds.credSaving}
        credSuccess={creds.credSuccess}
        doSaveCreds={creds.doSaveCreds}
      />

      <MetricChart vmId={vmId} className="md:col-span-3 md:row-span-2 xl:col-span-3 xl:row-span-2 h-64 md:h-[calc(2*12rem+0.5rem)] xl:h-auto" />

    </div>

    {mobileTermOpen && vmId && (
      <VMTerminalOverlay
        vmId={vmId}
        vmName={vm?.name}
        overlayHeight={overlayHeight}
        onClose={() => setMobileTermOpen(false)}
      />
    )}
    </>
  )
}
