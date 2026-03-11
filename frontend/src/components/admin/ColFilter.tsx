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
        className={`p-0.5 rounded transition-colors ${active ? 'text-blue-500 bg-blue-50' : 'text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100'}`}
      >
        <Filter size={10} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-white border border-neutral-200 rounded shadow-lg p-2 min-w-[160px]">
          {type === 'select' ? (
            <select autoFocus value={value} onChange={e => { onChange(e.target.value); setOpen(false) }}
              className="w-full text-xs border border-neutral-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400 bg-white">
              {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : (
            <div className="flex items-center gap-1">
              <input autoFocus type="text" value={value} onChange={e => onChange(e.target.value)}
                placeholder={placeholder ?? 'Filtrer…'}
                className="flex-1 text-xs border border-neutral-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400" />
              {value && (
                <button onClick={() => { onChange(''); setOpen(false) }} className="text-neutral-400 hover:text-neutral-700">
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
