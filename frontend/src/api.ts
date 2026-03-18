import type { ZodType } from 'zod'

export const API_BASE = import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000`

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
    return res.ok
  } catch { return false }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join(', ') || res.statusText
    }
    if (typeof body?.message === 'string') return body.message
  } catch { /* not JSON */ }
  return res.statusText || `Erreur ${res.status}`
}

export async function apiFetch<T>(path: string, init?: RequestInit, schema?: ZodType<T>): Promise<T> {
  let res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init })
  if (res.status === 401) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      res = await fetch(`${API_BASE}${path}`, { credentials: 'include', ...init })
    } else {
      window.location.href = loginUrl()
      throw new ApiError(401, 'Session expirée')
    }
  }
  if (!res.ok) {
    const message = await extractErrorMessage(res)
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  const data = await res.json()
  if (schema) return schema.parse(data)
  return data as T
}

export function loginUrl(): string {
  const redirect = encodeURIComponent(window.location.origin)
  return `${API_BASE}/api/auth/login?frontend_redirect=${redirect}`
}

export function logoutUrl(): string {
  const redirect = encodeURIComponent(window.location.origin)
  return `${API_BASE}/api/auth/logout?frontend_redirect=${redirect}`
}
