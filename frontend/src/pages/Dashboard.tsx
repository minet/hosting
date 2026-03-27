import { lazy, Suspense, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
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
    { label: 'RAM',    used: Math.round(usage.ram_mb / 1024), total: Math.round(limits.ram_mb / 1024), unit: 'Go',    color: 'blue'    },
    { label: 'Disque', used: usage.disk_gb,                   total: limits.disk_gb,                   unit: 'Go',    color: 'emerald' },
    { label: 'CPU',    used: usage.cpu_cores,                 total: limits.cpu_cores,                 unit: 'cœurs', color: 'violet'  },
  ] : null

  return (
    <div className="flex flex-col gap-3 h-full">

      {/* Top section: Welcome + Gauges */}
      <div className="flex flex-col gap-3 md:grid md:grid-cols-3 xl:grid-cols-6 shrink-0">

        {/* Welcome */}
        <div className="border border-neutral-100 shadow-md rounded-sm bg-white md:h-64 md:row-span-2 md:col-span-3 xl:col-span-3">
          <WelcomeCard />
        </div>

        {/* Titre gauges — masqué sur mobile */}
        <div className="hidden md:flex md:col-span-3 xl:col-span-3 items-center justify-center px-3 py-2 border border-neutral-100 shadow-md rounded-sm bg-white">
          <span className="text-sm font-semibold text-neutral-600">Utilisation de vos ressources allouées</span>
        </div>

        {/* Gauges — sur mobile : 3 en une ligne */}
        <div className="border border-neutral-100 shadow-md rounded-sm bg-white h-32 grid grid-cols-3 md:hidden p-2">
          {gaugeConfig ? gaugeConfig.map(g => (
            <ResourceGauge key={g.label} label={g.label} used={g.used} total={g.total} unit={g.unit} color={g.color} />
          )) : <div className="col-span-3 flex items-center justify-center"><div className="h-16 w-16 rounded-full bg-neutral-100 animate-pulse" /></div>}
        </div>

        {/* Gauges — sur md+ : une par cellule */}
        {(gaugeConfig ?? [{ label: 'RAM' }, { label: 'Disque' }, { label: 'CPU' }]).map(g => (
          <div key={g.label} className="hidden md:flex border border-neutral-100 shadow-md rounded-sm bg-white items-center justify-center p-2">
            {'used' in g ? <ResourceGauge label={g.label} used={g.used} total={g.total} unit={g.unit} color={g.color} /> : null}
          </div>
        ))}

      </div>

      {/* VM section: scrollable */}
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
