import { type ReactNode, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  tip?: string
  align?: 'center' | 'right'
  className?: string
  children: ReactNode
}

export default function Tooltip({ tip, align = 'center', className, children }: Props) {
  const ref = useRef<HTMLSpanElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  if (!tip) {
    return <span className={className}>{children}</span>
  }

  function show() {
    if (!ref.current) return
    const r = ref.current.getBoundingClientRect()
    const left = align === 'right' ? r.right : r.left + r.width / 2
    setPos({ top: r.top + window.scrollY, left: left + window.scrollX })
  }

  function hide() {
    setPos(null)
  }

  return (
    <span ref={ref} className={`relative${className ? ` ${className}` : ''}`} onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {pos && createPortal(
        <span
          className={`pointer-events-none fixed z-[9999] px-2 py-1 rounded bg-neutral-800 dark:bg-neutral-200 text-white dark:text-neutral-900 text-[10px] whitespace-nowrap -translate-y-full -translate-x-1/2 mb-1.5`}
          style={{
            top: pos.top - 6,
            left: align === 'right' ? pos.left : pos.left,
            transform: align === 'right'
              ? 'translateY(-100%) translateX(-100%)'
              : 'translateY(-100%) translateX(-50%)',
          }}
        >
          {tip}
        </span>,
        document.body,
      )}
    </span>
  )
}
