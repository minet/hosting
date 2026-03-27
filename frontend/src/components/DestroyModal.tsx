
interface Props {
  vmName?: string
  loadingAction: string | null
  onClose: () => void
  onConfirm: () => void
}

export default function DestroyModal({ vmName, loadingAction, onClose, onConfirm }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-8 flex flex-col items-center gap-4 max-w-xs w-full mx-4" onClick={e => e.stopPropagation()}>
        <img src="/assets/pinguins/PinguinTriste.svg" alt="Pingouin triste" className="w-24 h-24" />
        <div className="text-center">
          <p className="text-base font-bold text-neutral-800 dark:text-neutral-200">Supprimer <span className="text-red-500">{vmName}</span> ?</p>
          <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">Cette action est irréversible. La VM et toutes ses données seront définitivement supprimées.</p>
        </div>
        <div className="flex gap-3 w-full">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm}
            disabled={!!loadingAction}
            className="flex-1 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
          >
            Supprimer
          </button>
        </div>
      </div>
    </div>
  )
}
