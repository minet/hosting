import { useEffect, useState } from 'react'
import { Loader, Search, X, UserPen } from 'lucide-react'
import { apiFetch } from '../../api'

interface EligibleUser {
  id: string
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
}

interface Props {
  vmId: number
  vmName: string
  currentOwnerId: string | null
  onConfirm: (newOwnerId: string) => Promise<void>
  onClose: () => void
}

export default function ChangeOwnerModal({ vmId, vmName, currentOwnerId, onConfirm, onClose }: Props) {
  const [users, setUsers] = useState<EligibleUser[]>([])
  const [usersLoading, setUsersLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<EligibleUser | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<EligibleUser[]>('/api/admin/users/eligible')
      .then(setUsers)
      .finally(() => setUsersLoading(false))
  }, [])

  const filteredUsers = users.filter(u => {
    if (u.id === currentOwnerId) return false
    if (!search) return true
    const q = search.toLowerCase()
    const name = [u.first_name, u.last_name].filter(Boolean).join(' ').toLowerCase()
    return name.includes(q) || (u.username ?? '').toLowerCase().includes(q) || (u.email ?? '').toLowerCase().includes(q)
  })

  async function handleConfirm() {
    if (!selected) return
    setSaving(true)
    setError(null)
    try {
      await onConfirm(selected.id)
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

        <div>
          <h2 className="text-base font-bold text-neutral-800 dark:text-neutral-200">
            Changer le propriétaire de <span className="text-blue-500">{vmName} <span className="text-sm font-mono text-neutral-400">#{vmId}</span></span>
          </h2>
          <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
            Sélectionner le nouvel utilisateur (charte signée + cotisation active).
          </p>
        </div>

        {/* User search */}
        <div className="flex flex-col gap-2 min-h-0">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher un utilisateur…"
              className="w-full pl-7 pr-7 py-1.5 text-xs border border-neutral-200 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 placeholder-neutral-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 cursor-pointer">
                <X size={11} />
              </button>
            )}
          </div>

          {usersLoading ? (
            <div className="flex items-center gap-2 text-xs text-neutral-400 py-4 justify-center">
              <Loader size={12} className="animate-spin" /> Chargement des utilisateurs…
            </div>
          ) : (
            <div className="overflow-y-auto max-h-52 border border-neutral-200 dark:border-neutral-700 rounded-md divide-y divide-neutral-100 dark:divide-neutral-800">
              {filteredUsers.length === 0 && (
                <p className="text-xs text-neutral-400 py-3 text-center">Aucun utilisateur trouvé</p>
              )}
              {filteredUsers.map(u => {
                const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username || u.id
                const isSelected = selected?.id === u.id
                return (
                  <button
                    key={u.id}
                    onClick={() => setSelected(isSelected ? null : u)}
                    className={`w-full px-3 py-2 text-left text-xs transition-colors cursor-pointer ${isSelected
                      ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300'
                      : 'hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                    }`}
                  >
                    <span className="font-medium">{name}</span>
                    {u.email && <span className="text-neutral-400 dark:text-neutral-500 ml-2">{u.email}</span>}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}

        <div className="flex gap-3">
          <button onClick={onClose} disabled={saving}
            className="flex-1 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer disabled:opacity-40">
            Annuler
          </button>
          <button onClick={handleConfirm} disabled={saving || !selected}
            className="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center gap-2">
            {saving ? <Loader size={14} className="animate-spin" /> : <UserPen size={14} />}
            Changer
          </button>
        </div>
      </div>
    </div>
  )
}
