import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ResponsiveContainer, AreaChart, Area, Tooltip, XAxis, YAxis } from 'recharts'
import { apiFetch } from '../api'
import { useVMStatus } from '../contexts/VMStatusContext'

interface MetricPoint {
  time: number | null
  cpu: number | null
  mem: number | null
  maxmem: number | null
}

interface ChartPoint {
  time: number | null
  cpu: number | null
  ram: number | null
}

interface Props {
  vmId: number
  name: string
}

export default function VMOverviewChart({ vmId, name }: Props) {
  const [data, setData] = useState<ChartPoint[]>([])
  const entry = useVMStatus(vmId)
  const running = entry?.status === 'running'

  useEffect(() => {
    apiFetch<{ items: MetricPoint[] }>(`/api/vms/${vmId}/metrics?timeframe=hour`)
      .then(r => setData(r.items.map(p => ({
        time: p.time,
        cpu: p.cpu != null ? p.cpu * 100 : null,
        ram: p.mem != null && p.maxmem ? (p.mem / p.maxmem) * 100 : null,
      }))))
      .catch(() => null)
  }, [vmId])

  const hasDat = data.some(d => d.cpu != null || d.ram != null)

  return (
    <Link
      to={`/vm/${vmId}`}
      className="md:col-span-3 xl:col-span-2 border border-neutral-100 shadow-md rounded-sm bg-white px-4 py-3 flex flex-col h-32 xl:h-auto hover:border-neutral-300 transition-colors"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-2 h-2 rounded-full shrink-0 ${running ? 'bg-emerald-400' : 'bg-red-400'}`} />
        <p className="text-xs font-semibold text-neutral-700 truncate">{name}</p>
        <span className={`ml-auto text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${running ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-400'}`}>
          {entry?.status ?? '…'}
        </span>
      </div>

      {!hasDat ? (
        <div className="flex-1 flex items-center justify-center text-neutral-300 text-xs">Aucune donnée</div>
      ) : (
        <>
          <div className="flex gap-3 mb-1.5">
            <span className="flex items-center gap-1 text-[10px] text-neutral-400"><span className="w-2 h-0.5 rounded bg-violet-500 inline-block" />CPU</span>
            <span className="flex items-center gap-1 text-[10px] text-neutral-400"><span className="w-2 h-0.5 rounded bg-blue-500 inline-block" />RAM</span>
          </div>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 2, right: 2, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={`cpu-${vmId}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id={`ram-${vmId}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" hide />
                <YAxis hide domain={[0, 100]} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    return (
                      <div className="bg-white border border-neutral-200 rounded px-2 py-1 text-xs shadow flex flex-col gap-0.5">
                        {payload.map((p, i) => (
                          <span key={i} style={{ color: p.color }}>
                            {i === 0 ? 'CPU' : 'RAM'}: {(p.value as number).toFixed(1)} %
                          </span>
                        ))}
                      </div>
                    )
                  }}
                />
                <Area type="monotone" dataKey="cpu" stroke="#8b5cf6" strokeWidth={1.5} fill={`url(#cpu-${vmId})`} dot={false} isAnimationActive={false} />
                <Area type="monotone" dataKey="ram" stroke="#3b82f6" strokeWidth={1.5} fill={`url(#ram-${vmId})`} dot={false} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Link>
  )
}
