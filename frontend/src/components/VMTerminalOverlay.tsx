import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import VMTerminal, { type VMTerminalHandle } from './VMTerminal'

interface Props {
  vmId: string
  vmName: string | undefined
  overlayHeight: number
  onClose: () => void
}

export default function VMTerminalOverlay({ vmId, vmName, overlayHeight, onClose }: Props) {
  const termRef = useRef<VMTerminalHandle>(null)
  const termBarsRef = useRef<HTMLDivElement>(null)
  const [barsHeight, setBarsHeight] = useState(80)

  useEffect(() => {
    const el = termBarsRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setBarsHeight(el.offsetHeight))
    ro.observe(el)
    setBarsHeight(el.offsetHeight)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-black overflow-hidden" style={{ height: overlayHeight }}>
      <div ref={termBarsRef} className="fixed top-0 left-0 right-0 z-[52] flex flex-col">
        <div className="flex items-center justify-between px-4 py-2 bg-neutral-900 border-b border-neutral-700">
          <span className="text-sm font-semibold text-white">{vmName ?? 'Terminal'}</span>
          <button onClick={onClose} className="text-neutral-400 hover:text-white cursor-pointer">
            <X size={20} />
          </button>
        </div>
        <div className="flex gap-1 px-2 py-1.5 bg-neutral-800 border-b border-neutral-700 overflow-x-auto">
          {([
            ['Ctrl+C', '\x03'],
            ['Ctrl+D', '\x04'],
            ['Ctrl+Z', '\x1a'],
            ['Tab', '\t'],
            ['↑', '\x1b[A'],
            ['↓', '\x1b[B'],
          ] as [string, string][]).map(([label, seq]) => (
            <button
              key={label}
              onPointerDown={e => { e.preventDefault(); termRef.current?.sendRaw(seq) }}
              className="shrink-0 px-3 py-1 rounded bg-neutral-700 hover:bg-neutral-600 text-white text-xs font-mono cursor-pointer"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="absolute inset-0 overflow-hidden" style={{ top: barsHeight }}>
        <VMTerminal ref={termRef} vmId={vmId} mobileKeyboard />
      </div>
    </div>
  )
}
