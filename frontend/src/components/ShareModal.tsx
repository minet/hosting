import { X } from 'lucide-react'
import { Trans, useTranslation } from 'react-i18next'

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
  const { t } = useTranslation('vm')
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-6 flex flex-col gap-4 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-neutral-800 dark:text-neutral-200">{t('share.title')}</p>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer"><X size={16} /></button>
        </div>

        <div className="flex justify-center gap-2">
          <img src="/assets/pinguins/PinguinTourne.svg" alt="Pinguin tourne" className="w-16 h-16" />
          <img src="/assets/pinguins/PinguinsVP.svg" alt="Pinguins VP" className="w-16 h-16" />
        </div>

        <div className="flex flex-col gap-2 bg-neutral-50 dark:bg-neutral-800 border border-neutral-100 dark:border-neutral-700 rounded-lg p-3 text-xs text-neutral-500 dark:text-neutral-400">
          <p className="font-semibold text-neutral-700 dark:text-neutral-300">{t('share.findUserId')}</p>
          <p><Trans i18nKey="share.findUserIdDesc" ns="vm" components={{ mono: <span className="font-mono text-neutral-700 dark:text-neutral-300" /> }} /></p>
        </div>

        {shareUsers.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">{t('share.sharedAccess')}</p>
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
          <p className="font-semibold">{t('share.sharedRights')}</p>
          <ul className="flex flex-col gap-1 list-disc list-inside text-blue-600 dark:text-blue-400">
            <li>{t('share.rightsList.viewStatus')}</li>
            <li>{t('share.rightsList.accessTerminal')}</li>
            <li>{t('share.rightsList.startStopRestart')}</li>
          </ul>
          <p className="text-blue-500 dark:text-blue-400">{t('share.cannotModify')}</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">{t('share.memberNumber')}</label>
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
              {t('share.shareButton')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
