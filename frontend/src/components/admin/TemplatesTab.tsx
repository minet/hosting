import { useState } from 'react'
import { Loader, Plus, Trash2 } from 'lucide-react'
import { useAdminTemplates } from '../../hooks/useAdminTemplates'

export default function TemplatesTab() {
  const { templates, loading, create, remove } = useAdminTemplates()
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const id = parseInt(newId, 10)
    if (!id || id < 1001 || id > 1999 || !newName.trim()) return
    setSubmitting(true)
    try {
      await create(id, newName.trim())
      setNewId('')
      setNewName('')
    } catch (err: any) {
      setError(err.message ?? 'Erreur')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(templateId: number) {
    setError('')
    try {
      await remove(templateId)
    } catch (err: any) {
      setError(err.message ?? 'Erreur')
    }
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between shrink-0">
        <h1 className="text-base font-semibold text-neutral-800">Templates</h1>
        <span className="text-xs text-neutral-400 font-mono">
          {loading ? 'Chargement…' : `${templates.length} template${templates.length !== 1 ? 's' : ''}`}
        </span>
      </div>

      {/* Add form */}
      <form onSubmit={handleAdd} className="flex items-end gap-3 shrink-0">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-neutral-500">ID Proxmox</label>
          <input
            type="number" min={1001} max={1999} value={newId} onChange={e => setNewId(e.target.value)}
            placeholder="1001–1999"
            className="w-28 text-sm border border-neutral-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-blue-400"
            required
          />
        </div>
        <div className="flex flex-col gap-1 flex-1">
          <label className="text-xs font-medium text-neutral-500">Nom</label>
          <input
            type="text" value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="ex: Debian 12"
            className="text-sm border border-neutral-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-blue-400"
            required
          />
        </div>
        <button
          type="submit" disabled={submitting}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-neutral-900 hover:bg-neutral-700 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer"
        >
          <Plus size={14} /> Ajouter
        </button>
      </form>

      {error && (
        <p className="text-xs text-red-500 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</p>
      )}

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-auto rounded-sm border border-neutral-200 shadow-sm">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10 border-b border-neutral-200 bg-neutral-50">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider w-28 border-r border-neutral-200">ID</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider border-r border-neutral-200">Nom</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-neutral-500 uppercase tracking-wider w-20"></th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-neutral-100">
            {loading && (
              <tr><td colSpan={3} className="px-4 py-10 text-center text-neutral-400 text-xs"><Loader size={14} className="animate-spin inline mr-2" />Chargement…</td></tr>
            )}
            {!loading && templates.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-10 text-center text-neutral-400 text-xs">Aucun template</td></tr>
            )}
            {templates.map(t => (
              <tr key={t.template_id} className="hover:bg-neutral-50 transition-colors">
                <td className="px-3 py-2 font-mono text-xs text-neutral-500 border-r border-neutral-100">{t.template_id}</td>
                <td className="px-3 py-2 text-neutral-700 border-r border-neutral-100">{t.name}</td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => handleDelete(t.template_id)}
                    className="text-neutral-300 hover:text-red-500 transition-colors cursor-pointer"
                    title="Supprimer"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
