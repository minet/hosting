import { Eye, EyeOff } from 'lucide-react'
import Tooltip from './Tooltip'
import { type VMDetail } from '../types/vm'
import { vmFqdn } from './VMInfoCard'

export interface VMCredentials {
  credUsername: string
  setCredUsername: (v: string) => void
  credPassword: string
  setCredPassword: (v: string) => void
  credSshKey: string
  setCredSshKey: (v: string) => void
  showPassword: boolean
  setShowPassword: (fn: (v: boolean) => boolean) => void
  credSaving: boolean
  credSuccess: boolean
  doSaveCreds: () => void
}

interface Props {
  vm: VMDetail | null
  running: boolean
  isOwner: boolean
  creds: VMCredentials
}

export default function VMAccessCard({ vm, running, isOwner, creds }: Props) {
  const {
    credUsername, setCredUsername,
    credPassword, setCredPassword,
    credSshKey, setCredSshKey,
    showPassword, setShowPassword,
    credSaving, credSuccess, doSaveCreds,
  } = creds

  return (
    <div className="flex flex-col md:col-span-3 xl:col-span-3 border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 px-5 py-4 min-w-0 min-h-0 overflow-visible">
      <div className="flex items-center justify-between mb-2 min-w-0 gap-2 shrink-0">
        <div className="flex items-center gap-3 min-w-0 overflow-hidden">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500 shrink-0">Accès VM</p>
          {vm && isOwner && (
            <p className="text-[10px] text-neutral-500 dark:text-neutral-400 font-mono truncate min-w-0">
              <span className="font-bold">ssh {vm.username ?? 'username'}@{vmFqdn(vm)}</span> marche direct !
            </p>
          )}
        </div>
        <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : running ? "Éteignez la VM d'abord" : undefined} align="right">
          <button
            onClick={doSaveCreds}
            disabled={credSaving || !credUsername.trim() || running || !isOwner}
            className={`px-3 py-1 rounded-md text-xs font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shrink-0
              ${credSuccess ? 'bg-emerald-50 dark:bg-emerald-950 border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300' : 'bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900'}`}
          >
            {credSuccess ? 'Sauvegardé ✓' : credSaving ? '…' : 'Appliquer'}
          </button>
        </Tooltip>
      </div>
      <div className="flex flex-col gap-2 flex-1 min-h-0 min-w-0 overflow-hidden">
        <div className="flex gap-2 min-w-0 shrink-0">
          <div className="flex flex-col gap-1 flex-1 min-w-0">
            <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Utilisateur</label>
            <input
              value={credUsername}
              onChange={e => setCredUsername(e.target.value)}
              placeholder="username"
              disabled={!isOwner}
              className="w-full border border-neutral-200 dark:border-neutral-700 rounded-md px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-300 disabled:opacity-50 disabled:bg-neutral-50 dark:disabled:bg-neutral-800 bg-transparent text-neutral-900 dark:text-neutral-100"
            />
          </div>
          <div className="flex flex-col gap-1 flex-1 min-w-0">
            <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Mot de passe</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={credPassword}
                onChange={e => setCredPassword(e.target.value)}
                placeholder="••••••••"
                disabled={!isOwner}
                className="w-full border border-neutral-200 dark:border-neutral-700 rounded-md px-3 py-1.5 pr-8 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-300 disabled:opacity-50 disabled:bg-neutral-50 dark:disabled:bg-neutral-800 bg-transparent text-neutral-900 dark:text-neutral-100"
              />
              <button type="button" onClick={() => setShowPassword(v => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer">
                {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-1 flex-1 min-h-0 min-w-0 overflow-hidden">
          <label className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500 shrink-0">Clé SSH</label>
          <textarea
            value={credSshKey}
            onChange={e => setCredSshKey(e.target.value)}
            placeholder="ssh-ed25519 AAAA..."
            disabled={!isOwner}
            className="w-full flex-1 min-h-0 border border-neutral-200 dark:border-neutral-700 rounded-md px-3 py-1.5 text-xs font-mono resize-none focus:outline-none focus:ring-1 focus:ring-blue-300 disabled:opacity-50 disabled:bg-neutral-50 dark:disabled:bg-neutral-800 overflow-auto bg-transparent text-neutral-900 dark:text-neutral-100"
          />
        </div>
      </div>
    </div>
  )
}
