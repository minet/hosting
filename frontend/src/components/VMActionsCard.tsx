import { Play, Square, RotateCcw, Share2, Trash2 } from 'lucide-react'
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
  return (
    <div className="flex rounded-sm bg-white px-4 py-3 flex-col gap-2 min-w-0 overflow-hidden xl:justify-center">
      <div className="grid grid-cols-2 gap-2 h-full">
        {/* Row 1: Auto-start | Destroy/Stop */}
        <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : undefined}>
          <button
            onClick={onToggleOnboot}
            disabled={!!loadingAction || !isOwner || onboot === null}
            className="w-full h-full flex items-center justify-center gap-2 rounded-md bg-neutral-50 hover:bg-neutral-100 border border-neutral-200 text-xs font-semibold text-neutral-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-2.5"
          >
            <span>Auto-start</span>
            <span className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${onboot ? 'bg-violet-500' : 'bg-neutral-300'}`}>
              <span className={`inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${onboot ? 'translate-x-3.5' : 'translate-x-0.5'}`} />
            </span>
          </button>
        </Tooltip>
        {running ? (
          <button
            onClick={() => onAction('stop')}
            disabled={!!loadingAction}
            className="flex items-center justify-center gap-1.5 rounded-md bg-red-50 hover:bg-red-100 border border-red-300 text-red-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-2.5"
          >
            <Square size={13} className="shrink-0" />
            Stop
          </button>
        ) : (
          <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : undefined}>
            <button
              onClick={onOpenDestroyModal}
              disabled={!!loadingAction || !isOwner}
              className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-red-50 hover:bg-red-100 border border-red-300 text-red-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-2.5"
            >
              <Trash2 size={13} className="shrink-0" />
              Destroy
            </button>
          </Tooltip>
        )}

        {/* Row 2: Restart | Share */}
        <Tooltip tip={!running ? 'VM éteinte' : undefined}>
          <button
            onClick={() => onAction('restart')}
            disabled={!!loadingAction || !running}
            className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-2.5"
          >
            <RotateCcw size={13} className="shrink-0" />
            Restart
          </button>
        </Tooltip>
        <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : undefined}>
          <button
            onClick={onOpenShareModal}
            disabled={!isOwner}
            className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-blue-50 hover:bg-blue-100 border border-blue-300 text-blue-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-2.5"
          >
            <Share2 size={13} className="shrink-0" />
            Share
          </button>
        </Tooltip>

        {/* Row 3: Start (full width) */}
        <Tooltip tip={running ? 'Déjà allumée' : undefined} className="col-span-2">
          <button
            onClick={() => onAction('start')}
            disabled={!!loadingAction || running}
            className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 text-emerald-700 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer py-2.5"
          >
            <Play size={13} className="shrink-0" />
            Start
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
