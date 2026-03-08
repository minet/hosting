import ResourceGauge from '../components/ResourceGauge'
import WelcomeCard from '../components/WelcomeCard'
import VMOverviewChart from '../components/VMOverviewChart'
import { useResources } from '../hooks/useResources'
import { useVMs } from '../hooks/useVMs'

export default function Dashboard() {
  const resources = useResources()
  const vms = useVMs()
  const ownerVMs = vms.filter(v => v.role === 'owner')
  const { usage, limits } = resources ?? {}

  const gaugeConfig = usage && limits ? [
    { label: 'RAM',    used: Math.round(usage.ram_mb / 1024), total: Math.round(limits.ram_mb / 1024), unit: 'Go',    color: 'blue'    },
    { label: 'Disque', used: usage.disk_gb,                   total: limits.disk_gb,                   unit: 'Go',    color: 'emerald' },
    { label: 'CPU',    used: usage.cpu_cores,                 total: limits.cpu_cores,                 unit: 'cœurs', color: 'violet'  },
  ] : null

  return (
    <div className="flex flex-col gap-3 md:grid md:grid-cols-3 xl:grid-cols-6 xl:grid-rows-[auto_1fr_1fr_1fr] xl:h-full">

      {/* Welcome */}
      <div className="border border-neutral-100 shadow-md rounded-sm bg-white md:h-64 xl:h-auto md:row-span-2 md:col-span-3 xl:col-span-3">
        <WelcomeCard />
      </div>

      {/* Titre gauges — masqué sur mobile */}
      <div className="hidden md:flex md:col-span-3 xl:col-span-3 items-center justify-center px-3 py-2 border border-neutral-100 shadow-md rounded-sm bg-white">
        <span className="text-sm font-semibold text-neutral-600">Utilisation de vos ressources allouées</span>
      </div>

      {/* Gauges — sur mobile : 3 en une ligne */}
      <div className="border border-neutral-100 shadow-md rounded-sm bg-white h-32 xl:h-auto grid grid-cols-3 md:hidden p-2">
        {gaugeConfig && gaugeConfig.map(g => (
          <ResourceGauge key={g.label} label={g.label} used={g.used} total={g.total} unit={g.unit} color={g.color} />
        ))}
      </div>

      {/* Gauges — sur md+ : une par cellule */}
      {gaugeConfig && gaugeConfig.map(g => (
        <div key={g.label} className="hidden md:flex border border-neutral-100 shadow-md rounded-sm bg-white h-32 xl:h-auto items-center justify-center p-2">
          <ResourceGauge label={g.label} used={g.used} total={g.total} unit={g.unit} color={g.color} />
        </div>
      ))}

      {ownerVMs.map(vm => (
        <VMOverviewChart key={vm.vm_id} vmId={vm.vm_id} name={vm.name} />
      ))}
    </div>
  )
}
