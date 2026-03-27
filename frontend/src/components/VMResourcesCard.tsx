import { Cpu, MemoryStick, HardDrive, SlidersHorizontal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Tooltip from './Tooltip'
import { type VMDetail } from '../types/vm'

interface Props {
  vm: VMDetail | null
  running: boolean
  isOwner: boolean
  templateDeprecated: boolean
  onOpenResModal: () => void
}

export default function VMResourcesCard({ vm, running, isOwner, templateDeprecated, onOpenResModal }: Props) {
  const { t } = useTranslation('vm')
  const tc = useTranslation().t
  const modifyDisabled = !isOwner || running || templateDeprecated
  const modifyTip = !isOwner
    ? t('access.ownerOnly')
    : running
    ? t('access.stopFirst')
    : templateDeprecated
    ? t('deprecated.resourcesDisabled')
    : undefined

  return (
    <div className="border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 px-5 py-4 flex flex-col min-w-0 overflow-hidden">
      <div className="flex items-center justify-between mb-3 min-w-0 gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500 truncate">{t('resources.allocated')}</p>
        <div className="flex items-center gap-1.5 shrink-0">
          <Tooltip tip={modifyTip} align="right">
            <button
              onClick={onOpenResModal}
              disabled={modifyDisabled}
              className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-[10px] font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <SlidersHorizontal size={10} />
              {tc('modify')}
            </button>
          </Tooltip>
        </div>
      </div>
      {vm ? (
        <div className="flex flex-col gap-2 min-w-0">
          <div className="flex items-center justify-between min-w-0 gap-2">
            <span className="flex items-center gap-1.5 text-xs text-neutral-500 dark:text-neutral-400 shrink-0"><Cpu size={13} className="text-violet-500" />CPU</span>
            <span className="text-sm font-bold text-neutral-800 dark:text-neutral-200 truncate">{vm.cpu_cores} <span className="text-xs font-normal text-neutral-400 dark:text-neutral-500">{tc('cores', { count: vm.cpu_cores })}</span></span>
          </div>
          <div className="flex items-center justify-between min-w-0 gap-2">
            <span className="flex items-center gap-1.5 text-xs text-neutral-500 dark:text-neutral-400 shrink-0"><MemoryStick size={13} className="text-blue-500" />RAM</span>
            <span className="text-sm font-bold text-neutral-800 dark:text-neutral-200 truncate">{Math.round(vm.ram_mb / 1024)} <span className="text-xs font-normal text-neutral-400 dark:text-neutral-500">{tc('gb')}</span></span>
          </div>
          <div className="flex items-center justify-between min-w-0 gap-2">
            <span className="flex items-center gap-1.5 text-xs text-neutral-500 dark:text-neutral-400 shrink-0"><HardDrive size={13} className="text-emerald-500" />{t('resources.disk')}</span>
            <span className="text-sm font-bold text-neutral-800 dark:text-neutral-200 truncate">{vm.disk_gb} <span className="text-xs font-normal text-neutral-400 dark:text-neutral-500">{tc('gb')}</span></span>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-neutral-300 dark:text-neutral-600 text-xs">—</div>
      )}
    </div>
  )
}
