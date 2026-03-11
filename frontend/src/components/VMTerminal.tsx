import { useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

const API_BASE = import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000`

const enc = new TextEncoder()
const dec = new TextDecoder()

function encodeMuxFrame(channel: number, payload: Uint8Array): Uint8Array {
  const header = enc.encode(`${channel}:${payload.byteLength}:`)
  const frame = new Uint8Array(header.byteLength + payload.byteLength)
  frame.set(header, 0)
  frame.set(payload, header.byteLength)
  return frame
}

function decodeMuxFrames(buf: Uint8Array): { frames: { channel: number; payload: Uint8Array }[]; rest: Uint8Array } {
  const frames: { channel: number; payload: Uint8Array }[] = []
  let offset = 0
  while (offset < buf.length) {
    let c1 = -1
    for (let i = offset; i < buf.length; i++) { if (buf[i] === 58) { c1 = i; break; } }
    if (c1 === -1) break
    let c2 = -1
    for (let i = c1 + 1; i < buf.length; i++) { if (buf[i] === 58) { c2 = i; break; } }
    if (c2 === -1) break
    const channel = parseInt(dec.decode(buf.slice(offset, c1)), 10)
    const len = parseInt(dec.decode(buf.slice(c1 + 1, c2)), 10)
    if (isNaN(channel) || isNaN(len)) break
    const payloadStart = c2 + 1
    const payloadEnd = payloadStart + len
    if (payloadEnd > buf.length) break
    frames.push({ channel, payload: buf.slice(payloadStart, payloadEnd) })
    offset = payloadEnd
  }
  return { frames, rest: buf.slice(offset) }
}

export interface VMTerminalHandle {
  sendRaw: (data: string) => void
}

interface Props {
  vmId: string
  mobileKeyboard?: boolean
}

const VMTerminal = forwardRef<VMTerminalHandle, Props>(function VMTerminal({ vmId, mobileKeyboard }, ref) {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const sendRaw = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(encodeMuxFrame(0, enc.encode(data)))
    }
  }, [])

  useImperativeHandle(ref, () => ({ sendRaw }))

  const handleMobileKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const key = e.key
    if (key === 'Enter') { e.preventDefault(); sendRaw('\r'); return }
    if (key === 'Tab') { e.preventDefault(); sendRaw('\t'); return }
    if (key === 'Escape') { e.preventDefault(); sendRaw('\x1b'); return }
    if (key === 'ArrowUp') { e.preventDefault(); sendRaw('\x1b[A'); return }
    if (key === 'ArrowDown') { e.preventDefault(); sendRaw('\x1b[B'); return }
    if (key === 'ArrowRight') { e.preventDefault(); sendRaw('\x1b[C'); return }
    if (key === 'ArrowLeft') { e.preventDefault(); sendRaw('\x1b[D'); return }
    if (e.ctrlKey && key.length === 1) { e.preventDefault(); sendRaw(String.fromCharCode(key.toUpperCase().charCodeAt(0) - 64)); return }
  }, [sendRaw])

  const SENTINEL = '\u200B' // zero-width space

  const handleMobileInput = useCallback((e: React.FormEvent<HTMLTextAreaElement>) => {
    const nativeEvent = e.nativeEvent as InputEvent
    const textarea = e.target as HTMLTextAreaElement
    if (nativeEvent.inputType === 'deleteContentBackward') {
      sendRaw('\x7f')
      textarea.value = SENTINEL
      return
    }
    const value = textarea.value.replace(SENTINEL, '')
    if (value) {
      sendRaw(value)
    }
    textarea.value = SENTINEL
  }, [sendRaw])

  useEffect(() => {
    if (!containerRef.current) return

    const term = new Terminal({
      theme: {
        background: '#000000',
        foreground: '#e2e8f0',
        cursor: '#7dd3fc',
        selectionBackground: '#334155',
        black: '#1e293b',
        red: '#f87171',
        green: '#4ade80',
        yellow: '#facc15',
        blue: '#60a5fa',
        magenta: '#c084fc',
        cyan: '#22d3ee',
        white: '#e2e8f0',
        brightBlack: '#475569',
        brightRed: '#fca5a5',
        brightGreen: '#86efac',
        brightYellow: '#fde047',
        brightBlue: '#93c5fd',
        brightMagenta: '#d8b4fe',
        brightCyan: '#67e8f9',
        brightWhite: '#f8fafc',
      },
    })
    termRef.current = term
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(containerRef.current)
    fit.fit()

    const wsBase = API_BASE.replace(/^http/, 'ws')
    const ws = new WebSocket(`${wsBase}/api/vms/${vmId}/terminal`, ['binary'])
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    let rxBuffer = new Uint8Array(0)

    function sendResize() {
      fit.fit()
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(encodeMuxFrame(1, enc.encode(`${term.cols}:${term.rows}`)))
      }
    }

    ws.onopen = () => {
      fit.fit()
      sendResize()
      setTimeout(() => {
        term.clear()
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(encodeMuxFrame(0, enc.encode('\n')))
        }
      }, 800)
    }

    ws.onmessage = (e) => {
      const bytes = e.data instanceof ArrayBuffer ? new Uint8Array(e.data) : enc.encode(e.data as string)
      const merged = new Uint8Array(rxBuffer.byteLength + bytes.byteLength)
      merged.set(rxBuffer, 0)
      merged.set(bytes, rxBuffer.byteLength)
      rxBuffer = merged

      const { frames, rest } = decodeMuxFrames(rxBuffer)
      rxBuffer = rest

      if (frames.length > 0) {
        for (const frame of frames) {
          if (frame.channel === 0) term.write(frame.payload)
        }
      } else {
        term.write(new Uint8Array(rxBuffer))
        rxBuffer = new Uint8Array(0)
      }
    }

    ws.onclose = (e) => {
      term.writeln(`\r\n\x1b[33mConnexion fermée (code ${e.code}${e.reason ? ' — ' + e.reason : ''}).\x1b[0m`)
    }

    ws.onerror = () => {
      term.writeln('\r\n\x1b[31mErreur WebSocket.\x1b[0m')
    }

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(encodeMuxFrame(0, enc.encode(data)))
      }
    })

    const observer = new ResizeObserver(() => sendResize())
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      ws.close()
      term.dispose()
      termRef.current = null
      wsRef.current = null
    }
  }, [vmId])

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full rounded-sm overflow-hidden" />
      {mobileKeyboard && (
        <textarea
          autoFocus
          defaultValue={'\u200B'}
          onKeyDown={handleMobileKeyDown}
          onInput={handleMobileInput}
          className="absolute inset-0 opacity-0 w-full h-full cursor-default"
          style={{ caretColor: 'transparent', resize: 'none' }}
          aria-hidden
        />
      )}
    </div>
  )
})

export default VMTerminal
