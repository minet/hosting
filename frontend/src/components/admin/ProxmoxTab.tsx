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
      <div className="flex-1 h-2 bg-neutral-100 dark:bg-neutral-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${bg}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-neutral-500 dark:text-neutral-400 w-12 text-right">{pct.toFixed(0)}%</span>
    </div>
  )
}

function NodeCard({ node }: { node: ProxmoxNode }) {
  const isOnline = node.status === 'online'
  return (
    <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg p-4 bg-white dark:bg-neutral-900 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between mb-4 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <Server size={16} className="text-neutral-400 dark:text-neutral-500 shrink-0" />
          <span className="font-semibold text-neutral-800 dark:text-neutral-200 truncate">{node.node}</span>
        </div>
        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${isOnline ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-950 text-red-500 dark:text-red-400 border border-red-200 dark:border-red-800'}`}>
          {node.status}
        </span>
      </div>

      <div className="flex flex-col gap-3">
        <div>
          <div className="flex items-center justify-between mb-1 min-w-0">
            <span className="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400">
              <Cpu size={12} /> CPU
            </span>
            <span className="text-xs font-mono text-neutral-500 dark:text-neutral-400 truncate ml-2">
              {(node.cpu * 100).toFixed(1)}% de {node.maxcpu} cores
            </span>
          </div>
          <ProgressBar value={node.cpu * node.maxcpu} max={node.maxcpu} color="bg-violet-500" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1 min-w-0">
            <span className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400">
              <MemoryStick size={12} /> RAM
            </span>
            <span className="text-xs font-mono text-neutral-500 dark:text-neutral-400 truncate ml-2">
              {formatBytes(node.mem)} / {formatBytes(node.maxmem)}
            </span>
          </div>
          <ProgressBar value={node.mem} max={node.maxmem} color="bg-blue-500" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1 min-w-0">
            <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
              <HardDrive size={12} /> Disque local
            </span>
            <span className="text-xs font-mono text-neutral-500 dark:text-neutral-400 truncate ml-2">
              {formatBytes(node.disk)} / {formatBytes(node.maxdisk)}
            </span>
          </div>
          <ProgressBar value={node.disk} max={node.maxdisk} color="bg-emerald-500" />
        </div>

        {node.uptime > 0 && (
          <div className="flex items-center gap-1 text-xs text-neutral-400 dark:text-neutral-500 pt-1 border-t border-neutral-100 dark:border-neutral-800">
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
    <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm overflow-x-auto">
      <table className="w-full text-sm border-collapse min-w-[600px]">
        <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Storage</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Noeud</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Type</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Statut</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider w-64">Utilisation</th>
            <th className="px-3 py-2 text-right text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">Taille</th>
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
          {storages.length === 0 && (
            <tr><td colSpan={6} className="px-4 py-8 text-center text-neutral-400 dark:text-neutral-500 text-xs">Aucun stockage</td></tr>
          )}
          {storages.map((s, i) => (
            <tr key={i} className="hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors">
              <td className="px-3 py-2 font-medium text-neutral-700 dark:text-neutral-300">{s.storage}</td>
              <td className="px-3 py-2 text-xs text-neutral-500 dark:text-neutral-400">{s.node}</td>
              <td className="px-3 py-2 text-xs text-neutral-500 dark:text-neutral-400 font-mono">{s.plugintype}</td>
              <td className="px-3 py-2 text-xs">
                <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${s.status === 'available' ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-950 text-red-500 dark:text-red-400 border border-red-200 dark:border-red-800'}`}>
                  {s.status}
                </span>
              </td>
              <td className="px-3 py-2">
                {s.maxdisk > 0 && <ProgressBar value={s.disk} max={s.maxdisk} color="bg-emerald-500" />}
              </td>
              <td className="px-3 py-2 text-xs font-mono text-neutral-500 dark:text-neutral-400 text-right">
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
      <div className="flex items-center justify-center py-20 text-neutral-400 dark:text-neutral-500 text-sm">
        <Loader size={16} className="animate-spin mr-2" /> Chargement du statut Proxmox...
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <p className="text-sm text-red-500">{error ?? 'Erreur inconnue'}</p>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-xs font-semibold transition-colors cursor-pointer">
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
          <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">Proxmox VE</h1>
          {data.version && (
            <span className="text-xs font-mono text-neutral-400 dark:text-neutral-500">
              v{data.version.version}{data.version.release ? `-${data.version.release}` : ''}
            </span>
          )}
        </div>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-medium transition-colors cursor-pointer">
          <RefreshCw size={12} /> Actualiser
        </button>
      </div>

      {/* Cluster summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 shrink-0">
        <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg p-4 bg-white dark:bg-neutral-900 shadow-sm overflow-hidden">
          <div className="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400 mb-2">
            <Cpu size={12} className="shrink-0" /> CPU Cluster
          </div>
          <div className="text-lg font-mono font-semibold text-neutral-800 dark:text-neutral-200 mb-1 truncate">
            {totalCpu > 0 ? (usedCpu / totalCpu * 100).toFixed(1) : 0}%
          </div>
          <div className="text-xs text-neutral-400 dark:text-neutral-500 truncate">{usedCpu.toFixed(1)} / {totalCpu} cores</div>
          <div className="mt-2"><ProgressBar value={usedCpu} max={totalCpu} color="bg-violet-500" /></div>
        </div>
        <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg p-4 bg-white dark:bg-neutral-900 shadow-sm overflow-hidden">
          <div className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 mb-2">
            <MemoryStick size={12} className="shrink-0" /> RAM Cluster
          </div>
          <div className="text-lg font-mono font-semibold text-neutral-800 dark:text-neutral-200 mb-1 truncate">
            {totalMem > 0 ? (usedMem / totalMem * 100).toFixed(1) : 0}%
          </div>
          <div className="text-xs text-neutral-400 dark:text-neutral-500 truncate">{formatBytes(usedMem)} / {formatBytes(totalMem)}</div>
          <div className="mt-2"><ProgressBar value={usedMem} max={totalMem} color="bg-blue-500" /></div>
        </div>
        <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg p-4 bg-white dark:bg-neutral-900 shadow-sm overflow-hidden">
          <div className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 mb-2">
            <HardDrive size={12} className="shrink-0" /> Disque Cluster
          </div>
          <div className="text-lg font-mono font-semibold text-neutral-800 dark:text-neutral-200 mb-1 truncate">
            {totalDisk > 0 ? (usedDisk / totalDisk * 100).toFixed(1) : 0}%
          </div>
          <div className="text-xs text-neutral-400 dark:text-neutral-500 truncate">{formatBytes(usedDisk)} / {formatBytes(totalDisk)}</div>
          <div className="mt-2"><ProgressBar value={usedDisk} max={totalDisk} color="bg-emerald-500" /></div>
        </div>
      </div>

      {/* Nodes */}
      <div className="shrink-0">
        <h2 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
          Noeuds <span className="text-neutral-400 dark:text-neutral-500 font-normal">({data.nodes.length})</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.nodes.map(n => <NodeCard key={n.node} node={n} />)}
        </div>
      </div>

      {/* Storage */}
      <div className="shrink-0">
        <h2 className="text-sm font-semibold text-neutral-700 dark:text-neutral-300 mb-3">
          Stockage <span className="text-neutral-400 dark:text-neutral-500 font-normal">({data.storages.length})</span>
        </h2>
        <StorageTable storages={data.storages} />
      </div>
    </div>
  )
}
