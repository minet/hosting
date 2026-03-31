import { useState, useRef, useEffect } from 'react'
import { LogOut, Menu, Star, Sun, Moon, ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { logoutUrl } from '../api'
import { useTheme } from '../contexts/ThemeContext'

interface Props {
  onBurgerClick?: () => void
}

const LANGS = [
  { code: 'fr', label: 'FR', flag: '🇫🇷' },
  { code: 'en', label: 'EN', flag: '🇬🇧' },
  { code: 'zh', label: '中文', flag: '🇨🇳' },
]

export default function Header({ onBurgerClick }: Props) {
  const { theme, toggle } = useTheme()
  const { i18n, t } = useTranslation()
  const [langOpen, setLangOpen] = useState(false)
  const langRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node)) setLangOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const currentLang = LANGS.find(l => i18n.language?.startsWith(l.code)) || LANGS[0]

  return (
    <header className="flex items-center justify-between px-6 py-3 border-b shrink-0 relative z-40 bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-700 shadow-md dark:shadow-none">
      <div className="flex items-center gap-3">
        {onBurgerClick && (
          <button onClick={onBurgerClick} className="md:hidden text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors">
            <Menu size={20} />
          </button>
        )}
        <img src="/assets/logo/text_hosting_dark.png" alt="Hosting" className="h-8 dark:hidden" />
        <img src="/assets/logo/text_hosting_light.png" alt="Hosting" className="h-8 hidden dark:block" />
        <span className="text-xs text-neutral-400 font-medium">v3.0</span>
      </div>
      <div className="flex items-center gap-3">
        {/* Language dropdown */}
        <div className="relative" ref={langRef}>
          <button
            onClick={() => setLangOpen(!langOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 border border-neutral-200 dark:border-neutral-700 rounded-md text-[11px] font-semibold text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
          >
            <span>{currentLang.flag}</span>
            <span>{currentLang.label}</span>
            <ChevronDown size={12} className={`transition-transform ${langOpen ? 'rotate-180' : ''}`} />
          </button>
          {langOpen && (
            <div className="absolute right-0 mt-1 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-md shadow-lg overflow-hidden min-w-[100px]">
              {LANGS.map(l => (
                <button
                  key={l.code}
                  onClick={() => { i18n.changeLanguage(l.code); setLangOpen(false) }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold transition-colors cursor-pointer ${
                    i18n.language?.startsWith(l.code)
                      ? 'bg-neutral-100 dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100'
                      : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-700'
                  }`}
                >
                  <span>{l.flag}</span>
                  <span>{l.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={toggle}
          className="flex items-center justify-center w-8 h-8 rounded-md text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
          title={theme === 'dark' ? t('lightMode') : t('darkMode')}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <a
          href="https://github.com/andinox/hosting"
          target="_blank"
          rel="noreferrer"
          className="hidden md:flex items-center gap-1.5 text-xs px-3 py-1.5 border rounded-sm transition-colors border-neutral-200 dark:border-neutral-600 text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:border-neutral-400"
        >
          <span className="flex"><Star size={13} className="text-yellow-400 fill-yellow-400" /></span>
          Star on GitHub
        </a>
        <a href={logoutUrl()} className="text-red-400 hover:text-red-600 transition-colors">
          <LogOut size={20} />
        </a>
      </div>
    </header>
  )
}
