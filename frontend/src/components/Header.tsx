import { LogOut, Menu, Star } from 'lucide-react'
import { logoutUrl } from '../api'

interface Props {
  onBurgerClick: () => void
  dark?: boolean
}

export default function Header({ onBurgerClick, dark }: Props) {
  return (
    <header className={`flex items-center justify-between px-6 py-3 border-b shrink-0 relative z-40 ${dark ? 'bg-neutral-800 border-neutral-700 shadow-none' : 'bg-white border-neutral-200 shadow-md'}`}>
      <div className="flex items-center gap-3">
        <button onClick={onBurgerClick} className="md:hidden text-neutral-500 hover:text-neutral-900 transition-colors">
          <Menu size={20} />
        </button>
        <img src="/assets/logo/text_hosting_dark.png" alt="Hosting" className="h-8" />
        <span className="text-xs text-neutral-400 font-medium">v3.0</span>
      </div>
      <div className="flex items-center gap-3">
        <a
          href="https://github.com/andinox/hosting"
          target="_blank"
          rel="noreferrer"
          className={`hidden md:flex items-center gap-1.5 text-xs px-3 py-1.5 border rounded-sm transition-colors ${dark ? 'border-neutral-600 text-neutral-400 hover:text-neutral-100 hover:border-neutral-400' : 'border-neutral-200 text-neutral-500 hover:text-neutral-900 hover:border-neutral-400'}`}
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
