import { type ReactNode } from 'react'

interface Props {
  tip?: string
  align?: 'center' | 'right'
  className?: string
  children: ReactNode
}

export default function Tooltip({ tip, align = 'center', className, children }: Props) {
  const pos = align === 'right' ? 'right-0' : 'left-1/2 -translate-x-1/2'
  return (
    <span className={`relative group${className ? ` ${className}` : ''}`}>
      {children}
      {tip && (
        <span className={`pointer-events-none absolute bottom-full ${pos} mb-1.5 px-2 py-1 rounded bg-neutral-800 text-white text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-10`}>
          {tip}
        </span>
      )}
    </span>
  )
}
