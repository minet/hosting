import type { ReactNode } from 'react'
import Header from './Header'

interface Props {
  children: ReactNode
}

export default function AdminLayout({ children }: Props) {
  return (
    <div className="flex flex-col h-screen bg-white text-neutral-900">
      <Header />
      <main className="flex-1 overflow-hidden p-4">{children}</main>
    </div>
  )
}
