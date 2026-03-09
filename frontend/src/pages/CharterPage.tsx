import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { API_BASE, apiFetch, logoutUrl } from '../api'

interface Props {
  onSigned: () => void
}

export default function CharterPage({ onSigned }: Props) {
  const [charterText, setCharterText] = useState<string | null>(null)
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false)
  const [checked, setChecked] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/charte`, { credentials: 'include' })
      .then((r) => r.text())
      .then(setCharterText)
      .catch(() => setCharterText(null))
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    function onScroll() {
      if (!el) return
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 8
      if (atBottom) setHasScrolledToBottom(true)
    }

    el.addEventListener('scroll', onScroll)
    // Check immediately in case content is short enough to not need scrolling
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [charterText])

  async function handleSign() {
    if (!checked) return
    setLoading(true)
    setError(null)
    try {
      await apiFetch('/api/charter/sign', { method: 'POST' })
      // Token already refreshed server-side — just reload user state
      onSigned()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Une erreur est survenue.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-3xl bg-white border border-neutral-200 rounded-xl shadow-md flex flex-col overflow-hidden" style={{ maxHeight: '90vh' }}>
        {/* Header */}
        <div className="px-8 py-5 border-b border-neutral-200 flex items-center gap-4 shrink-0">
          <img src="/assets/logo/text_hosting_dark.png" alt="Hosting" className="h-7" />
          <div>
            <h1 className="text-lg font-semibold text-neutral-900">Charte d'utilisation</h1>
            <p className="text-xs text-neutral-500">Vous devez accepter la charte pour accéder à la plateforme Hosting MiNET.</p>
          </div>
        </div>

        {/* Charter content */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-8 py-6 text-sm text-neutral-700 leading-relaxed"
          style={{ minHeight: 0 }}
        >
          {charterText === null ? (
            <p className="text-neutral-400 italic">Chargement de la charte…</p>
          ) : (
            <ReactMarkdown
              components={{
                h1: ({ children }) => <h1 className="text-xl font-bold text-neutral-900 mt-6 mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-semibold text-neutral-800 mt-5 mb-1.5 border-b border-neutral-100 pb-1">{children}</h2>,
                p: ({ children }) => <p className="mb-3 text-neutral-700 leading-relaxed">{children}</p>,
                ul: ({ children }) => <ul className="mb-3 pl-5 space-y-1 list-disc text-neutral-700">{children}</ul>,
                li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{children}</a>,
              }}
            >
              {charterText}
            </ReactMarkdown>
          )}
        </div>

        {/* Scroll hint */}
        {!hasScrolledToBottom && charterText !== null && (
          <div className="text-center text-xs text-neutral-400 py-2 border-t border-neutral-100 bg-white shrink-0">
            Faites défiler jusqu'en bas pour pouvoir accepter la charte
          </div>
        )}

        {/* Footer actions */}
        <div className="px-8 py-5 border-t border-neutral-200 bg-neutral-50 shrink-0 flex flex-col gap-4">
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</p>
          )}
          <label className={`flex items-start gap-3 select-none ${hasScrolledToBottom ? 'cursor-pointer' : 'cursor-not-allowed opacity-40'}`}>
            <input
              type="checkbox"
              className="mt-0.5 w-4 h-4 accent-neutral-900 shrink-0"
              checked={checked}
              disabled={!hasScrolledToBottom}
              onChange={(e) => setChecked(e.target.checked)}
            />
            <span className="text-sm text-neutral-700">
              J'ai lu et j'accepte la charte d'utilisation de la plateforme Hosting MiNET dans son intégralité.
              Un exemplaire signé me sera envoyé par email.
            </span>
          </label>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSign}
              disabled={!checked || !hasScrolledToBottom || loading}
              className="px-5 py-2 bg-neutral-900 text-white text-sm font-medium rounded-md hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? 'Enregistrement…' : 'Signer et continuer'}
            </button>
            <a
              href={logoutUrl()}
              className="text-sm text-neutral-500 hover:text-neutral-800 transition-colors"
            >
              Se déconnecter
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
