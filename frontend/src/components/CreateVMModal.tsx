import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, ApiError } from '../api'
import { useResources } from '../hooks/useResources'
import { useTemplates } from '../hooks/useTemplates'

interface Props {
  onClose: () => void
}

interface TaskItem {
  status: string | null
  exitstatus: string | null
  type: string | null
  starttime: number | null
  endtime: number | null
}

const VM_NAME_MAX_LENGTH = 60

const inputClass = "w-full border border-neutral-200 dark:border-neutral-600 rounded-md px-3 py-2 text-sm text-neutral-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 bg-white dark:bg-neutral-800"
const labelClass = "text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wide"


export default function CreateVMModal({ onClose }: Props) {
  const resources = useResources()
  const templates = useTemplates()
  const remaining = resources?.remaining
  const { t } = useTranslation('vm')
  const tc = useTranslation().t

  const maxCpu = remaining?.cpu_cores ?? 1
  const maxRam = remaining ? Math.floor(remaining.ram_mb / 1024) : 1
  const maxDisk = remaining?.disk_gb ?? 1

  const [name, setName] = useState('')
  const [templateId, setTemplateId] = useState<number | ''>('')

  useEffect(() => {
    if (templates.length > 0 && templateId === '') setTemplateId(templates[0].template_id)
  }, [templates])

  const selectedTemplate = templates.find(t => t.template_id === templateId)
  const minCpu = selectedTemplate?.min_cpu_cores ?? 1
  const minRam = selectedTemplate?.min_ram_gb ?? 1
  const minDisk = selectedTemplate?.min_disk_gb ?? 10

  const [cpu, setCpu] = useState<number | ''>(2)
  const [ram, setRam] = useState<number | ''>(2)
  const [disk, setDisk] = useState<number | ''>(10)

  useEffect(() => {
    setCpu(prev => prev === '' ? minCpu : Math.max(prev, minCpu))
    setRam(prev => prev === '' ? minRam : Math.max(prev, minRam))
    setDisk(prev => prev === '' ? minDisk : Math.max(prev, minDisk))
  }, [minCpu, minRam, minDisk, templateId])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sshKey, setSshKey] = useState('')
  const [creating, setCreating] = useState(false)
  const [statusText, setStatusText] = useState(t('create.steps.reserving'))
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const findVmRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const taskPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const creationTimeRef = useRef<number>(0)

  useEffect(() => {
    return () => {
      if (findVmRef.current) clearInterval(findVmRef.current)
      if (taskPollRef.current) clearInterval(taskPollRef.current)
    }
  }, [])

  function stopAll() {
    if (findVmRef.current) clearInterval(findVmRef.current)
    if (taskPollRef.current) clearInterval(taskPollRef.current)
  }

  function taskTypeLabel(type: string | null): string {
    if (type === 'qmclone') return t('create.steps.cloning')
    if (type === 'qmconfig') return t('create.steps.configuring')
    if (type === 'qmresize') return t('create.steps.resizing')
    if (type === 'qmigrate') return t('create.steps.migrating')
    if (type === 'vzmigrate') return t('create.steps.migratingInProgress')
    return t('create.steps.provisioning')
  }

  async function startTaskPolling(vmId: number) {
    async function poll() {
      try {
        const res = await apiFetch<{ items: TaskItem[] }>(`/api/vms/${vmId}/tasks`)
        const recent = res.items.filter(t => (t.starttime ?? 0) >= creationTimeRef.current)
        const running = recent.find(t => !t.endtime)
        if (running) {
          setStatusText(taskTypeLabel(running.type))
        }
      } catch (err) {
        if (err instanceof Response && err.status === 401) {
          stopAll()
          setError(tc('sessionExpired'))
          setCreating(false)
        }
      }
    }
    poll()
    taskPollRef.current = setInterval(poll, 2000)
  }

  const VM_NAME_RE = /^[a-zA-Z0-9][a-zA-Z0-9-]*$/

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!templateId) return
    if (cpu === '' || ram === '' || disk === '') return
    if (!VM_NAME_RE.test(name) || name.length > VM_NAME_MAX_LENGTH) return
    setCreating(true)
    setError(null)
    setDone(false)
    setStatusText(t('create.steps.reserving'))
    creationTimeRef.current = Math.floor(Date.now() / 1000)

    let existingIds: Set<number>
    try {
      const existing = await apiFetch<{ items: { vm_id: number }[] }>('/api/vms')
      existingIds = new Set(existing.items.map(v => v.vm_id))
    } catch {
      existingIds = new Set()
    }

    const postPromise = apiFetch<{ vm_id: number }>('/api/vms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        template_id: templateId,
        cpu_cores: cpu as number,
        ram_gb: ram as number,
        disk_gb: disk as number,
        resource: { username, password: password || null, ssh_public_key: sshKey },
      }),
    })

    let taskPollingStarted = false
    findVmRef.current = setInterval(async () => {
      if (taskPollingStarted) return
      try {
        const vms = await apiFetch<{ items: { vm_id: number }[] }>('/api/vms')
        const newVm = vms.items.find(v => !existingIds.has(v.vm_id))
        if (newVm) {
          taskPollingStarted = true
          clearInterval(findVmRef.current!)
          setStatusText(t('create.steps.cloning'))
          startTaskPolling(newVm.vm_id)
        }
      } catch { /* retry */ }
    }, 1500)

    try {
      const result = await postPromise as { vm_id: number; network?: { ipv4: string | null } }
      stopAll()
      if (result.network && result.network.ipv4 === null) {
        setStatusText(t('create.steps.successNoIpv4'))
      } else {
        setStatusText(t('create.steps.success'))
      }
      setDone(true)
      setTimeout(onClose, 2500)
    } catch (err) {
      stopAll()
      if (err instanceof ApiError && err.status === 401) {
        setError(tc('sessionExpired'))
      } else {
        setError(err instanceof ApiError ? err.message : t('create.errorCreating'))
      }
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={creating ? undefined : onClose} />
      <div className="relative bg-white dark:bg-neutral-900 rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-neutral-100 dark:border-neutral-800">
          <div className="flex items-center gap-3">
            <img src="/assets/pinguins/PenguinHeureux.svg" alt="Penguin" className="h-10 w-auto" />
            <div>
              <h2 className="text-lg font-bold text-neutral-800 dark:text-neutral-200 select-none">{t('createVM')}</h2>
              <p className="text-xs text-neutral-400 dark:text-neutral-500 select-none">{t('configureNewVM')}</p>
            </div>
          </div>
          {!creating && (
            <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors cursor-pointer">
              <X size={20} />
            </button>
          )}
        </div>

        {/* Pas de ressources */}
        {!creating && resources && ((remaining?.cpu_cores ?? 1) <= 0 || (remaining?.ram_mb ?? 1) <= 0 || (remaining?.disk_gb ?? 1) <= 0) ? (
          <div className="flex flex-col items-center justify-center gap-4 py-12 px-6 text-center">
            <img src="/assets/pinguins/PinguinTriste.svg" alt="Triste" className="h-24 w-auto" />
            <div>
              <p className="text-base font-bold text-neutral-800 dark:text-neutral-200">{t('create.quotaExhausted')}</p>
              <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">{t('create.quotaExhaustedDesc')}</p>
            </div>
            <button onClick={onClose} className="mt-2 px-5 py-2 text-sm font-semibold bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-md transition-colors cursor-pointer">
              {tc('close')}
            </button>
          </div>
        ) : null}

        {/* Loading state */}
        {creating ? (
          <div className="flex flex-col items-center justify-center gap-5 py-16 px-6">
            <img
              src="/assets/pinguins/PinguinPerdu.svg"
              alt="Loading"
              className={`h-24 w-auto ${done ? '' : 'animate-spin'}`}
              style={{ animationDuration: '2s' }}
            />
            <div className="text-center">
              <p className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">{statusText}</p>
            </div>
            {error && (
              <div className="w-full">
                <p className="text-xs text-red-500 bg-red-50 dark:bg-red-950 px-3 py-2 rounded-md text-center">{error}</p>
                <button onClick={onClose} className="mt-3 w-full text-sm text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 cursor-pointer">{tc('close')}</button>
              </div>
            )}
          </div>
        ) : resources && ((remaining?.cpu_cores ?? 1) <= 0 || (remaining?.ram_mb ?? 1) <= 0 || (remaining?.disk_gb ?? 1) <= 0) ? null : (
          <form onSubmit={handleSubmit} className="px-6 py-5 flex flex-col gap-6">

            {/* Machine */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-bold text-neutral-700 dark:text-neutral-300 border-l-2 border-blue-400 pl-2">{name || t('newVM')}</h3>
              <div className="flex flex-col gap-1">
                <label className={labelClass}>{t('create.name')} <span className="normal-case font-normal text-neutral-400 dark:text-neutral-500">({t('create.nameHint', { max: VM_NAME_MAX_LENGTH })})</span></label>
                <input
                  className={inputClass}
                  value={name}
                  onChange={e => setName(e.target.value.slice(0, VM_NAME_MAX_LENGTH))}
                  placeholder="ma-vm"
                  maxLength={VM_NAME_MAX_LENGTH}
                  pattern="^[a-zA-Z0-9][a-zA-Z0-9-]*$"
                  title={t('create.nameValidation')}
                  required
                />
                {name && !/^[a-zA-Z0-9][a-zA-Z0-9-]*$/.test(name) && (
                  <p className="text-xs text-red-500">{t('create.nameError')}</p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <label className={labelClass}>{t('create.template')}</label>
                <select className={inputClass} value={templateId} onChange={e => setTemplateId(Number(e.target.value))} required>
                  <option value="">{t('create.selectTemplate')}</option>
                  {templates.map(tpl => (
                    <option key={tpl.template_id} value={tpl.template_id}>
                      {tpl.name}{tpl.version ? ` (${tpl.version})` : ''}
                    </option>
                  ))}
                </select>
                {selectedTemplate?.comment && (
                  <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-0.5">{selectedTemplate.comment}</p>
                )}
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('create.cpu')} <span className="block sm:inline normal-case font-normal text-neutral-400 dark:text-neutral-500">({t('create.max', { max: maxCpu })})</span></label>
                  <input className={inputClass} type="number" min={minCpu} max={maxCpu} value={cpu} onChange={e => setCpu(e.target.value === '' ? '' : Number(e.target.value))} required />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('create.ramGb')} <span className="block sm:inline normal-case font-normal text-neutral-400 dark:text-neutral-500">({t('create.max', { max: maxRam })})</span></label>
                  <input className={inputClass} type="number" min={minRam} max={maxRam} value={ram} onChange={e => setRam(e.target.value === '' ? '' : Number(e.target.value))} required />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('create.diskGb')} <span className="block sm:inline normal-case font-normal text-neutral-400 dark:text-neutral-500">({t('create.max', { max: maxDisk })})</span></label>
                  <input className={inputClass} type="number" min={minDisk} max={maxDisk} value={disk} onChange={e => setDisk(e.target.value === '' ? '' : Number(e.target.value))} required />
                </div>
              </div>
            </section>

            {/* Accès */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-bold text-neutral-700 dark:text-neutral-300 border-l-2 border-blue-400 pl-2">{t('create.sshAccess')}</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('create.username')}</label>
                  <input className={inputClass} value={username} onChange={e => setUsername(e.target.value)} placeholder="monuser" required />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>{t('create.password')}</label>
                  <input className={inputClass} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" autoComplete="new-password" />
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <label className={labelClass}>
                  {t('create.sshKey')}
                  <a href="https://wiki.minet.net/fr/guides/misc/ssh-key" target="_blank" rel="noopener noreferrer" className="ml-1.5 normal-case font-normal text-blue-500 hover:text-blue-600 hover:underline">
                    {t('create.sshKeyHelp')}
                  </a>
                </label>
                <textarea className={`${inputClass} font-mono text-xs resize-none`} rows={3} value={sshKey} onChange={e => setSshKey(e.target.value)} placeholder="ssh-ed25519 AAAA..." required />
              </div>
            </section>

            {error && <p className="text-xs text-red-500 bg-red-50 dark:bg-red-950 px-3 py-2 rounded-md">{error}</p>}

            {/* Actions */}
            <div className="flex gap-3 justify-end pt-1">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-neutral-600 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors cursor-pointer">
                {tc('cancel')}
              </button>
              <button type="submit" className="px-5 py-2 text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors cursor-pointer">
                {t('create.createButton')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
