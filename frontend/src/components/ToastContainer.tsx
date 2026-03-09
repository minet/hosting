import { X } from 'lucide-react'
import { useToast } from '../contexts/ToastContext'

const typeStyles = {
  error: 'bg-red-50 border-red-200 text-red-700',
  success: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  info: 'bg-blue-50 border-blue-200 text-blue-700',
}

export default function ToastContainer() {
  const { toasts } = useToast()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map(t => (
        <div key={t.id} className={`flex items-start gap-2 px-4 py-3 rounded-lg border shadow-lg text-sm animate-[slideIn_0.2s_ease-out] ${typeStyles[t.type]}`}>
          <p className="flex-1">{t.message}</p>
        </div>
      ))}
    </div>
  )
}
