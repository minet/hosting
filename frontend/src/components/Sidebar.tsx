import { Monitor, Plus, Star, Share2 } from 'lucide-react'
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useVMList, useVMStatus } from '../contexts/VMStatusContext'

function VMSidebarItem({ vm, expanded, onMobileClose }: { vm: { vm_id: number; name: string; role: string }; expanded: boolean; onMobileClose: () => void }) {
  const entry = useVMStatus(vm.vm_id)
  const running = entry?.status === 'running'
  const shared = vm.role === 'shared'
  return (
    <Link
      to={`/vm/${vm.vm_id}`}
      onClick={onMobileClose}
      className={`relative flex items-center py-2 rounded-sm text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 overflow-hidden ${expanded ? 'gap-3 px-2 pl-3' : 'justify-center'}`}
    >
      <span className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-full ${running ? 'bg-emerald-500' : 'bg-red-400'}`} />
      <Monitor size={16} className="shrink-0 ml-1" />
      <span className={`text-xs whitespace-nowrap overflow-hidden transition-all duration-200 flex-1 ${expanded ? 'opacity-100 max-w-xs' : 'opacity-0 max-w-0'}`}>
        {vm.name}
      </span>
      {shared && expanded && <Share2 size={11} className="shrink-0 text-blue-400" />}
    </Link>
  )
}

interface Props {
  mobileOpen: boolean
  onMobileClose: () => void
  onCreateVM: () => void
}

export default function Sidebar({ mobileOpen, onMobileClose, onCreateVM }: Props) {
  const [hovered, setHovered] = useState(false)
  const expanded = hovered || mobileOpen
  const vms = useVMList()

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [mobileOpen])

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-20 md:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={`
          fixed top-0 bottom-0 left-0 z-30 bg-white dark:bg-neutral-900 flex flex-col transition-all duration-200 ease-in-out shadow-[4px_0_12px_rgba(0,0,0,0.12)] dark:shadow-[4px_0_12px_rgba(0,0,0,0.4)]
          ${mobileOpen ? 'translate-x-0 w-52' : '-translate-x-full md:translate-x-0'}
          ${hovered ? 'md:w-52' : 'md:w-14'}
        `}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <nav className="flex flex-col gap-1 p-2 pt-16">

          {/* Section VMs */}
          <Link
            to="/"
            className={`flex items-center py-2 rounded-sm text-neutral-500 dark:text-neutral-400 border-b border-neutral-200 dark:border-neutral-700 ${expanded ? 'gap-3 px-2' : 'justify-center'}`}
          >
            <Monitor size={18} className="shrink-0" />
            <span className={`text-sm whitespace-nowrap overflow-hidden transition-all duration-200 ${expanded ? 'opacity-100 max-w-xs' : 'opacity-0 max-w-0'}`}>
              Machines virtuelles
            </span>
          </Link>

          {vms.map(vm => (
            <VMSidebarItem key={vm.vm_id} vm={vm} expanded={expanded} onMobileClose={onMobileClose} />
          ))}

          {/* Séparateur + bouton créer */}
          <div className={vms.length > 0 ? 'border-t border-neutral-200 dark:border-neutral-700 mt-1 pt-1' : ''}>
            <button
              onClick={onCreateVM}
              className={`w-full flex items-center py-2 rounded-sm text-neutral-900 dark:text-neutral-100 ${expanded ? 'gap-3 px-2' : 'justify-center'} cursor-pointer`}
            >
              <Plus size={18} strokeWidth={3} className="shrink-0" />
              <span className={`text-sm font-semibold whitespace-nowrap overflow-hidden transition-all duration-200 ${expanded ? 'opacity-100 max-w-xs' : 'opacity-0 max-w-0'}`}>
                Créer une VM
              </span>
            </button>
          </div>
        </nav>

        <div className="mt-auto p-4 md:hidden">
          <a
            href="https://github.com/andinox/hosting"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-xs px-3 py-2 border border-neutral-200 dark:border-neutral-700 rounded-sm text-neutral-500 dark:text-neutral-400"
          >
            <span className="flex"><Star size={13} className="text-yellow-400 fill-yellow-400" /></span>
            Star on GitHub
          </a>
        </div>
      </aside>
    </>
  )
}
