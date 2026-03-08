const API_BASE = import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000`

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
    return res.ok
  } catch { return false }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init })
  if (res.status === 401) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init })
    } else {
      window.location.href = loginUrl()
      throw res
    }
  }
  if (!res.ok) throw res
  return res.json() as Promise<T>
}

export function loginUrl(): string {
  const redirect = encodeURIComponent(window.location.origin)
  return `${API_BASE}/api/auth/login?frontend_redirect=${redirect}`
}

export function logoutUrl(): string {
  const redirect = encodeURIComponent(window.location.origin)
  return `${API_BASE}/api/auth/logout?frontend_redirect=${redirect}`
}
