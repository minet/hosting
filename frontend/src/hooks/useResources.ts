import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

interface ResourceLimits {
  cpu_cores: number
  ram_mb: number
  disk_gb: number
}

interface ResourceUsage {
  vm_count: number
  cpu_cores: number
  ram_mb: number
  disk_gb: number
}

interface Resources {
  usage: ResourceUsage
  limits: ResourceLimits
  remaining: ResourceLimits
}

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

  useEffect(() => {
    apiFetch<Resources>('/api/users/me/resources')
      .then(data => { writeCache(data); setResources(data) })
      .catch(() => null)
  }, [])

  return resources
}
