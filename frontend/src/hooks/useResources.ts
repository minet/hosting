import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { ResourcesSchema, type Resources } from '../schemas'

const CACHE_KEY = 'resources_cache'

function readCache(): Resources | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function writeCache(data: Resources) {
  try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(data)) } catch { /* ignore */ }
}

export function useResources() {
  const [resources, setResources] = useState<Resources | null>(readCache)
  const { toast } = useToast()

  useEffect(() => {
    apiFetch('/api/users/me/resources', undefined, ResourcesSchema)
      .then(data => { writeCache(data); setResources(data) })
      .catch(err => toast(err.message ?? 'Impossible de charger les ressources'))
  }, [])

  return resources
}
