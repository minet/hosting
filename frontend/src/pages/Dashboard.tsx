import { lazy, Suspense, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import ResourceGauge from '../components/ResourceGauge'
import WelcomeCard from '../components/WelcomeCard'
const VMOverviewChart = lazy(() => import('../components/VMOverviewChart'))
import { ChartCardSkeleton } from '../components/Skeleton'
import { useResources } from '../hooks/useResources'
import { useVMs } from '../hooks/useVMs'
import { apiFetch } from '../api'

interface MetricPoint {
  time: number | null
  cpu: number | null
  mem: number | null
  maxmem: number | null
}

export interface ChartPoint {
  time: number | null
  cpu: number | null
  ram: number | null
}

function toChartPoints(items: MetricPoint[]): ChartPoint[] {
  return items.map(p => ({
    time: p.time,
    cpu: p.cpu != null ? p.cpu * 100 : null,
    ram: p.mem != null && p.maxmem ? (p.mem / p.maxmem) * 100 : null,
  }))
}

export default function Dashboard() {
  const resources = useResources()
  const { vms, loading: vmsLoading } = useVMs()
  const ownerVMs = useMemo(() => vms.filter(v => v.role === 'owner'), [vms])
  const { usage, limits } = resources ?? {}
  const { t } = useTranslation('dashboard')
  const tc = useTranslation().t

  const vmIds = useMemo(() => ownerVMs.map(v => v.vm_id).join(','), [ownerVMs])
  const metricsQuery = useQuery({
    queryKey: ['dashboard-metrics', vmIds],
    queryFn: async () => {
      const r = await apiFetch<{ items: Record<string, MetricPoint[]> }>(`/api/vms/metrics/batch?vm_ids=${vmIds}&timeframe=hour`)
      const map: Record<string, ChartPoint[]> = {}
      for (const [id, items] of Object.entries(r.items)) {
        map[id] = toChartPoints(items)
      }
      return map
    },
    enabled: ownerVMs.length > 0,
  })
  const metricsMap = metricsQuery.data ?? {}

  const gaugeConfig = usage && limits ? [
    { label: 'RAM',    used: Math.round(usage.ram_mb / 1024), total: Math.round(limits.ram_mb / 1024), unit: tc('gb'),    color: 'blue'    },
    { label: 'Disk',   used: usage.disk_gb,                   total: limits.disk_gb,                   unit: tc('gb'),    color: 'emerald' },
    { label: 'CPU',    used: usage.cpu_cores,                 total: limits.cpu_cores,                 unit: tc('cores', { count: limits.cpu_cores }), color: 'violet'  },
  ] : null

  return (
    <div className="flex flex-col gap-3 h-full">

      {/* Top section: Welcome + Gauges */}
      <div className="flex flex-col gap-3 md:grid md:grid-cols-3 xl:grid-cols-6 shrink-0">

        {/* Welcome */}
        <div className="border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 md:h-64 md:row-span-2 md:col-span-3 xl:col-span-3">
          <WelcomeCard />
        </div>

        {/* Gauges — mobile */}
        <div className="border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 h-32 grid grid-cols-3 md:hidden p-2">
          {gaugeConfig ? gaugeConfig.map(g => (
            <ResourceGauge key={g.label} label={g.label} used={g.used} total={g.total} unit={g.unit} color={g.color} />
          )) : <div className="col-span-3 flex items-center justify-center"><div className="h-16 w-16 rounded-full bg-neutral-100 dark:bg-neutral-800 animate-pulse" /></div>}
        </div>

        {/* Titre + Gauges — md+ */}
        <div className="hidden md:flex md:col-span-3 xl:col-span-3 md:row-span-2 flex-col gap-1.5">
          <div className="flex items-center px-3 py-1 border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900">
            <span className="text-xs font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">{t('resourceUsage')}</span>
          </div>
          <div className="grid grid-cols-3 gap-3 flex-1">
            {(gaugeConfig ?? [{ label: 'RAM' }, { label: 'Disk' }, { label: 'CPU' }]).map(g => (
              <div key={g.label} className="flex border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 items-center justify-center p-2">
                {'used' in g ? <ResourceGauge label={g.label} used={g.used} total={g.total} unit={g.unit} color={g.color} /> : null}
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* VM section */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-3 gap-3 pb-3">
          {vmsLoading ? (
            <>
              <ChartCardSkeleton className="h-32" />
              <ChartCardSkeleton className="h-32" />
              <ChartCardSkeleton className="h-32" />
            </>
          ) : (
            ownerVMs.map(vm => (
              <Suspense key={vm.vm_id} fallback={<ChartCardSkeleton className="h-32" />}>
                <VMOverviewChart vmId={vm.vm_id} name={vm.name} data={metricsMap[String(vm.vm_id)]} />
              </Suspense>
            ))
          )}
        </div>
      </div>

    </div>
  )
}
