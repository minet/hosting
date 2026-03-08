import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api'
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

const inputClass = "w-full border border-neutral-200 rounded-md px-3 py-2 text-sm text-neutral-800 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 bg-white"
const labelClass = "text-xs font-semibold text-neutral-500 uppercase tracking-wide"


export default function CreateVMModal({ onClose }: Props) {
  const resources = useResources()
  const templates = useTemplates()
  const remaining = resources?.remaining

  const maxCpu = remaining?.cpu_cores ?? 1
  const maxRam = remaining ? Math.floor(remaining.ram_mb / 1024) : 1
  const maxDisk = remaining?.disk_gb ?? 1

  const [name, setName] = useState('')
  const [templateId, setTemplateId] = useState<number | ''>('')

  useEffect(() => {
    if (templates.length > 0 && templateId === '') setTemplateId(templates[0].template_id)
  }, [templates])

  const [cpu, setCpu] = useState(2)
  const [ram, setRam] = useState(2)
  const [disk, setDisk] = useState(10)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sshKey, setSshKey] = useState('')
  const [creating, setCreating] = useState(false)
  const [statusText, setStatusText] = useState('Réservation des ressources...')
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
    if (type === 'qmclone') return 'Clonage du template en cours...'
    if (type === 'qmconfig') return 'Configuration de la VM...'
    if (type === 'qmresize') return 'Redimensionnement du disque...'
    if (type === 'qmigrate') return 'Migration vers le nœud optimal...'
    if (type === 'vzmigrate') return 'Migration en cours...'
    return 'Provisionnement en cours...'
  }

  async function startTaskPolling(vmId: number) {
    async function poll() {
      try {
        const res = await apiFetch<{ items: TaskItem[] }>(`/api/vms/${vmId}/tasks`)
        const recent = res.items.filter(t => (t.starttime ?? 0) >= creationTimeRef.current)
        // Task en cours = endtime null ou 0
        const running = recent.find(t => !t.endtime)
        if (running) {
          setStatusText(taskTypeLabel(running.type))
        }
      } catch (err) {
        if (err instanceof Response && err.status === 401) {
          stopAll()
          setError('Session expirée, veuillez vous reconnecter.')
          setCreating(false)
        }
      }
    }
    poll()
    taskPollRef.current = setInterval(poll, 2000)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!templateId) return
    setCreating(true)
    setError(null)
    setDone(false)
    setStatusText('Réservation des ressources...')
    creationTimeRef.current = Math.floor(Date.now() / 1000)

    // Snapshot des VM existantes
    let existingIds: Set<number>
    try {
      const existing = await apiFetch<{ items: { vm_id: number }[] }>('/api/vms')
      existingIds = new Set(existing.items.map(v => v.vm_id))
    } catch {
      existingIds = new Set()
    }

    // Lancer le POST sans l'attendre
    const postPromise = apiFetch<{ vm_id: number }>('/api/vms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        template_id: templateId,
        cpu_cores: cpu,
        ram_gb: ram,
        disk_gb: disk,
        resource: { username, password: password || null, ssh_public_key: sshKey },
      }),
    })

    // Poller /api/vms pour trouver le vm_id dès qu'il est en BDD
    let taskPollingStarted = false
    findVmRef.current = setInterval(async () => {
      if (taskPollingStarted) return
      try {
        const vms = await apiFetch<{ items: { vm_id: number }[] }>('/api/vms')
        const newVm = vms.items.find(v => !existingIds.has(v.vm_id))
        if (newVm) {
          taskPollingStarted = true
          clearInterval(findVmRef.current!)
          setStatusText('Clonage du template en cours...')
          startTaskPolling(newVm.vm_id)
        }
      } catch { /* retry */ }
    }, 1500)

    // Attendre la fin du POST
    try {
      await postPromise
      stopAll()
      setStatusText('VM créée avec succès !')
      setDone(true)
      setTimeout(onClose, 1500)
    } catch (err) {
      stopAll()
      if (err instanceof Response && err.status === 401) {
        setError('Session expirée, veuillez vous reconnecter.')
      } else {
        setError('Une erreur est survenue lors de la création de la VM.')
      }
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={creating ? undefined : onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-neutral-100">
          <div className="flex items-center gap-3">
            <img src="/assets/pinguins/PenguinHeureux.svg" alt="Penguin" className="h-10 w-auto" />
            <div>
              <h2 className="text-lg font-bold text-neutral-800 select-none">Créer une VM</h2>
              <p className="text-xs text-neutral-400 select-none">Configurez votre nouvelle machine virtuelle</p>
            </div>
          </div>
          {!creating && (
            <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer">
              <X size={20} />
            </button>
          )}
        </div>

        {/* Pas de ressources */}
        {!creating && resources && ((remaining?.cpu_cores ?? 1) <= 0 || (remaining?.ram_mb ?? 1) <= 0 || (remaining?.disk_gb ?? 1) <= 0) ? (
          <div className="flex flex-col items-center justify-center gap-4 py-12 px-6 text-center">
            <img src="/assets/pinguins/PinguinTriste.svg" alt="Triste" className="h-24 w-auto" />
            <div>
              <p className="text-base font-bold text-neutral-800">Quota épuisé</p>
              <p className="text-sm text-neutral-500 mt-1">Vous avez utilisé toutes vos ressources allouées. Supprimez une VM pour en créer une nouvelle.</p>
            </div>
            <button onClick={onClose} className="mt-2 px-5 py-2 text-sm font-semibold bg-neutral-100 hover:bg-neutral-200 text-neutral-700 rounded-md transition-colors cursor-pointer">
              Fermer
            </button>
          </div>
        ) : null}

        {/* Loading state */}
        {creating ? (
          <div className="flex flex-col items-center justify-center gap-5 py-16 px-6">
            <img
              src="/assets/pinguins/PinguinPerdu.svg"
              alt="Chargement"
              className={`h-24 w-auto ${done ? '' : 'animate-spin'}`}
              style={{ animationDuration: '2s' }}
            />
            <div className="text-center">
              <p className="text-sm font-semibold text-neutral-700">{statusText}</p>
            </div>
            {error && (
              <div className="w-full">
                <p className="text-xs text-red-500 bg-red-50 px-3 py-2 rounded-md text-center">{error}</p>
                <button onClick={onClose} className="mt-3 w-full text-sm text-neutral-500 hover:text-neutral-700 cursor-pointer">Fermer</button>
              </div>
            )}
          </div>
        ) : resources && ((remaining?.cpu_cores ?? 1) <= 0 || (remaining?.ram_mb ?? 1) <= 0 || (remaining?.disk_gb ?? 1) <= 0) ? null : (
          <form onSubmit={handleSubmit} className="px-6 py-5 flex flex-col gap-6">

            {/* Machine */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-bold text-neutral-700 border-l-2 border-blue-400 pl-2">{name || 'Nouvelle VM'}</h3>
              <div className="flex flex-col gap-1">
                <label className={labelClass}>Nom</label>
                <input className={inputClass} value={name} onChange={e => setName(e.target.value)} placeholder="ma-vm" required />
              </div>
              <div className="flex flex-col gap-1">
                <label className={labelClass}>Template</label>
                <select className={inputClass} value={templateId} onChange={e => setTemplateId(Number(e.target.value))} required>
                  <option value="">Sélectionner un template</option>
                  {templates.map(t => (
                    <option key={t.template_id} value={t.template_id}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>CPU <span className="block sm:inline normal-case font-normal text-neutral-400">(max {maxCpu})</span></label>
                  <input className={inputClass} type="number" min={2} max={maxCpu} value={cpu} onChange={e => setCpu(Number(e.target.value))} required />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>RAM Go <span className="block sm:inline normal-case font-normal text-neutral-400">(max {maxRam})</span></label>
                  <input className={inputClass} type="number" min={2} max={maxRam} value={ram} onChange={e => setRam(Number(e.target.value))} required />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>Disque Go <span className="block sm:inline normal-case font-normal text-neutral-400">(max {maxDisk})</span></label>
                  <input className={inputClass} type="number" min={1} max={maxDisk} value={disk} onChange={e => setDisk(Number(e.target.value))} required />
                </div>
              </div>
            </section>

            {/* Accès */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-bold text-neutral-700 border-l-2 border-blue-400 pl-2">Accès SSH</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>Nom d'utilisateur</label>
                  <input className={inputClass} value={username} onChange={e => setUsername(e.target.value)} placeholder="monuser" required />
                </div>
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>Mot de passe</label>
                  <input className={inputClass} type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" autoComplete="new-password" />
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <label className={labelClass}>Clé SSH publique</label>
                <textarea className={`${inputClass} font-mono text-xs resize-none`} rows={3} value={sshKey} onChange={e => setSshKey(e.target.value)} placeholder="ssh-ed25519 AAAA..." required />
              </div>
            </section>

            {error && <p className="text-xs text-red-500 bg-red-50 px-3 py-2 rounded-md">{error}</p>}

            {/* Actions */}
            <div className="flex gap-3 justify-end pt-1">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-neutral-600 hover:text-neutral-800 transition-colors cursor-pointer">
                Annuler
              </button>
              <button type="submit" className="px-5 py-2 text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors cursor-pointer">
                Créer la VM
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
