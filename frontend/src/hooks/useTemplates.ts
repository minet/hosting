import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { TemplateListSchema } from '../schemas'

interface Template {
  template_id: number
  name: string
}

export function useTemplates() {
  const [templates, setTemplates] = useState<Template[]>([])
  const { toast } = useToast()

  useEffect(() => {
    apiFetch('/api/templates', undefined, TemplateListSchema)
      .then(r => setTemplates(r.items))
      .catch(err => toast(err.message ?? 'Impossible de charger les templates'))
  }, [])

  return templates
}
