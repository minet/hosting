import { useState } from 'react'
import type { ReactNode } from 'react'
import { VMModalContext } from '../contexts/VMModalContext'
import CreateVMModal from './CreateVMModal'
import Header from './Header'
import Sidebar from './Sidebar'

interface Props {
  children: ReactNode
}

export default function Layout({ children }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [vmModalOpen, setVmModalOpen] = useState(false)

  return (
    <VMModalContext.Provider value={() => setVmModalOpen(true)}>
      <div className="flex flex-col h-screen bg-white text-neutral-900 overflow-x-hidden">
        <Header onBurgerClick={() => setMobileOpen((o) => !o)} />
        <div className="flex-1 overflow-hidden relative">
          <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} onCreateVM={() => setVmModalOpen(true)} />
          <main className="h-full overflow-y-auto overflow-x-hidden p-6 md:pl-20">{children}</main>
        </div>
        {vmModalOpen && <CreateVMModal onClose={() => setVmModalOpen(false)} />}
      </div>
    </VMModalContext.Provider>
  )
}
