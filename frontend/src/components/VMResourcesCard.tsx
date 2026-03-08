import { Cpu, MemoryStick, HardDrive, SlidersHorizontal } from 'lucide-react'
import Tooltip from './Tooltip'
import { type VMDetail } from '../types/vm'

interface Props {
  vm: VMDetail | null
  running: boolean
  isOwner: boolean
  onOpenResModal: () => void
}

export default function VMResourcesCard({ vm, running, isOwner, onOpenResModal }: Props) {
  return (
    <div className="border border-neutral-100 shadow-md rounded-sm bg-white px-5 py-4 flex flex-col justify-between h-32 md:h-48 xl:h-auto">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400">Ressources allouées</p>
        <div className="flex items-center gap-1.5">
          <Tooltip tip={!isOwner ? 'Réservé au propriétaire' : running ? "Éteignez la VM d'abord" : undefined} align="right">
            <button
              onClick={onOpenResModal}
              disabled={!isOwner || running}
              className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-neutral-900 hover:bg-neutral-700 text-white text-[10px] font-semibold transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <SlidersHorizontal size={10} />
              Modifier
            </button>
          </Tooltip>
        </div>
      </div>
      {vm ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs text-neutral-500"><Cpu size={13} className="text-violet-500" />CPU</span>
            <span className="text-sm font-bold text-neutral-800">{vm.cpu_cores} <span className="text-xs font-normal text-neutral-400">cœurs</span></span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs text-neutral-500"><MemoryStick size={13} className="text-blue-500" />RAM</span>
            <span className="text-sm font-bold text-neutral-800">{Math.round(vm.ram_mb / 1024)} <span className="text-xs font-normal text-neutral-400">Go</span></span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs text-neutral-500"><HardDrive size={13} className="text-emerald-500" />Disque</span>
            <span className="text-sm font-bold text-neutral-800">{vm.disk_gb} <span className="text-xs font-normal text-neutral-400">Go</span></span>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-neutral-300 text-xs">—</div>
      )}
    </div>
  )
}
