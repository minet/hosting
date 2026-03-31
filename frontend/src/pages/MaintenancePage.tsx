import { useTranslation } from 'react-i18next'

export default function MaintenancePage() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-neutral-50 dark:bg-neutral-950 px-6 text-center gap-6">
      <img src="/assets/pinguins/PinguinTriste.svg" alt="" className="w-40 h-40" />
      <h1 className="text-2xl font-bold text-neutral-800 dark:text-neutral-200">{t('maintenance.title')}</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 max-w-md">{t('maintenance.description')}</p>
    </div>
  )
}
