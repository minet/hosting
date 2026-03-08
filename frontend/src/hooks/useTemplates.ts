import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

interface Template {
  template_id: number
  name: string
}

export function useTemplates() {
  const [templates, setTemplates] = useState<Template[]>([])

  useEffect(() => {
    apiFetch<{ items: Template[] }>('/api/templates')
      .then(r => setTemplates(r.items))
      .catch(() => null)
  }, [])

  return templates
}
