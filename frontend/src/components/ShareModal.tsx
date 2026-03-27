import { X } from 'lucide-react'

interface Props {
  shareUsers: { user_id: string; role: string }[]
  shareInput: string
  setShareInput: (v: string) => void
  loadingAction: string | null
  onClose: () => void
  onShare: () => void
  onRevoke: (userId: string) => void
}

export default function ShareModal({ shareUsers, shareInput, setShareInput, loadingAction, onClose, onShare, onRevoke }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-6 flex flex-col gap-4 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-neutral-800 dark:text-neutral-200">Partager la VM</p>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer"><X size={16} /></button>
        </div>

        <div className="flex flex-col gap-2 bg-neutral-50 dark:bg-neutral-800 border border-neutral-100 dark:border-neutral-700 rounded-lg p-3 text-xs text-neutral-500 dark:text-neutral-400">
          <p className="font-semibold text-neutral-700 dark:text-neutral-300">Comment trouver l'ID d'un utilisateur ?</p>
          <p>Chaque membre MiNET possède un numéro d'adhérent visible sur la page d'accueil de Hosting, affiché en petit à côté de son prénom sous la forme <span className="font-mono text-neutral-700 dark:text-neutral-300">#12345</span>.</p>
        </div>

        {shareUsers.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Accès partagés</p>
            <div className="flex flex-col gap-1">
              {shareUsers.map(u => {
                const adh = u.user_id.split(':').at(-1)
                return (
                  <div key={u.user_id} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-neutral-50 dark:bg-neutral-800 border border-neutral-100 dark:border-neutral-700">
                    <span className="text-xs font-mono text-neutral-600 dark:text-neutral-400 flex-1">#{adh}</span>
                    <button onClick={() => onRevoke(u.user_id)} className="text-neutral-300 dark:text-neutral-600 hover:text-red-400 transition-colors cursor-pointer">
                      <X size={13} />
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-2 bg-blue-50 dark:bg-blue-950 border border-blue-100 dark:border-blue-800 rounded-lg p-3 text-xs text-blue-700 dark:text-blue-300">
          <p className="font-semibold">Droits de l'utilisateur partagé</p>
          <ul className="flex flex-col gap-1 list-disc list-inside text-blue-600 dark:text-blue-400">
            <li>Voir le statut et les métriques de la VM</li>
            <li>Accéder au terminal</li>
            <li>Démarrer / arrêter / redémarrer</li>
          </ul>
          <p className="text-blue-500 dark:text-blue-400">Il ne peut pas modifier les ressources, les accès ni supprimer la VM.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Numéro d'adhérent</label>
          <div className="flex gap-2">
            <input
              autoFocus
              value={shareInput}
              onChange={e => setShareInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && onShare()}
              placeholder="12345"
              className="flex-1 border border-neutral-200 dark:border-neutral-700 rounded-md px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-300 bg-transparent text-neutral-900 dark:text-neutral-100"
            />
            <button
              onClick={onShare}
              disabled={!!loadingAction || !shareInput.trim()}
              className="px-4 py-1.5 rounded-md bg-blue-500 hover:bg-blue-600 text-white text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              Partager
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
