import { useState, useRef, useEffect } from 'react'
import { Filter, X } from 'lucide-react'

export interface ColFilterProps {
  active: boolean; type: 'text' | 'select'; value: string
  onChange: (v: string) => void; options?: { label: string; value: string }[]; placeholder?: string
}

export default function ColFilter({ active, type, value, onChange, options, placeholder }: ColFilterProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  return (
    <div ref={ref} className="relative inline-block" onClick={e => e.stopPropagation()}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`p-0.5 rounded transition-colors ${active ? 'text-blue-500 bg-blue-50 dark:bg-blue-950' : 'text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-700'}`}
      >
        <Filter size={10} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded shadow-lg p-2 min-w-[160px]">
          {type === 'select' ? (
            <select autoFocus value={value} onChange={e => { onChange(e.target.value); setOpen(false) }}
              className="w-full text-xs border border-neutral-200 dark:border-neutral-600 rounded px-2 py-1 focus:outline-none focus:border-blue-400 bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100">
              {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : (
            <div className="flex items-center gap-1">
              <input autoFocus type="text" value={value} onChange={e => onChange(e.target.value)}
                placeholder={placeholder ?? 'Filtrer…'}
                className="flex-1 text-xs border border-neutral-200 dark:border-neutral-600 rounded px-2 py-1 focus:outline-none focus:border-blue-400 bg-transparent text-neutral-900 dark:text-neutral-100" />
              {value && (
                <button onClick={() => { onChange(''); setOpen(false) }} className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300">
                  <X size={11} />
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
