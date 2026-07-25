import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, Loader, Plus, Search, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { apiFetch, ApiError } from '../../api'
import { useTemplates } from '../../hooks/useTemplates'
import type { GroupMember } from '../../hooks/useAdminGroupMembers'

interface Props {
  onClose: () => void
  onCreated: () => void
  users: GroupMember[]
  usersLoading: boolean
}

interface UserIdentity {
  id: string
  username: string | null
  first_name: string | null
  last_name: string | null
  email: string | null
}

const VM_NAME_MAX_LENGTH = 60
const inputClass = 'w-full border border-neutral-200 dark:border-neutral-600 rounded-md px-3 py-2 text-sm text-neutral-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 bg-white dark:bg-neutral-800'
const labelClass = 'text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wide'

type SelectedUser = UserIdentity & { source: 'loaded' | 'verified' }

function displayName(user: Pick<UserIdentity, 'username' | 'first_name' | 'last_name'> & { id: string | null }): string {
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username || user.id || ''
}

function uniqueUsers(users: GroupMember[]): GroupMember[] {
  const map = new Map<string, GroupMember>()
  for (const user of users) {
    if (!user.id || map.has(user.id)) continue
    map.set(user.id, user)
  }
  return [...map.values()]
}

export default function CreateVMForUserModal({ onClose, onCreated, users, usersLoading }: Props) {
  const { t } = useTranslation('admin')
  const tc = useTranslation().t
  const templates = useTemplates()
  const localUsers = useMemo(() => uniqueUsers(users), [users])

  const [search, setSearch] = useState('')
  const [selectedUser, setSelectedUser] = useState<SelectedUser | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [templateId, setTemplateId] = useState<number | ''>('')
  const [cpu, setCpu] = useState<number | ''>(2)
  const [ram, setRam] = useState<number | ''>(2)
  const [disk, setDisk] = useState<number | ''>(10)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sshKey, setSshKey] = useState('')

  const [creating, setCreating] = useState(false)
  const [successVmId, setSuccessVmId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    }
  }, [])

  useEffect(() => {
    if (templates.length > 0 && templateId === '') setTemplateId(templates[0].template_id)
  }, [templates, templateId])

  const selectedTemplate = templates.find(template => template.template_id === templateId)
  const minCpu = selectedTemplate?.min_cpu_cores ?? 1
  const minRam = selectedTemplate?.min_ram_gb ?? 1
  const minDisk = selectedTemplate?.min_disk_gb ?? 10

  useEffect(() => {
    setCpu(prev => prev === '' ? minCpu : Math.max(prev, minCpu))
    setRam(prev => prev === '' ? minRam : Math.max(prev, minRam))
    setDisk(prev => prev === '' ? minDisk : Math.max(prev, minDisk))
  }, [minCpu, minRam, minDisk, templateId])

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return localUsers.slice(0, 8)
    return localUsers.filter(user => {
      const name = displayName(user).toLowerCase()
      return user.id?.toLowerCase().includes(q) || name.includes(q) || (user.email ?? '').toLowerCase().includes(q) || (user.username ?? '').toLowerCase().includes(q)
    }).slice(0, 8)
  }, [localUsers, search])

  function selectLoadedUser(user: GroupMember) {
    if (!user.id) return
    setSelectedUser({
      id: user.id,
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      source: 'loaded',
    })
    setSearch(user.id)
    setVerifyError(null)
  }

  function handleSearchChange(value: string) {
    setSearch(value)
    if (selectedUser && value.trim() !== selectedUser.id && value.trim() !== displayName(selectedUser)) {
      setSelectedUser(null)
    }
    setVerifyError(null)
  }

  async function verifyManualUser() {
    const userId = search.trim()
    if (!userId) {
      setVerifyError(t('createVm.userIdRequired'))
      return
    }

    const loadedMatch = localUsers.find(user => user.id === userId)
    if (loadedMatch) {
      selectLoadedUser(loadedMatch)
      return
    }

    setVerifying(true)
    setVerifyError(null)
    try {
      const data = await apiFetch<UserIdentity>(`/api/users/${encodeURIComponent(userId)}/identity`)
      setSelectedUser({ ...data, source: 'verified' })
      setSearch(userId)
    } catch (err) {
      setSelectedUser(null)
      setVerifyError(err instanceof ApiError ? err.message : t('createVm.verifyFailed'))
    } finally {
      setVerifying(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedUser || templateId === '' || cpu === '' || ram === '' || disk === '') return
    if (!name.trim() || !username.trim() || !sshKey.trim()) return

    setCreating(true)
    setError(null)
    setSuccessVmId(null)

    try {
      const result = await apiFetch<{ vm_id: number }>(`/api/users/${encodeURIComponent(selectedUser.id)}/vms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          template_id: templateId,
          cpu_cores: cpu as number,
          ram_gb: ram as number,
          disk_gb: disk as number,
          resource: {
            username,
            password: password || null,
            ssh_public_key: sshKey,
          },
        }),
      })
      setSuccessVmId(result.vm_id)
      onCreated()
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
      closeTimerRef.current = setTimeout(onClose, 2200)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('createVm.createFailed'))
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={creating ? undefined : onClose} />
      <div className="relative w-full max-w-4xl max-h-[92vh] overflow-y-auto rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl">
        <div className="flex items-center justify-between gap-4 px-6 pt-6 pb-4 border-b border-neutral-100 dark:border-neutral-800">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-neutral-800 dark:text-neutral-200 truncate">{t('createVm.title')}</h2>
            <p className="mt-1 text-xs text-neutral-400 dark:text-neutral-500">{t('createVm.subtitle')}</p>
          </div>
          {!creating && (
            <button onClick={onClose} className="shrink-0 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors cursor-pointer">
              <X size={20} />
            </button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5">
          <div className="flex flex-col gap-5">
            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-bold text-neutral-700 dark:text-neutral-300 border-l-2 border-blue-400 pl-2">{t('createVm.userSection')}</h3>

              <div className="flex flex-col gap-2">
                <label className={labelClass}>{t('createVm.loadedUsersLabel')}</label>
                <div className="flex gap-2">
                  <div className="relative flex-1 min-w-0">
                    <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
                    <input
                      value={search}
                      onChange={e => handleSearchChange(e.target.value)}
                      placeholder={t('createVm.loadedUsersPlaceholder')}
                      className={`${inputClass} pl-8 pr-8`}
                      disabled={creating}
                    />
                    {search && (
                      <button type="button" onClick={() => handleSearchChange('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 cursor-pointer">
                        <X size={11} />
                      </button>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={verifyManualUser}
                    disabled={creating || verifying || !search.trim()}
                    className="shrink-0 inline-flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-white"
                  >
                    {verifying ? <Loader size={14} className="animate-spin" /> : <Check size={14} />}
                    {t('createVm.verifyButton')}
                  </button>
                </div>
                <p className="text-xs text-neutral-400 dark:text-neutral-500">{t('createVm.manualUserHint')}</p>
                {(verifyError && !selectedUser) && <p className="text-xs text-red-500">{verifyError}</p>}
              </div>

              <div className="max-h-52 overflow-y-auto rounded-md border border-neutral-200 dark:border-neutral-700 divide-y divide-neutral-100 dark:divide-neutral-800">
                {usersLoading ? (
                  <div className="flex items-center justify-center gap-2 py-4 text-xs text-neutral-400">
                    <Loader size={12} className="animate-spin" /> {tc('loading')}
                  </div>
                ) : filteredUsers.length === 0 ? (
                  <p className="px-3 py-3 text-xs text-neutral-400 text-center">{t('createVm.loadedUsersEmpty')}</p>
                ) : (
                  filteredUsers.map(user => {
                    const isSelected = selectedUser?.id === user.id
                    return (
                      <button
                        type="button"
                        key={user.id}
                        onClick={() => selectLoadedUser(user)}
                        className={`w-full px-3 py-2 text-left text-xs transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300' : 'hover:bg-neutral-50 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'}`}
                      >
                        <span className="font-medium">{displayName(user)}</span>
                        <span className="ml-2 text-neutral-400 dark:text-neutral-500">{user.id}</span>
                        {user.email && <span className="ml-2 text-neutral-400 dark:text-neutral-500">{user.email}</span>}
                      </button>
                    )
                  })
                )}
              </div>

              {selectedUser && (
                <div className="rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50/70 dark:bg-blue-950/30 p-3 text-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">{t('createVm.selectedUser')}</p>
                      <p className="mt-1 font-medium text-neutral-800 dark:text-neutral-200 truncate">{displayName(selectedUser)}</p>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">{selectedUser.id}</p>
                      {selectedUser.email && <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">{selectedUser.email}</p>}
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${selectedUser.source === 'loaded' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'}`}>
                      {selectedUser.source === 'loaded' ? t('createVm.loadedBadge') : t('createVm.verifiedBadge')}
                    </span>
                  </div>
                  {selectedUser.source === 'verified' && <p className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">{t('createVm.verifiedHint')}</p>}
                </div>
              )}
            </section>

            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-bold text-neutral-700 dark:text-neutral-300 border-l-2 border-blue-400 pl-2">{t('createVm.paramsSection')}</h3>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-1 md:col-span-2">
                  <label className={labelClass}>{t('createVm.vmName')}</label>
                  <input
                    className={inputClass}
                    value={name}
                    onChange={e => setName(e.target.value.slice(0, VM_NAME_MAX_LENGTH))}
                    placeholder="vm-admin"
                    maxLength={VM_NAME_MAX_LENGTH}
                    required
                    disabled={creating}
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('createVm.template')}</label>
                  <select
                    className={inputClass}
                    value={templateId}
                    onChange={e => setTemplateId(Number(e.target.value))}
                    required
                    disabled={creating}
                  >
                    <option value="">{t('createVm.selectTemplate')}</option>
                    {templates.map(template => <option key={template.template_id} value={template.template_id}>{template.name}</option>)}
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-3 md:col-span-2">
                  <div className="flex flex-col gap-1">
                    <label className={labelClass}>{t('createVm.cpu')}</label>
                    <input className={inputClass} type="number" min={minCpu} value={cpu} onChange={e => setCpu(e.target.value === '' ? '' : Number(e.target.value))} disabled={creating} />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className={labelClass}>{t('createVm.ram')}</label>
                    <input className={inputClass} type="number" min={minRam} value={ram} onChange={e => setRam(e.target.value === '' ? '' : Number(e.target.value))} disabled={creating} />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className={labelClass}>{t('createVm.disk')}</label>
                    <input className={inputClass} type="number" min={minDisk} value={disk} onChange={e => setDisk(e.target.value === '' ? '' : Number(e.target.value))} disabled={creating} />
                  </div>
                </div>
              </div>
            </section>

            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-bold text-neutral-700 dark:text-neutral-300 border-l-2 border-blue-400 pl-2">{t('createVm.credentialsSection')}</h3>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('createVm.vmUsername')}</label>
                  <input className={inputClass} value={username} onChange={e => setUsername(e.target.value)} required disabled={creating} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('createVm.vmPassword')}</label>
                  <input className={inputClass} type="password" value={password} onChange={e => setPassword(e.target.value)} disabled={creating} />
                </div>
                <div className="flex flex-col gap-1 md:col-span-2">
                  <label className={labelClass}>{t('createVm.sshKey')}</label>
                  <textarea className={`${inputClass} min-h-28`} value={sshKey} onChange={e => setSshKey(e.target.value)} required disabled={creating} />
                </div>
              </div>
            </section>

            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-bold text-neutral-700 dark:text-neutral-300 border-l-2 border-blue-400 pl-2">{t('createVm.confirmationSection')}</h3>
              <div className="rounded-lg border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800/40 p-4 text-sm text-neutral-700 dark:text-neutral-300">
                <div className="grid gap-2 md:grid-cols-2">
                  <p><span className="font-semibold">{t('createVm.summaryUser')}:</span> {selectedUser ? `${displayName(selectedUser)} (${selectedUser.id})` : t('createVm.noUserSelected')}</p>
                  <p><span className="font-semibold">{t('createVm.summaryTemplate')}:</span> {selectedTemplate?.name ?? '—'}</p>
                  <p><span className="font-semibold">{t('createVm.summaryResources')}:</span> {cpu || '—'} CPU, {ram || '—'} {tc('gb')}, {disk || '—'} {tc('gb')}</p>
                  <p><span className="font-semibold">{t('createVm.summaryCredentials')}:</span> {username || '—'}</p>
                </div>
              </div>

              {error && <p className="text-xs text-red-500">{error}</p>}
              {successVmId !== null && (
                <div className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/30 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                  {t('createVm.success', { vmId: successVmId })}
                </div>
              )}
            </section>

            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={creating}
                className="rounded-md border border-neutral-200 dark:border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-40 cursor-pointer"
              >
                {tc('cancel')}
              </button>
              <button
                type="submit"
                disabled={creating || !selectedUser || templateId === '' || !name.trim() || !username.trim() || !sshKey.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {creating ? <Loader size={14} className="animate-spin" /> : <Plus size={14} />}
                {creating ? t('createVm.creating') : t('createVm.createButton')}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}