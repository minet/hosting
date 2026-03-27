import { X, Cpu, MemoryStick, HardDrive } from 'lucide-react'

interface Props {
  newCpu: number
  setNewCpu: (v: number) => void
  newRam: number
  setNewRam: (v: number) => void
  newDisk: number
  setNewDisk: (v: number) => void
  resSaving: boolean
  maxCpu: number
  maxRam: number
  maxDisk: number
  minCpu: number
  minRam: number
  minDisk: number
  onClose: () => void
  onSave: () => void
}

export default function ResourcesModal({ newCpu, setNewCpu, newRam, setNewRam, newDisk, setNewDisk, resSaving, maxCpu, maxRam, maxDisk, minCpu, minRam, minDisk, onClose, onSave }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white dark:bg-neutral-900 rounded-xl shadow-2xl p-6 flex flex-col gap-5 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-neutral-800 dark:text-neutral-200">Modifier les ressources</p>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 cursor-pointer"><X size={16} /></button>
        </div>

        {/* CPU */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600 dark:text-neutral-400"><Cpu size={13} className="text-violet-500" />CPU</span>
            <span className="text-sm font-bold text-neutral-800 dark:text-neutral-200">{newCpu} <span className="text-xs font-normal text-neutral-400 dark:text-neutral-500">cœur{newCpu > 1 ? 's' : ''}</span></span>
          </div>
          <input type="range" min={minCpu} max={maxCpu} value={newCpu} onChange={e => setNewCpu(Number(e.target.value))}
            className="w-full accent-violet-500 cursor-pointer" />
          <div className="flex justify-between text-[10px] text-neutral-400 dark:text-neutral-500">
            <span>{minCpu} cœur{minCpu > 1 ? 's' : ''}</span><span>{maxCpu} cœur{maxCpu > 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* RAM */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600 dark:text-neutral-400"><MemoryStick size={13} className="text-blue-500" />RAM</span>
            <span className="text-sm font-bold text-neutral-800 dark:text-neutral-200">{newRam} <span className="text-xs font-normal text-neutral-400 dark:text-neutral-500">Go</span></span>
          </div>
          <input type="range" min={minRam} max={maxRam} value={newRam} onChange={e => setNewRam(Number(e.target.value))}
            className="w-full accent-blue-500 cursor-pointer" />
          <div className="flex justify-between text-[10px] text-neutral-400 dark:text-neutral-500">
            <span>{minRam} Go</span><span>{maxRam} Go</span>
          </div>
        </div>

        {/* Disque */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600 dark:text-neutral-400"><HardDrive size={13} className="text-emerald-500" />Disque</span>
            <span className="text-sm font-bold text-neutral-800 dark:text-neutral-200">{newDisk} <span className="text-xs font-normal text-neutral-400 dark:text-neutral-500">Go</span></span>
          </div>
          <input type="range" min={minDisk} max={maxDisk} value={newDisk} onChange={e => setNewDisk(Number(e.target.value))}
            className="w-full accent-emerald-500 cursor-pointer" />
          <div className="flex justify-between text-[10px] text-neutral-400 dark:text-neutral-500">
            <span>{minDisk} Go</span><span>{maxDisk} Go</span>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm font-semibold text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer">
            Annuler
          </button>
          <button onClick={onSave} disabled={resSaving}
            className="flex-1 py-2 rounded-lg bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer">
            {resSaving ? '…' : 'Appliquer'}
          </button>
        </div>
      </div>
    </div>
  )
}
