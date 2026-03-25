import { useState, useEffect, useMemo, memo, useCallback } from 'react'
import { ResponsiveContainer, AreaChart, Area, Tooltip, XAxis, YAxis } from 'recharts'
import { Loader, RefreshCw, Server, HardDrive, Cpu, MemoryStick, Clock } from 'lucide-react'
import { useProxmoxStatus, type ProxmoxNode, type ProxmoxStorage } from '../../hooks/useProxmoxStatus'
import { apiFetch } from '../../api'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['Ko', 'Mo', 'Go', 'To']
  let i = -1
  let val = bytes
  do { val /= 1024; i++ } while (val >= 1024 && i < units.length - 1)
  return `${val.toFixed(1)} ${units[i]}`
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}j ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  const bg = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-500' : color
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${bg}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-neutral-500 w-12 text-right">{pct.toFixed(0)}%</span>
    </div>
  )
}

function formatRate(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} Go/s`
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} Mo/s`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} Ko/s`
  return `${bytes.toFixed(0)} o/s`
}

interface NodeMetricDef {
  key: string
  label: string
  colorA: string
  colorB?: string
  labelA?: string
  labelB?: string
  extract: (p: Record<string, number | null>) => { a: number | null; b?: number | null }
  format: (v: number) => string
}

const NODE_METRICS: NodeMetricDef[] = [
  {
    key: 'cpu', label: 'CPU', colorA: '#8b5cf6',
    extract: p => ({ a: p.cpu != null ? p.cpu * 100 : null }),
    format: v => `${v.toFixed(1)} %`,
  },
  {
    key: 'ram', label: 'RAM', colorA: '#3b82f6',
    extract: p => ({ a: p.memused != null && p.memtotal ? (p.memused / p.memtotal) * 100 : null }),
    format: v => `${v.toFixed(1)} %`,
  },
  {
    key: 'iowait', label: 'IO Wait', colorA: '#f59e0b',
    extract: p => ({ a: p.iowait != null ? p.iowait * 100 : null }),
    format: v => `${v.toFixed(1)} %`,
  },
  {
    key: 'net', label: 'Réseau', colorA: '#06b6d4', colorB: '#ec4899',
    labelA: 'In', labelB: 'Out',
    extract: p => ({ a: p.netin, b: p.netout }),
    format: formatRate,
  },
]

const NODE_TIMEFRAMES = [
  { key: 'hour',  label: '1h' },
  { key: 'day',   label: '1j' },
  { key: 'week',  label: '1sem' },
  { key: 'month', label: '1mois' },
  { key: 'year',  label: '1an' },
]

const NodeChartTooltip = memo(function NodeChartTooltip({ active, payload, def }: { active?: boolean; payload?: { color: string; value: number }[]; def: NodeMetricDef }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-neutral-200 rounded px-2 py-1 text-xs text-neutral-700 shadow flex flex-col gap-0.5">
      {payload.map((p, i) => (
        <span key={i} style={{ color: p.color }}>
          {i === 0 && def.labelA ? `${def.labelA}: ` : i === 1 && def.labelB ? `${def.labelB}: ` : ''}
          {def.format(p.value)}
        </span>
      ))}
    </div>
  )
})

function NodeMetricChart({ nodes }: { nodes: ProxmoxNode[] }) {
  const [selectedNode, setSelectedNode] = useState(nodes[0]?.node ?? '')
  const [selectedMetric, setSelectedMetric] = useState('cpu')
  const [timeframe, setTimeframe] = useState('hour')
  const [rawData, setRawData] = useState<Record<string, number | null>[]>([])
  const [loading, setLoading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const def = NODE_METRICS.find(m => m.key === selectedMetric) ?? NODE_METRICS[0]
  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  useEffect(() => {
    if (!selectedNode) return
    setLoading(true)
    apiFetch<{ items: Record<string, number | null>[] }>(`/api/cluster/nodes/${selectedNode}/metrics?timeframe=${timeframe}`)
      .then(r => setRawData(r.items))
      .catch(() => setRawData([]))
      .finally(() => setLoading(false))
  }, [selectedNode, timeframe, refreshKey])

  const data = useMemo(() =>
    rawData.map(p => ({ time: p.time, a: def.extract(p).a, b: def.extract(p).b })),
    [rawData, def]
  )
  const filled = data.filter(d => d.a != null)

  return (
    <div className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 flex flex-col" style={{ minHeight: 320 }}>
      {/* Header: node selector + refresh + timeframes */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <select
            value={selectedNode}
            onChange={e => setSelectedNode(e.target.value)}
            className="text-xs font-semibold text-neutral-700 bg-neutral-50 border border-neutral-200 rounded px-2 py-1"
          >
            {nodes.map(n => <option key={n.node} value={n.node}>{n.node}</option>)}
          </select>
          <button onClick={refresh} disabled={loading} className="text-neutral-300 hover:text-neutral-500 transition-colors cursor-pointer disabled:opacity-40">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
        <div className="flex gap-1">
          {NODE_TIMEFRAMES.map(tf => (
            <button
              key={tf.key}
              onClick={() => setTimeframe(tf.key)}
              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold transition-colors cursor-pointer ${
                timeframe === tf.key ? 'bg-neutral-900 text-white' : 'text-neutral-400 hover:text-neutral-600'
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* Metric selector */}
      <div className="flex gap-1 flex-wrap mb-3">
        {NODE_METRICS.map(m => (
          <button
            key={m.key}
            onClick={() => setSelectedMetric(m.key)}
            className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-colors cursor-pointer border ${
              selectedMetric === m.key ? 'text-white border-transparent' : 'text-neutral-400 border-neutral-200 hover:border-neutral-300'
            }`}
            style={selectedMetric === m.key ? { backgroundColor: m.colorA, borderColor: m.colorA } : {}}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-neutral-300 text-xs">Chargement…</div>
      ) : filled.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-neutral-300 text-xs">Aucune donnée</div>
      ) : (
        <div className="flex-1 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`node-grad-a-${def.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={def.colorA} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={def.colorA} stopOpacity={0} />
                </linearGradient>
                {def.colorB && (
                  <linearGradient id={`node-grad-b-${def.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={def.colorB} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={def.colorB} stopOpacity={0} />
                  </linearGradient>
                )}
              </defs>
              <XAxis dataKey="time" hide />
              <YAxis hide domain={[0, 'auto']} />
              <Tooltip content={<NodeChartTooltip def={def} />} />
              <Area type="monotone" dataKey="a" stroke={def.colorA} strokeWidth={2}
                fill={`url(#node-grad-a-${def.key})`} dot={false} isAnimationActive={false} />
              {def.colorB && (
                <Area type="monotone" dataKey="b" stroke={def.colorB} strokeWidth={2}
                  fill={`url(#node-grad-b-${def.key})`} dot={false} isAnimationActive={false} />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function NodeCard({ node }: { node: ProxmoxNode }) {
  const isOnline = node.status === 'online'
  return (
    <div className="border border-neutral-200 rounded-lg p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Server size={16} className="text-neutral-400" />
          <span className="font-semibold text-neutral-800">{node.node}</span>
        </div>
        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${isOnline ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' : 'bg-red-50 text-red-500 border border-red-200'}`}>
          {node.status}
        </span>
      </div>

      <div className="flex flex-col gap-3">
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="flex items-center gap-1 text-xs text-violet-600">
              <Cpu size={12} /> CPU
            </span>
            <span className="text-xs font-mono text-neutral-500">
              {(node.cpu * 100).toFixed(1)}% de {node.maxcpu} cores
            </span>
          </div>
          <ProgressBar value={node.cpu * node.maxcpu} max={node.maxcpu} color="bg-violet-500" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="flex items-center gap-1 text-xs text-blue-600">
              <MemoryStick size={12} /> RAM
            </span>
            <span className="text-xs font-mono text-neutral-500">
              {formatBytes(node.mem)} / {formatBytes(node.maxmem)}
            </span>
          </div>
          <ProgressBar value={node.mem} max={node.maxmem} color="bg-blue-500" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="flex items-center gap-1 text-xs text-emerald-600">
              <HardDrive size={12} /> Disque local
            </span>
            <span className="text-xs font-mono text-neutral-500">
              {formatBytes(node.disk)} / {formatBytes(node.maxdisk)}
            </span>
          </div>
          <ProgressBar value={node.disk} max={node.maxdisk} color="bg-emerald-500" />
        </div>

        {node.uptime > 0 && (
          <div className="flex items-center gap-1 text-xs text-neutral-400 pt-1 border-t border-neutral-100">
            <Clock size={11} />
            Uptime: <span className="font-mono">{formatUptime(node.uptime)}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function StorageTable({ storages }: { storages: ProxmoxStorage[] }) {
  const grouped = new Map<string, ProxmoxStorage[]>()
  for (const s of storages) {
    const key = s.storage
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key)!.push(s)
  }

  return (
    <div className="border border-neutral-200 rounded-lg overflow-hidden shadow-sm">
      <table className="w-full text-sm border-collapse">
        <thead className="bg-neutral-50 border-b border-neutral-200">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">Storage</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">Noeud</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">Type</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">Statut</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider w-64">Utilisation</th>
            <th className="px-3 py-2 text-right text-xs font-semibold text-neutral-500 uppercase tracking-wider">Taille</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-neutral-100">
          {storages.length === 0 && (
            <tr><td colSpan={6} className="px-4 py-8 text-center text-neutral-400 text-xs">Aucun stockage</td></tr>
          )}
          {storages.map((s, i) => (
            <tr key={i} className="hover:bg-neutral-50 transition-colors">
              <td className="px-3 py-2 font-medium text-neutral-700">{s.storage}</td>
              <td className="px-3 py-2 text-xs text-neutral-500">{s.node}</td>
              <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{s.plugintype}</td>
              <td className="px-3 py-2 text-xs">
                <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${s.status === 'available' ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' : 'bg-red-50 text-red-500 border border-red-200'}`}>
                  {s.status}
                </span>
              </td>
              <td className="px-3 py-2">
                {s.maxdisk > 0 && <ProgressBar value={s.disk} max={s.maxdisk} color="bg-emerald-500" />}
              </td>
              <td className="px-3 py-2 text-xs font-mono text-neutral-500 text-right">
                {s.maxdisk > 0 ? formatBytes(s.maxdisk) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ProxmoxTab() {
  const { data, loading, error, refresh } = useProxmoxStatus()

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-neutral-400 text-sm">
        <Loader size={16} className="animate-spin mr-2" /> Chargement du statut Proxmox...
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <p className="text-sm text-red-500">{error ?? 'Erreur inconnue'}</p>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 hover:bg-neutral-700 text-white text-xs font-semibold transition-colors cursor-pointer">
          <RefreshCw size={12} /> Réessayer
        </button>
      </div>
    )
  }

  const totalCpu = data.nodes.reduce((a, n) => a + n.maxcpu, 0)
  const usedCpu = data.nodes.reduce((a, n) => a + n.cpu * n.maxcpu, 0)
  const totalMem = data.nodes.reduce((a, n) => a + n.maxmem, 0)
  const usedMem = data.nodes.reduce((a, n) => a + n.mem, 0)
  const totalDisk = data.nodes.reduce((a, n) => a + n.maxdisk, 0)
  const usedDisk = data.nodes.reduce((a, n) => a + n.disk, 0)

  return (
    <div className="flex flex-col gap-6 h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold text-neutral-800">Proxmox VE</h1>
          {data.version && (
            <span className="text-xs font-mono text-neutral-400">
              v{data.version.version}{data.version.release ? `-${data.version.release}` : ''}
            </span>
          )}
        </div>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100 text-xs font-medium transition-colors cursor-pointer">
          <RefreshCw size={12} /> Actualiser
        </button>
      </div>

      {/* Cluster summary */}
      <div className="grid grid-cols-3 gap-4 shrink-0">
        <div className="border border-neutral-200 rounded-lg p-4 bg-white shadow-sm">
          <div className="flex items-center gap-1 text-xs text-violet-600 mb-2">
            <Cpu size={12} /> CPU Cluster
          </div>
          <div className="text-lg font-mono font-semibold text-neutral-800 mb-1">
            {totalCpu > 0 ? (usedCpu / totalCpu * 100).toFixed(1) : 0}%
          </div>
          <div className="text-xs text-neutral-400">{usedCpu.toFixed(1)} / {totalCpu} cores</div>
          <div className="mt-2"><ProgressBar value={usedCpu} max={totalCpu} color="bg-violet-500" /></div>
        </div>
        <div className="border border-neutral-200 rounded-lg p-4 bg-white shadow-sm">
          <div className="flex items-center gap-1 text-xs text-blue-600 mb-2">
            <MemoryStick size={12} /> RAM Cluster
          </div>
          <div className="text-lg font-mono font-semibold text-neutral-800 mb-1">
            {totalMem > 0 ? (usedMem / totalMem * 100).toFixed(1) : 0}%
          </div>
          <div className="text-xs text-neutral-400">{formatBytes(usedMem)} / {formatBytes(totalMem)}</div>
          <div className="mt-2"><ProgressBar value={usedMem} max={totalMem} color="bg-blue-500" /></div>
        </div>
        <div className="border border-neutral-200 rounded-lg p-4 bg-white shadow-sm">
          <div className="flex items-center gap-1 text-xs text-emerald-600 mb-2">
            <HardDrive size={12} /> Disque Cluster
          </div>
          <div className="text-lg font-mono font-semibold text-neutral-800 mb-1">
            {totalDisk > 0 ? (usedDisk / totalDisk * 100).toFixed(1) : 0}%
          </div>
          <div className="text-xs text-neutral-400">{formatBytes(usedDisk)} / {formatBytes(totalDisk)}</div>
          <div className="mt-2"><ProgressBar value={usedDisk} max={totalDisk} color="bg-emerald-500" /></div>
        </div>
      </div>

      {/* Node metrics chart */}
      {data.nodes.length > 0 && (
        <div className="shrink-0">
          <h2 className="text-sm font-semibold text-neutral-700 mb-3">Métriques</h2>
          <NodeMetricChart nodes={data.nodes} />
        </div>
      )}

      {/* Nodes */}
      <div className="shrink-0">
        <h2 className="text-sm font-semibold text-neutral-700 mb-3">
          Noeuds <span className="text-neutral-400 font-normal">({data.nodes.length})</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.nodes.map(n => <NodeCard key={n.node} node={n} />)}
        </div>
      </div>

      {/* Storage */}
      <div className="shrink-0">
        <h2 className="text-sm font-semibold text-neutral-700 mb-3">
          Stockage <span className="text-neutral-400 font-normal">({data.storages.length})</span>
        </h2>
        <StorageTable storages={data.storages} />
      </div>
    </div>
  )
}
