import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation('charter')
  const tc = useTranslation().t
  const { t: tAuth } = useTranslation('auth')

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
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [charterText])

  async function handleSign() {
    if (!checked) return
    setLoading(true)
    setError(null)
    try {
      await apiFetch('/api/charter/sign', { method: 'POST' })
      onSigned()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : tc('errorOccurred'))
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-3xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-xl shadow-md flex flex-col overflow-hidden" style={{ maxHeight: '90vh' }}>
        {/* Header */}
        <div className="px-8 py-5 border-b border-neutral-200 dark:border-neutral-700 flex items-center gap-4 shrink-0">
          <img src="/assets/logo/text_hosting_dark.png" alt="Hosting" className="h-7 dark:hidden" />
          <img src="/assets/logo/text_hosting_light.png" alt="Hosting" className="h-7 hidden dark:block" />
          <div>
            <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{t('title')}</h1>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">{t('subtitle')}</p>
          </div>
        </div>

        {/* Charter content */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-8 py-6 text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed"
          style={{ minHeight: 0 }}
        >
          {charterText === null ? (
            <p className="text-neutral-400 dark:text-neutral-500 italic">{t('loadingCharter')}</p>
          ) : (
            <ReactMarkdown
              components={{
                h1: ({ children }) => <h1 className="text-xl font-bold text-neutral-900 dark:text-neutral-100 mt-6 mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-semibold text-neutral-800 dark:text-neutral-200 mt-5 mb-1.5 border-b border-neutral-100 dark:border-neutral-800 pb-1">{children}</h2>,
                p: ({ children }) => <p className="mb-3 text-neutral-700 dark:text-neutral-300 leading-relaxed">{children}</p>,
                ul: ({ children }) => <ul className="mb-3 pl-5 space-y-1 list-disc text-neutral-700 dark:text-neutral-300">{children}</ul>,
                li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">{children}</a>,
              }}
            >
              {charterText}
            </ReactMarkdown>
          )}
        </div>

        {/* Scroll hint */}
        {!hasScrolledToBottom && charterText !== null && (
          <div className="text-center text-xs text-neutral-400 dark:text-neutral-500 py-2 border-t border-neutral-100 dark:border-neutral-800 bg-white dark:bg-neutral-900 shrink-0">
            {t('scrollHint')}
          </div>
        )}

        {/* Footer actions */}
        <div className="px-8 py-5 border-t border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 shrink-0 flex flex-col gap-4">
          {error && (
            <p className="text-sm text-red-600 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-md px-3 py-2">{error}</p>
          )}
          <label className={`flex items-start gap-3 select-none ${hasScrolledToBottom ? 'cursor-pointer' : 'cursor-not-allowed opacity-40'}`}>
            <input
              type="checkbox"
              className="mt-0.5 w-4 h-4 accent-neutral-900 dark:accent-neutral-100 shrink-0"
              checked={checked}
              disabled={!hasScrolledToBottom}
              onChange={(e) => setChecked(e.target.checked)}
            />
            <span className="text-sm text-neutral-700 dark:text-neutral-300">
              {t('accept')}
            </span>
          </label>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSign}
              disabled={!checked || !hasScrolledToBottom || loading}
              className="px-5 py-2 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-sm font-medium rounded-md hover:bg-neutral-700 dark:hover:bg-neutral-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? t('signing') : t('signAndContinue')}
            </button>
            <a
              href={logoutUrl()}
              className="text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors"
            >
              {tAuth('logout')}
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
