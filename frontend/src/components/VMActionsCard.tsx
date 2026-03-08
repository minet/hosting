import { Play, Square, RotateCcw, Share2, Trash2 } from 'lucide-react'
import Tooltip from './Tooltip'

interface Props {
  running: boolean
  isOwner: boolean
  loadingAction: string | null
  onAction: (action: 'start' | 'stop' | 'restart') => void
  onOpenDestroyModal: () => void
  onOpenShareModal: () => void
}

export default function VMActionsCard({ running, isOwner, loadingAction, onAction, onOpenDestroyModal, onOpenShareModal }: Props) {
  return (
    <div className="flex rounded-sm bg-white px-4 py-3 flex-col gap-2 h-32 md:h-48 xl:h-auto xl:justify-center">
      <div className="grid grid-cols-2 gap-2 h-full">
        <Tooltip tip={running ? 'Déjà allumée' : undefined}>
          <button
            onClick={() => onAction('start')}
            disabled={!!loadingAction || running}
            className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 text-emerald-700 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <Play size={13} className="shrink-0" />
            Start
          </button>
        </Tooltip>
        {running ? (
          <button
            onClick={() => onAction('stop')}
            disabled={!!loadingAction}
            className="flex items-center justify-center gap-1.5 rounded-md bg-red-50 hover:bg-red-100 border border-red-300 text-red-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <Square size={13} className="shrink-0" />
            Stop
          </button>
        ) : (
          <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : undefined}>
            <button
              onClick={onOpenDestroyModal}
              disabled={!!loadingAction || !isOwner}
              className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-red-50 hover:bg-red-100 border border-red-300 text-red-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              <Trash2 size={13} className="shrink-0" />
              Destroy
            </button>
          </Tooltip>
        )}
        <Tooltip tip={!running ? 'VM éteinte' : undefined}>
          <button
            onClick={() => onAction('restart')}
            disabled={!!loadingAction || !running}
            className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <RotateCcw size={13} className="shrink-0" />
            Restart
          </button>
        </Tooltip>
        <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : undefined}>
          <button
            onClick={onOpenShareModal}
            disabled={!isOwner}
            className="w-full h-full flex items-center justify-center gap-1.5 rounded-md bg-blue-50 hover:bg-blue-100 border border-blue-300 text-blue-600 text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <Share2 size={13} className="shrink-0" />
            Share
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
