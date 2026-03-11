import { useState } from 'react'
import { Eye, Loader } from 'lucide-react'
import { apiFetch } from '../../api'

interface UserIdentity { username: string | null; first_name: string | null; last_name: string | null; email: string | null }

export default function RevealOwner({ ownerId }: { ownerId: string }) {
  const [identity, setIdentity] = useState<UserIdentity | null>(null)
  const [loading, setLoading] = useState(false)
  const [revealed, setRevealed] = useState(false)

  async function reveal() {
    if (revealed) return
    setLoading(true)
    try {
      const data = await apiFetch<UserIdentity>(`/api/users/${encodeURIComponent(ownerId)}/identity`)
      setIdentity(data)
    } finally {
      setLoading(false)
      setRevealed(true)
    }
  }

  if (!revealed) {
    return (
      <button onClick={reveal} className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-blue-500 transition-colors" title="Révéler l'identité">
        {loading ? <Loader size={11} className="animate-spin text-blue-400" /> : <Eye size={11} />}
        <span className="font-mono">{ownerId}</span>
      </button>
    )
  }

  const name = [identity?.first_name, identity?.last_name].filter(Boolean).join(' ') || identity?.username || null
  return (
    <div className="flex flex-col gap-0.5" title={ownerId}>
      {name
        ? <span className="text-xs font-medium text-neutral-700">{name}</span>
        : <span className="font-mono text-xs text-neutral-500">{ownerId}</span>
      }
      {identity?.email && <span className="text-xs text-neutral-400">{identity.email}</span>}
    </div>
  )
}
