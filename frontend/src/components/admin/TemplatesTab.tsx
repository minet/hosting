import { useState } from 'react'
import { Loader, Plus, Trash2, Pencil, Check, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAdminTemplates } from '../../hooks/useAdminTemplates'
import type { AdminTemplate, AdminTemplateUpdatePayload } from '../../hooks/useAdminTemplates'

const inputCls = "text-sm border border-neutral-200 dark:border-neutral-600 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-blue-400 bg-transparent text-neutral-900 dark:text-neutral-100"

export default function TemplatesTab() {
  const { templates, loading, create, update, remove, toggleActive } = useAdminTemplates()
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')
  const [newVersion, setNewVersion] = useState('')
  const [newMinCpu, setNewMinCpu] = useState('1')
  const [newMinRam, setNewMinRam] = useState('2')
  const [newMinDisk, setNewMinDisk] = useState('10')
  const [newComment, setNewComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [editId, setEditId] = useState<number | null>(null)
  const [editFields, setEditFields] = useState<AdminTemplateUpdatePayload>({})
  const { t } = useTranslation('admin')
  const tc = useTranslation().t

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const id = parseInt(newId, 10)
    if (!id || id < 1001 || id > 1999 || !newName.trim()) return
    setSubmitting(true)
    try {
      await create({
        template_id: id,
        name: newName.trim(),
        version: newVersion.trim() || null,
        min_cpu_cores: parseInt(newMinCpu, 10) || 1,
        min_ram_gb: parseInt(newMinRam, 10) || 2,
        min_disk_gb: parseInt(newMinDisk, 10) || 10,
        comment: newComment.trim() || null,
      })
      setNewId('')
      setNewName('')
      setNewVersion('')
      setNewMinCpu('1')
      setNewMinRam('2')
      setNewMinDisk('10')
      setNewComment('')
    } catch (err: any) {
      setError(err.message ?? tc('error'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(templateId: number) {
    setError('')
    try {
      await remove(templateId)
    } catch (err: any) {
      setError(err.message ?? tc('error'))
    }
  }

  async function handleToggleActive(templateId: number, current: boolean) {
    setError('')
    try {
      await toggleActive(templateId, !current)
    } catch (err: any) {
      setError(err.message ?? tc('error'))
    }
  }

  function startEdit(tpl: AdminTemplate) {
    setEditId(tpl.template_id)
    setEditFields({
      name: tpl.name,
      version: tpl.version ?? '',
      min_cpu_cores: tpl.min_cpu_cores,
      min_ram_gb: tpl.min_ram_gb,
      min_disk_gb: tpl.min_disk_gb,
      comment: tpl.comment ?? '',
    })
  }

  async function saveEdit() {
    if (editId === null) return
    setError('')
    try {
      const fields: AdminTemplateUpdatePayload = {}
      const tpl = templates.find(t => t.template_id === editId)
      if (!tpl) return
      if (editFields.name && editFields.name !== tpl.name) fields.name = editFields.name
      if ((editFields.version ?? '') !== (tpl.version ?? '')) fields.version = editFields.version || null
      if (editFields.min_cpu_cores !== undefined && editFields.min_cpu_cores !== tpl.min_cpu_cores) fields.min_cpu_cores = editFields.min_cpu_cores
      if (editFields.min_ram_gb !== undefined && editFields.min_ram_gb !== tpl.min_ram_gb) fields.min_ram_gb = editFields.min_ram_gb
      if (editFields.min_disk_gb !== undefined && editFields.min_disk_gb !== tpl.min_disk_gb) fields.min_disk_gb = editFields.min_disk_gb
      if ((editFields.comment ?? '') !== (tpl.comment ?? '')) fields.comment = editFields.comment || null
      if (Object.keys(fields).length > 0) {
        await update(editId, fields)
      }
      setEditId(null)
    } catch (err: any) {
      setError(err.message ?? tc('error'))
    }
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between shrink-0">
        <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">Templates</h1>
        <span className="text-xs text-neutral-400 dark:text-neutral-500 font-mono">
          {loading ? tc('loading') : t('templates.count', { count: templates.length })}
        </span>
      </div>

      {/* Add form */}
      <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3 shrink-0">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.proxmoxId')}</label>
          <input
            type="number" min={1001} max={1999} value={newId} onChange={e => setNewId(e.target.value)}
            placeholder="1001–1999"
            className={`w-28 ${inputCls}`}
            required
          />
        </div>
        <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.name')}</label>
          <input
            type="text" value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="ex: Debian 12"
            className={inputCls}
            required
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.version')}</label>
          <input
            type="text" value={newVersion} onChange={e => setNewVersion(e.target.value)}
            placeholder="ex: 12"
            className={`w-20 ${inputCls}`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.minCpu')}</label>
          <input
            type="number" min={1} value={newMinCpu} onChange={e => setNewMinCpu(e.target.value)}
            className={`w-16 ${inputCls}`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.minRam')}</label>
          <input
            type="number" min={1} value={newMinRam} onChange={e => setNewMinRam(e.target.value)}
            className={`w-16 ${inputCls}`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.minDisk')}</label>
          <input
            type="number" min={1} value={newMinDisk} onChange={e => setNewMinDisk(e.target.value)}
            className={`w-16 ${inputCls}`}
          />
        </div>
        <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
          <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">{t('templates.comment')}</label>
          <input
            type="text" value={newComment} onChange={e => setNewComment(e.target.value)}
            placeholder={t('templates.commentPlaceholder')}
            className={inputCls}
          />
        </div>
        <button
          type="submit" disabled={submitting}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
        >
          <Plus size={14} /> {t('templates.add')}
        </button>
      </form>

      {error && (
        <p className="text-xs text-red-500 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-md px-3 py-2">{error}</p>
      )}

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-auto rounded-sm border border-neutral-200 dark:border-neutral-700 shadow-sm">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10 border-b border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider w-20 border-r border-neutral-200 dark:border-neutral-700">ID</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider border-r border-neutral-200 dark:border-neutral-700">{t('templates.name')}</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider w-20 border-r border-neutral-200 dark:border-neutral-700">{t('templates.version')}</th>
              <th className="px-3 py-2 text-center text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider w-28 border-r border-neutral-200 dark:border-neutral-700">{t('templates.minResources')}</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider border-r border-neutral-200 dark:border-neutral-700">{t('templates.comment')}</th>
              <th className="px-3 py-2 text-center text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider w-20 border-r border-neutral-200 dark:border-neutral-700">{t('templates.active')}</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider w-20"></th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {loading && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs"><Loader size={14} className="animate-spin inline mr-2" />{tc('loading')}</td></tr>
            )}
            {!loading && templates.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">{t('templates.noTemplate')}</td></tr>
            )}
            {templates.map(tpl => {
              const isEditing = editId === tpl.template_id
              return (
                <tr key={tpl.template_id} className={`hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors ${!tpl.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-3 py-2 font-mono text-xs text-neutral-500 dark:text-neutral-400 border-r border-neutral-100 dark:border-neutral-800">{tpl.template_id}</td>
                  <td className="px-3 py-2 text-neutral-700 dark:text-neutral-300 border-r border-neutral-100 dark:border-neutral-800">
                    {isEditing ? (
                      <input className={`w-full ${inputCls}`} value={editFields.name ?? ''} onChange={e => setEditFields(f => ({ ...f, name: e.target.value }))} />
                    ) : tpl.name}
                  </td>
                  <td className="px-3 py-2 text-neutral-500 dark:text-neutral-400 text-xs border-r border-neutral-100 dark:border-neutral-800">
                    {isEditing ? (
                      <input className={`w-full ${inputCls}`} value={(editFields.version as string) ?? ''} onChange={e => setEditFields(f => ({ ...f, version: e.target.value }))} />
                    ) : (tpl.version ?? '—')}
                  </td>
                  <td className="px-3 py-2 text-center text-xs text-neutral-500 dark:text-neutral-400 border-r border-neutral-100 dark:border-neutral-800">
                    {isEditing ? (
                      <div className="flex gap-1 justify-center">
                        <input type="number" min={1} className={`w-12 ${inputCls} text-center`} value={editFields.min_cpu_cores ?? 1} onChange={e => setEditFields(f => ({ ...f, min_cpu_cores: Number(e.target.value) }))} />
                        <input type="number" min={1} className={`w-12 ${inputCls} text-center`} value={editFields.min_ram_gb ?? 2} onChange={e => setEditFields(f => ({ ...f, min_ram_gb: Number(e.target.value) }))} />
                        <input type="number" min={1} className={`w-12 ${inputCls} text-center`} value={editFields.min_disk_gb ?? 10} onChange={e => setEditFields(f => ({ ...f, min_disk_gb: Number(e.target.value) }))} />
                      </div>
                    ) : (
                      <span className="font-mono">{tpl.min_cpu_cores}C / {tpl.min_ram_gb}G / {tpl.min_disk_gb}G</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-neutral-500 dark:text-neutral-400 text-xs border-r border-neutral-100 dark:border-neutral-800 max-w-[200px] truncate" title={tpl.comment ?? ''}>
                    {isEditing ? (
                      <input className={`w-full ${inputCls}`} value={(editFields.comment as string) ?? ''} onChange={e => setEditFields(f => ({ ...f, comment: e.target.value }))} />
                    ) : (tpl.comment ?? '—')}
                  </td>
                  <td className="px-3 py-2 text-center border-r border-neutral-100 dark:border-neutral-800">
                    <button
                      onClick={() => handleToggleActive(tpl.template_id, tpl.is_active)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer ${tpl.is_active ? 'bg-emerald-500' : 'bg-neutral-300 dark:bg-neutral-600'}`}
                      title={tpl.is_active ? t('templates.deactivate') : t('templates.activate')}
                    >
                      <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${tpl.is_active ? 'translate-x-4' : 'translate-x-1'}`} />
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {isEditing ? (
                        <>
                          <button onClick={saveEdit} className="text-emerald-500 hover:text-emerald-600 transition-colors cursor-pointer" title={tc('save')}>
                            <Check size={14} />
                          </button>
                          <button onClick={() => setEditId(null)} className="text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer" title={tc('cancel')}>
                            <X size={14} />
                          </button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => startEdit(tpl)} className="text-neutral-300 dark:text-neutral-600 hover:text-blue-500 transition-colors cursor-pointer" title={tc('edit')}>
                            <Pencil size={14} />
                          </button>
                          <button onClick={() => handleDelete(tpl.template_id)} className="text-neutral-300 dark:text-neutral-600 hover:text-red-500 transition-colors cursor-pointer" title={tc('delete')}>
                            <Trash2 size={14} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
