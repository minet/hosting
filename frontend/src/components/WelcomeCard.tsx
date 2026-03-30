import { ArrowRight, Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useOpenVMModal } from '../contexts/VMModalContext'
import { useUser } from '../contexts/UserContext'
import { useResources } from '../hooks/useResources'

export default function WelcomeCard() {
  const me = useUser()
  const name = me.prenom ?? me.username
  const resources = useResources()
  const openVMModal = useOpenVMModal()
  const adhId = me.user_id?.split(':').at(-1) ?? null
  const [copied, setCopied] = useState(false)
  const { t } = useTranslation('vm')

  function copyId() {
    if (!adhId) return
    if (navigator.clipboard) {
      navigator.clipboard.writeText(adhId).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }).catch(() => null)
    } else {
      const el = document.createElement('textarea')
      el.value = adhId
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const limits = resources?.limits

  return (
    <div className="flex flex-col md:h-full p-5 gap-4">
      <div className="flex items-center gap-3">
        <img src="/assets/logo/icon_hosting_dark.svg" alt="Hosting" className="h-8 md:h-8 xl:h-9 dark:hidden" />
        <img src="/assets/logo/icon_hosting_light.svg" alt="Hosting" className="h-8 md:h-8 xl:h-9 hidden dark:block" />
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-lg md:text-base xl:text-lg font-semibold text-neutral-800 dark:text-neutral-200">
            {t('welcome.title', { name })}
          </span>
          {adhId && (
            <span className="flex items-center gap-1">
              <span className="text-xs font-mono text-neutral-400 dark:text-neutral-500">#{adhId}</span>
              <button onClick={copyId} className="text-neutral-300 dark:text-neutral-600 hover:text-neutral-500 dark:hover:text-neutral-400 transition-colors cursor-pointer">
                {copied ? <Check size={11} className="text-emerald-500" /> : <Copy size={11} />}
              </button>
            </span>
          )}
        </div>
      </div>
      <div className="border-l-2 border-neutral-200 dark:border-neutral-700 pl-3 flex flex-col gap-3">
        <p className="text-sm md:text-xs xl:text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
          {t('welcome.description')}
          {limits && (
            <> <Trans
              i18nKey="welcome.limits"
              ns="vm"
              values={{ cpu: limits.cpu_cores, ram: limits.ram_mb / 1024, disk: limits.disk_gb }}
              components={{
                cores: <span className="text-neutral-700 dark:text-neutral-300 font-medium" />,
                ram: <span className="text-neutral-700 dark:text-neutral-300 font-medium" />,
                disk: <span className="text-neutral-700 dark:text-neutral-300 font-medium" />,
              }}
            /></>
          )}
        </p>
        {me.cotise_end_ms && (
          <p className="text-sm md:text-xs xl:text-xs text-neutral-500 dark:text-neutral-400">
            {t('welcome.subscriptionExpires')}{' '}
            <span className="text-neutral-700 dark:text-neutral-300 font-medium">
              {(() => {
                const diff = me.cotise_end_ms - Date.now()
                const days = Math.floor(diff / (1000 * 60 * 60 * 24))
                if (days > 365) return t('welcome.years', { count: Math.floor(days / 365) })
                if (days > 30) return t('welcome.months', { count: Math.floor(days / 30) })
                return t('welcome.days', { count: days })
              })()}
            </span>.
          </p>
        )}
      </div>
<button onClick={openVMModal} className="w-full h-16 md:flex-1 md:min-h-10 bg-blue-400/15 hover:bg-blue-400/25 active:bg-blue-400/40 border border-blue-200 dark:border-blue-700 shadow-sm hover:shadow-md text-blue-700 dark:text-blue-300 rounded-md flex flex-row items-center px-4 gap-4 font-medium transition-colors cursor-pointer">
        <img src="/assets/pinguins/PinguinFiere.svg" alt="Pinguin" className="h-[90%] w-auto" />
        <div className="flex flex-col items-start flex-1">
          <span className="font-semibold text-sm md:text-base xl:text-base">{t('createVM')}</span>
          <span className="hidden md:block text-xs text-blue-500 dark:text-blue-400 font-normal">{t('configureVM')}</span>
        </div>
        <ArrowRight className="h-5 w-5 text-blue-400" />
      </button>
    </div>
  )
}
