import { SquarePen, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface Props {
  currentName: string
  newName: string
  setNewName: (v: string) => void
  error?: string | null
  saving: boolean
  onClose: () => void
  onSave: () => void
}

export default function RenameModal({
  currentName,
  newName,
  setNewName,
  error,
  saving,
  onClose,
  onSave,
}: Props) {
  const { t } = useTranslation('vm')
  const tc = useTranslation().t

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-6 flex flex-col gap-4 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SquarePen size={16} className="text-blue-500" />
            <p className="text-sm font-bold text-neutral-800 dark:text-neutral-200">{t('rename.title')}</p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
              {t('rename.nameLabel')}
            </label>
            <input
              autoFocus
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder={currentName}
              maxLength={60}
              className="w-full border border-neutral-200 dark:border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 bg-white dark:bg-neutral-800"
            />
            {error && <p className="text-xs text-red-500 mt-0.5">{error}</p>}
            <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
              {t('rename.nameHint')}
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
            >
              {tc('cancel')}
            </button>
            <button
              type="submit"
              disabled={saving || !newName.trim() || newName.trim() === currentName}
              className="flex-1 py-2 rounded-lg bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {saving ? '…' : tc('save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
