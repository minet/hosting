import { Play, Square, RotateCcw, Share2, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Tooltip from './Tooltip'

interface Props {
  running: boolean
  isOwner: boolean
  loadingAction: string | null
  onboot: boolean | null
  onToggleOnboot: () => void
  onAction: (action: 'start' | 'stop' | 'restart') => void
  onOpenDestroyModal: () => void
  onOpenShareModal: () => void
}

export default function VMActionsCard({ running, isOwner, loadingAction, onboot, onToggleOnboot, onAction, onOpenDestroyModal, onOpenShareModal }: Props) {
  const { t } = useTranslation('vm')
  return (
    <div className="@container flex rounded-sm flex-col gap-1 min-w-0 overflow-hidden xl:justify-center">
      <div className="grid grid-cols-2 grid-rows-3 gap-[clamp(0.25rem,1.5cqw,0.5rem)] h-full">
        {/* Row 1: Auto-start | Destroy/Stop */}
        <Tooltip tip={!isOwner ? t('access.ownerOnly') : undefined}>
          <button
            onClick={onToggleOnboot}
            disabled={!!loadingAction || !isOwner || onboot === null}
            className={`w-full h-full flex items-center justify-center gap-1 rounded-md border text-[clamp(0.55rem,2.5cqw,0.75rem)] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-[clamp(0.25rem,1.5cqw,0.625rem)] ${onboot ? 'bg-violet-50 dark:bg-violet-950 hover:bg-violet-100 dark:hover:bg-violet-900 border-violet-300 dark:border-violet-700 text-violet-700 dark:text-violet-300' : 'bg-neutral-50 dark:bg-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-700 border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400'}`}
          >
            <span>Auto-start</span>
            <span className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${onboot ? 'bg-violet-500' : 'bg-neutral-300 dark:bg-neutral-600'}`}>
              <span className={`inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${onboot ? 'translate-x-3.5' : 'translate-x-0.5'}`} />
            </span>
          </button>
        </Tooltip>
        {running ? (
          <button
            onClick={() => onAction('stop')}
            disabled={!!loadingAction}
            className="flex items-center justify-center gap-1 rounded-md bg-red-50 dark:bg-red-950 hover:bg-red-100 dark:hover:bg-red-900 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 text-[clamp(0.55rem,2.5cqw,0.75rem)] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-[clamp(0.25rem,1.5cqw,0.625rem)]"
          >
            <Square size={13} className="shrink-0" />
            Stop
          </button>
        ) : (
          <Tooltip tip={!isOwner ? t('access.ownerOnly') : undefined}>
            <button
              onClick={onOpenDestroyModal}
              disabled={!!loadingAction || !isOwner}
              className="w-full h-full flex items-center justify-center gap-1 rounded-md bg-red-50 dark:bg-red-950 hover:bg-red-100 dark:hover:bg-red-900 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 text-[clamp(0.55rem,2.5cqw,0.75rem)] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-[clamp(0.25rem,1.5cqw,0.625rem)]"
            >
              <Trash2 size={13} className="shrink-0" />
              Destroy
            </button>
          </Tooltip>
        )}

        {/* Row 2: Restart | Share */}
        <Tooltip tip={!running ? t('actions.vmOff') : undefined}>
          <button
            onClick={() => onAction('restart')}
            disabled={!!loadingAction || !running}
            className="w-full h-full flex items-center justify-center gap-1 rounded-md bg-amber-50 dark:bg-amber-950 hover:bg-amber-100 dark:hover:bg-amber-900 border border-amber-300 dark:border-amber-700 text-amber-600 dark:text-amber-400 text-[clamp(0.55rem,2.5cqw,0.75rem)] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-[clamp(0.25rem,1.5cqw,0.625rem)]"
          >
            <RotateCcw size={13} className="shrink-0" />
            Restart
          </button>
        </Tooltip>
        <Tooltip tip={!isOwner ? t('access.ownerOnly') : undefined}>
          <button
            onClick={onOpenShareModal}
            disabled={!isOwner}
            className="w-full h-full flex items-center justify-center gap-1 rounded-md bg-blue-50 dark:bg-blue-950 hover:bg-blue-100 dark:hover:bg-blue-900 border border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400 text-[clamp(0.55rem,2.5cqw,0.75rem)] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-[clamp(0.25rem,1.5cqw,0.625rem)]"
          >
            <Share2 size={13} className="shrink-0" />
            Share
          </button>
        </Tooltip>

        {/* Row 3: Start (full width) */}
        <Tooltip tip={running ? t('actions.alreadyOn') : undefined} className="col-span-2">
          <button
            onClick={() => onAction('start')}
            disabled={!!loadingAction || running}
            className="w-full h-full flex items-center justify-center gap-1 rounded-md bg-emerald-50 dark:bg-emerald-950 hover:bg-emerald-100 dark:hover:bg-emerald-900 border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 text-[clamp(0.55rem,2.5cqw,0.75rem)] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-[clamp(0.25rem,1.5cqw,0.625rem)]"
          >
            <Play size={13} className="shrink-0" />
            Start
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
