import { Loader, Network } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../../api'

interface IPStats {
  total: number
  used: number
  free: number
  freeing_soon: number
  free_soon: number
}

function useIPStats() {
  const { data, isLoading: loading, error } = useQuery({
    queryKey: ['admin-ip-stats'],
    queryFn: () => apiFetch<IPStats>('/api/admin/ip-stats'),
  })
  return { stats: data ?? null, loading, error: error ? (error as Error).message : null }
}

function Legend({ color, label, title }: { color: string; label: string; title?: string }) {
  return (
    <span className="flex items-center gap-1.5 whitespace-nowrap" title={title}>
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${color}`} />
      <span className="text-neutral-600 dark:text-neutral-400">{label}</span>
    </span>
  )
}

/**
 * Compact IPv4 pool gauge: green = free now, blue = freed soon by the purge,
 * grey tail = addresses in use and staying.
 */
export default function IPPoolStats() {
  const { t } = useTranslation('admin')
  const { stats, loading, error } = useIPStats()

  const total = stats?.total ?? 0
  // Clamp so the segments never overflow the track (possible if the configured
  // pool size is lowered below the current usage).
  const free = stats ? Math.max(0, Math.min(stats.free, total)) : 0
  const soon = stats ? Math.max(0, Math.min(stats.freeing_soon, total - free)) : 0
  const staying = Math.max(0, total - free - soon)
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0)

  return (
    <div className="shrink-0 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-sm px-3 py-2">
      <div className="flex items-center gap-1.5 shrink-0">
        <Network size={14} className="text-neutral-400 dark:text-neutral-500" />
        <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">{t('ipPool.title')}</span>
      </div>

      {loading && <Loader size={14} className="animate-spin text-neutral-400" />}
      {!loading && error && <span className="text-xs text-red-500">{t('ipPool.error')}</span>}

      {!loading && !error && stats && (
        <>
          <div className="flex flex-1 min-w-[160px] h-3 rounded-full overflow-hidden bg-neutral-200 dark:bg-neutral-700">
            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct(free)}%` }} />
            <div className="h-full bg-blue-500 transition-all" style={{ width: `${pct(soon)}%` }} />
          </div>

          <div className="flex items-center gap-3 shrink-0 text-xs font-mono">
            <Legend color="bg-emerald-500" label={t('ipPool.free', { n: free })} />
            <Legend color="bg-blue-500" label={t('ipPool.soon', { n: soon })} title={t('ipPool.soonTotal', { n: stats.free_soon })} />
            <Legend color="bg-neutral-300 dark:bg-neutral-600" label={t('ipPool.used', { n: staying })} />
            <span className="text-neutral-400 dark:text-neutral-500">{t('ipPool.total', { n: total })}</span>
          </div>
        </>
      )}
    </div>
  )
}
