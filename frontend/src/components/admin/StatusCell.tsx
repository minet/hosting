import { useVMStatus } from '../../contexts/VMStatusContext'

export default function StatusCell({ vmId }: { vmId: number }) {
  const entry = useVMStatus(vmId)
  const status = entry?.status
  const dot = !status ? 'bg-neutral-300' : status === 'running' ? 'bg-emerald-500' : 'bg-red-400'
  const label = !status
    ? <span className="text-neutral-400">—</span>
    : status === 'running'
      ? <span className="text-emerald-600 font-medium">running</span>
      : <span className="text-red-500 font-medium">{status}</span>
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${dot}`} />
      {label}
    </div>
  )
}
