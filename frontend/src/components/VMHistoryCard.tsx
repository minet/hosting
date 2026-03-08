import { Play, Square, RotateCcw, Trash2, Plus, Settings, type LucideIcon } from 'lucide-react'
import { type VMTask } from '../types/vm'

const TASK_TYPES: Record<string, { label: string; Icon: LucideIcon; color: string }> = {
  qmstart:   { label: 'Start',   Icon: Play,      color: 'text-emerald-500' },
  qmstop:    { label: 'Stop',    Icon: Square,    color: 'text-red-500'     },
  qmreboot:  { label: 'Restart', Icon: RotateCcw, color: 'text-amber-500'   },
  qmdestroy: { label: 'Destroy', Icon: Trash2,    color: 'text-red-500'     },
  qmcreate:  { label: 'Create',  Icon: Plus,      color: 'text-blue-500'    },
  qmpatch:   { label: 'Patch',   Icon: Settings,  color: 'text-violet-500'  },
  qmconfig:  { label: 'Config',  Icon: Settings,  color: 'text-violet-500'  },
}

interface Props {
  tasks: VMTask[]
}

export default function VMHistoryCard({ tasks }: Props) {
  const filtered = tasks.filter(t => t.type !== 'vncproxy')

  return (
    <div className="md:col-span-2 border border-neutral-100 shadow-md rounded-sm bg-white px-5 py-4 flex flex-col h-64 md:h-48 xl:h-auto">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-3">Historique</p>
      {filtered.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-neutral-300 text-xs">Aucune action récente</div>
      ) : (
        <div className="flex flex-col gap-1.5 overflow-y-auto flex-1">
          {filtered.map((t, i) => {
            const ok = t.exitstatus === 'OK'
            const date = t.starttime
              ? new Date(t.starttime * 1000).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
              : '—'
            const meta = t.type ? TASK_TYPES[t.type] : undefined
            const Icon = meta?.Icon
            return (
              <div key={t.upid ?? i} className="flex items-center gap-2 text-xs py-1 border-b border-neutral-50 last:border-0">
                {Icon && <Icon size={11} className="shrink-0 text-neutral-400" fill="currentColor" strokeWidth={0} />}
                <span className="text-neutral-600 flex-1">{meta?.label ?? t.type ?? '—'}</span>
                <span className={`shrink-0 font-medium ${ok ? 'text-emerald-500' : 'text-red-400'}`}>{ok ? 'OK' : t.exitstatus ?? '—'}</span>
                <span className="text-neutral-400 shrink-0">{date}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
