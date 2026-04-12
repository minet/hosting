import { useEffect, useState } from 'react'
import { Loader, X, FileStack } from 'lucide-react'
import { apiFetch } from '../../api'

interface Template {
  template_id: number
  name: string
  version: string | null
  is_active: boolean
}

interface Props {
  vmId: number
  vmName: string
  currentTemplateId: number
  onConfirm: (templateId: number) => Promise<void>
  onClose: () => void
}

export default function ChangeTemplateModal({ vmId, vmName, currentTemplateId, onConfirm, onClose }: Props) {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ items: Template[] }>('/api/admin/templates')
      .then(r => setTemplates(r.items))
      .finally(() => setLoading(false))
  }, [])

  async function handleConfirm() {
    if (selected === null) return
    setSaving(true)
    setError(null)
    try {
      await onConfirm(selected)
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-6 flex flex-col gap-4 max-w-md w-full mx-4 max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-neutral-800 dark:text-neutral-200">
              Changer le template de <span className="text-blue-500">{vmName} <span className="text-sm font-mono text-neutral-400">#{vmId}</span></span>
            </h2>
            <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
              Met à jour uniquement la référence en base — ne re-provisionne pas la VM.
            </p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer shrink-0 ml-3">
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-xs text-neutral-400 py-4 justify-center">
            <Loader size={12} className="animate-spin" /> Chargement des templates…
          </div>
        ) : (
          <div className="overflow-y-auto max-h-64 border border-neutral-200 dark:border-neutral-700 rounded-md divide-y divide-neutral-100 dark:divide-neutral-800">
            {templates.length === 0 && (
              <p className="text-xs text-neutral-400 py-3 text-center">Aucun template disponible</p>
            )}
            {templates.map(tpl => {
              const isCurrent = tpl.template_id === currentTemplateId
              const isSelected = selected === tpl.template_id
              return (
                <button
                  key={tpl.template_id}
                  onClick={() => !isCurrent && setSelected(isSelected ? null : tpl.template_id)}
                  disabled={isCurrent}
                  className={`w-full px-3 py-2 text-left text-xs transition-colors cursor-pointer disabled:cursor-default ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300'
                      : isCurrent
                        ? 'bg-neutral-50 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-500'
                        : 'hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{tpl.name}</span>
                    {tpl.version && <span className="text-neutral-400 dark:text-neutral-500">{tpl.version}</span>}
                    {isCurrent && <span className="ml-auto text-[10px] font-semibold text-neutral-400 dark:text-neutral-500">actuel</span>}
                    {!tpl.is_active && <span className="ml-auto text-[10px] font-semibold text-amber-500">inactif</span>}
                    <span className="font-mono text-neutral-300 dark:text-neutral-600 text-[10px] ml-auto">#{tpl.template_id}</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {error && <p className="text-xs text-red-500">{error}</p>}

        <div className="flex gap-3">
          <button onClick={onClose} disabled={saving}
            className="flex-1 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer disabled:opacity-40">
            Annuler
          </button>
          <button onClick={handleConfirm} disabled={saving || selected === null}
            className="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center gap-2">
            {saving ? <Loader size={14} className="animate-spin" /> : <FileStack size={14} />}
            Changer
          </button>
        </div>
      </div>
    </div>
  )
}
