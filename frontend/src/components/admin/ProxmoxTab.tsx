import { Loader, RefreshCw, Server, HardDrive, Cpu, MemoryStick, Clock } from 'lucide-react'
import { useProxmoxStatus, type ProxmoxNode, type ProxmoxStorage } from '../../hooks/useProxmoxStatus'

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
