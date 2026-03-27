import { useState, useEffect, useMemo, memo, useCallback } from 'react'
import { ResponsiveContainer, AreaChart, Area, Tooltip, XAxis, YAxis } from 'recharts'
import { RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'

interface MetricPoint {
  time: number | null
  cpu: number | null
  mem: number | null
  maxmem: number | null
  diskread: number | null
  diskwrite: number | null
  netin: number | null
  netout: number | null
}

interface ChartPoint {
  time: number | null
  a: number | null
  b?: number | null
}

interface MetricDef {
  key: string
  label: string
  colorA: string
  colorB?: string
  labelA?: string
  labelB?: string
  extractA: (p: MetricPoint) => number | null
  extractB?: (p: MetricPoint) => number | null
  format: (v: number) => string
}

function formatRate(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB/s`
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB/s`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB/s`
  return `${bytes.toFixed(0)} B/s`
}

const ChartTooltip = memo(function ChartTooltip({ active, payload, def }: { active?: boolean; payload?: { color: string; value: number }[]; def: MetricDef }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded px-2 py-1 text-xs text-neutral-700 dark:text-neutral-300 shadow flex flex-col gap-0.5">
      {payload.map((p, i) => (
        <span key={i} style={{ color: p.color }}>
          {i === 0 && def.labelA ? `${def.labelA}: ` : i === 1 && def.labelB ? `${def.labelB}: ` : ''}
          {def.format(p.value as number)}
        </span>
      ))}
    </div>
  )
})

interface Props {
  vmId: string
  className?: string
}

export default function MetricChart({ vmId, className = '' }: Props) {
  const { t } = useTranslation('vm')
  const tc = useTranslation().t

  const METRICS: MetricDef[] = useMemo(() => [
    {
      key: 'cpu',    label: 'CPU',       colorA: '#8b5cf6',
      extractA: p => p.cpu != null ? p.cpu * 100 : null,
      format: v => `${v.toFixed(1)} %`,
    },
    {
      key: 'ram',    label: 'RAM',       colorA: '#3b82f6',
      extractA: p => p.mem != null && p.maxmem ? (p.mem / p.maxmem) * 100 : null,
      format: v => `${v.toFixed(1)} %`,
    },
    {
      key: 'diskread',  label: 'Disk Read',  colorA: '#10b981',
      extractA: p => p.diskread,
      format: formatRate,
    },
    {
      key: 'diskwrite', label: 'Disk Write', colorA: '#f59e0b',
      extractA: p => p.diskwrite,
      format: formatRate,
    },
    {
      key: 'net', label: t('metrics.network'), colorA: '#06b6d4', colorB: '#ec4899',
      labelA: 'In', labelB: 'Out',
      extractA: p => p.netin,
      extractB: p => p.netout,
      format: formatRate,
    },
  ], [t])

  const TIMEFRAMES = useMemo(() => [
    { key: 'hour',  label: tc('timeframes.hour') },
    { key: 'day',   label: tc('timeframes.day') },
    { key: 'week',  label: tc('timeframes.week') },
    { key: 'month', label: tc('timeframes.month') },
    { key: 'year',  label: tc('timeframes.year') },
  ], [tc])

  const [selectedKey, setSelectedKey] = useState('cpu')
  const [timeframe, setTimeframe] = useState('hour')
  const [rawData, setRawData] = useState<MetricPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const def = METRICS.find(m => m.key === selectedKey) ?? METRICS[0]

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  useEffect(() => {
    setLoading(true)
    apiFetch<{ items: MetricPoint[] }>(`/api/vms/${vmId}/metrics?timeframe=${timeframe}`)
      .then(r => setRawData(r.items))
      .catch(() => setRawData([]))
      .finally(() => setLoading(false))
  }, [vmId, timeframe, refreshKey])

  const data: ChartPoint[] = useMemo(() =>
    rawData.map(p => ({
      time: p.time,
      a: def.extractA(p),
      b: def.extractB ? def.extractB(p) : undefined,
    })),
    [rawData, def]
  )

  const filled = data.filter(d => d.a != null)

  return (
    <div className={`border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 px-4 py-3 flex flex-col overflow-hidden ${className}`}>
      <div className="flex items-center justify-between mb-1.5 min-w-0 gap-2">
        <div className="flex items-center gap-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">{def.label}</p>
          <button
            onClick={refresh}
            disabled={loading}
            className="text-neutral-300 dark:text-neutral-600 hover:text-neutral-500 dark:hover:text-neutral-400 transition-colors cursor-pointer disabled:opacity-40"
          >
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
        <div className="flex gap-1">
          {TIMEFRAMES.map(tf => (
            <button
              key={tf.key}
              onClick={() => setTimeframe(tf.key)}
              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold transition-colors cursor-pointer ${
                timeframe === tf.key
                  ? 'bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900'
                  : 'text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300'
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-1 flex-wrap mb-2">
        {METRICS.map(m => (
          <button
            key={m.key}
            onClick={() => setSelectedKey(m.key)}
            className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-colors cursor-pointer border ${
              selectedKey === m.key
                ? 'text-white border-transparent'
                : 'text-neutral-400 dark:text-neutral-500 border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600'
            }`}
            style={selectedKey === m.key ? { backgroundColor: m.colorA, borderColor: m.colorA } : {}}
          >
            {m.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-neutral-300 dark:text-neutral-600 text-xs">{tc('loading')}</div>
      ) : filled.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-neutral-300 dark:text-neutral-600 text-xs">{tc('noData')}</div>
      ) : (
        <div className="flex-1 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`grad-a-${def.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={def.colorA} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={def.colorA} stopOpacity={0} />
                </linearGradient>
                {def.colorB && (
                  <linearGradient id={`grad-b-${def.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={def.colorB} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={def.colorB} stopOpacity={0} />
                  </linearGradient>
                )}
              </defs>
              <XAxis dataKey="time" hide />
              <YAxis hide domain={[0, 'auto']} />
              <Tooltip content={<ChartTooltip def={def} />} />
              <Area type="monotone" dataKey="a" stroke={def.colorA} strokeWidth={2}
                fill={`url(#grad-a-${def.key})`} dot={false} isAnimationActive={false} />
              {def.extractB && (
                <Area type="monotone" dataKey="b" stroke={def.colorB} strokeWidth={2}
                  fill={`url(#grad-b-${def.key})`} dot={false} isAnimationActive={false} />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
