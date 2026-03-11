import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api'

export interface AdminTemplate {
  template_id: number
  name: string
}

export function useAdminTemplates() {
  const [templates, setTemplates] = useState<AdminTemplate[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(() => {
    setLoading(true)
    apiFetch<{ items: AdminTemplate[] }>('/api/templates')
      .then(r => setTemplates(r.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  async function create(template_id: number, name: string) {
    const tpl = await apiFetch<AdminTemplate>('/api/templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id, name }),
    })
    setTemplates(prev => [...prev, tpl].sort((a, b) => a.template_id - b.template_id))
    return tpl
  }

  async function remove(template_id: number) {
    await apiFetch<void>(`/api/templates/${template_id}`, { method: 'DELETE' })
    setTemplates(prev => prev.filter(t => t.template_id !== template_id))
  }

  return { templates, loading, create, remove, refresh }
}
