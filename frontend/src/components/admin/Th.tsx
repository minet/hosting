import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import ColFilter from './ColFilter'
import type { ColFilterProps } from './ColFilter'

export type SortKey = 'vm_id' | 'name' | 'template_name' | 'cpu_cores' | 'ipv4' | 'ipv6' | 'mac' | 'dns' | 'owner_id' | 'status' | 'node' | 'cotise'
export type SortDir = 'asc' | 'desc'

export const COLS = ['vm_id', 'status', 'name', 'template_name', 'cpu_cores', 'node', 'ipv4', 'ipv6', 'mac', 'dns', 'owner_id', 'cotise'] as const
export type ColId = typeof COLS[number]

export const DEFAULT_WIDTHS: Record<ColId, number> = {
  vm_id: 60, status: 120, name: 150, template_name: 130,
  cpu_cores: 220, node: 120, ipv4: 120, ipv6: 260, mac: 140, dns: 200, owner_id: 340, cotise: 90,
}

export interface ThProps {
  col: ColId; label: string; width: number
  sortKey: SortKey; sortDir: SortDir; onSort: (col: SortKey) => void
  onResize?: (col: ColId, width: number) => void
  filter?: ColFilterProps
}

export default function Th({ col, label, width, sortKey, sortDir, onSort, onResize, filter }: ThProps) {
  const sorted = (col as string) === sortKey

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!onResize) return
    e.preventDefault()
    e.stopPropagation()
    const target = e.currentTarget
    target.setPointerCapture(e.pointerId)
    const startX = e.clientX
    const startWidth = width

    const onPointerMove = (ev: PointerEvent) => {
      const delta = ev.clientX - startX
      onResize(col, Math.max(60, startWidth + delta))
    }

    const onPointerUp = (ev: PointerEvent) => {
      try {
        target.releasePointerCapture(ev.pointerId)
      } catch {}
      target.removeEventListener('pointermove', onPointerMove)
      target.removeEventListener('pointerup', onPointerUp)
      target.removeEventListener('pointercancel', onPointerUp)
    }

    target.addEventListener('pointermove', onPointerMove)
    target.addEventListener('pointerup', onPointerUp)
    target.addEventListener('pointercancel', onPointerUp)
  }

  return (
    <th
      className="group relative px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider whitespace-nowrap bg-neutral-50 dark:bg-neutral-800 border-r border-neutral-200 dark:border-neutral-700 last:border-r-0 select-none overflow-hidden"
      style={{ width, minWidth: width }}
    >
      <div className="flex items-center gap-1.5 overflow-hidden">
        <button className="flex items-center gap-1 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors overflow-hidden" onClick={() => onSort(col as SortKey)}>
          <span className="truncate">{label}</span>
          {sorted
            ? sortDir === 'asc' ? <ChevronUp size={11} className="text-blue-500 shrink-0" /> : <ChevronDown size={11} className="text-blue-500 shrink-0" />
            : <ChevronsUpDown size={11} className="text-neutral-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
          }
        </button>
        {filter && <ColFilter {...filter} />}
      </div>
      {/* Resize handle */}
      {onResize && (
        <div
          className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-blue-400 transition-colors opacity-0 group-hover:opacity-100 touch-none select-none"
          onPointerDown={handlePointerDown}
        />
      )}
    </th>
  )
}
