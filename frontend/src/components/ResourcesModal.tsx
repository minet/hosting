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
  onClose: () => void
  onSave: () => void
}

export default function ResourcesModal({ newCpu, setNewCpu, newRam, setNewRam, newDisk, setNewDisk, resSaving, maxCpu, maxRam, maxDisk, onClose, onSave }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl p-6 flex flex-col gap-5 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-bold text-neutral-800">Modifier les ressources</p>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer"><X size={16} /></button>
        </div>

        {/* CPU */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><Cpu size={13} className="text-violet-500" />CPU</span>
            <span className="text-sm font-bold text-neutral-800">{newCpu} <span className="text-xs font-normal text-neutral-400">cœur{newCpu > 1 ? 's' : ''}</span></span>
          </div>
          <input type="range" min={1} max={maxCpu} value={newCpu} onChange={e => setNewCpu(Number(e.target.value))}
            className="w-full accent-violet-500 cursor-pointer" />
          <div className="flex justify-between text-[10px] text-neutral-400">
            <span>1 cœur</span><span>{maxCpu} cœur{maxCpu > 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* RAM */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><MemoryStick size={13} className="text-blue-500" />RAM</span>
            <span className="text-sm font-bold text-neutral-800">{newRam} <span className="text-xs font-normal text-neutral-400">Go</span></span>
          </div>
          <input type="range" min={1} max={maxRam} value={newRam} onChange={e => setNewRam(Number(e.target.value))}
            className="w-full accent-blue-500 cursor-pointer" />
          <div className="flex justify-between text-[10px] text-neutral-400">
            <span>1 Go</span><span>{maxRam} Go</span>
          </div>
        </div>

        {/* Disque */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600"><HardDrive size={13} className="text-emerald-500" />Disque</span>
            <span className="text-sm font-bold text-neutral-800">{newDisk} <span className="text-xs font-normal text-neutral-400">Go</span></span>
          </div>
          <input type="range" min={10} max={maxDisk} value={newDisk} onChange={e => setNewDisk(Number(e.target.value))}
            className="w-full accent-emerald-500 cursor-pointer" />
          <div className="flex justify-between text-[10px] text-neutral-400">
            <span>10 Go</span><span>{maxDisk} Go</span>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-neutral-200 text-sm font-semibold text-neutral-600 hover:bg-neutral-50 transition-colors cursor-pointer">
            Annuler
          </button>
          <button onClick={onSave} disabled={resSaving}
            className="flex-1 py-2 rounded-lg bg-neutral-900 hover:bg-neutral-700 text-white text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer">
            {resSaving ? '…' : 'Appliquer'}
          </button>
        </div>
      </div>
    </div>
  )
}
