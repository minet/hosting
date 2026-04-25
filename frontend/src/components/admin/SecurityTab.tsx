import { Loader, RefreshCw, Shield, ShieldAlert, Globe, Plug, Package, Zap, Server, KeyRound, Gamepad2, Cloud, Code2, Braces, Filter, Workflow, Database, Layers, type LucideIcon } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '../../api'

type UserLookup = Map<string, { name: string; email: string | null }>

interface CveEntry {
  id: string
  score: number
  published: string
}

interface SecurityFinding {
  ip: string
  ports: number[]
  hostnames: string[]
  cpes: string[]
  cves: CveEntry[]
}

interface SecurityScanResult {
  vm_id: number
  vm_name: string
  owner_id: string
  ipv4: string | null
  ipv6: string | null
  scanned_at: string | null
  findings: SecurityFinding[]
}

function useSecurityScans() {
  const qc = useQueryClient()
  const { data, isLoading: loading, error } = useQuery({
    queryKey: ['admin-security'],
    queryFn: () => apiFetch<SecurityScanResult[]>('/api/admin/security'),
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin-security'] })
  return { data: data ?? [], loading, error: error ? (error as Error).message : null, refresh }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function cveColor(score: number): string {
  if (score >= 9) return 'bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 border-red-300 dark:border-red-700'
  return 'bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300 border-orange-300 dark:border-orange-700'
}

function cvesByTier(cves: CveEntry[]): { critical: number; high: number; max: number } {
  const critical = cves.filter(c => c.score >= 9).length
  const high = cves.filter(c => c.score >= 8 && c.score < 9).length
  const max = cves.length > 0 ? Math.max(...cves.map(c => c.score)) : 0
  return { critical, high, max }
}


function CveSummary({ cves }: { cves: CveEntry[] }) {
  const { critical, high } = cvesByTier(cves)
  if (critical === 0 && high === 0) return null
  return (
    <div className="flex items-center gap-1.5">
      {critical > 0 && (
        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 border border-red-300 dark:border-red-700">
          🔴 {critical}
        </span>
      )}
      {high > 0 && (
        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300 border border-orange-300 dark:border-orange-700">
          🟠 {high}
        </span>
      )}
    </div>
  )
}

interface CpeInfo { Icon: LucideIcon; color: string; label: string; version?: string }

const CPE_MAP: Array<{ match: RegExp; Icon: LucideIcon; color: string; label: string }> = [
  { match: /openssh/,                Icon: KeyRound,  color: 'text-emerald-500', label: 'OpenSSH' },
  { match: /nginx/,                  Icon: Globe,     color: 'text-green-500',   label: 'nginx' },
  { match: /http_server/,            Icon: Globe,     color: 'text-orange-500',  label: 'Apache' },
  { match: /caddy/,                  Icon: Globe,     color: 'text-blue-500',    label: 'Caddy' },
  { match: /minecraft/,              Icon: Gamepad2,  color: 'text-green-600',   label: 'Minecraft' },
  { match: /cloudflare/,             Icon: Cloud,     color: 'text-orange-400',  label: 'Cloudflare' },
  { match: /elastic_load_balancing/, Icon: Cloud,     color: 'text-orange-500',  label: 'AWS ELB' },
  { match: /node\.?js|nodejs/,       Icon: Code2,     color: 'text-green-500',   label: 'Node.js' },
  { match: /express/,                Icon: Code2,     color: 'text-neutral-500', label: 'Express' },
  { match: /golang|:go$/,            Icon: Braces,    color: 'text-cyan-500',    label: 'Go' },
  { match: /squid/,                  Icon: Filter,    color: 'text-blue-500',    label: 'Squid' },
  { match: /n8n/,                    Icon: Workflow,  color: 'text-pink-500',    label: 'n8n' },
  { match: /minio/,                  Icon: Database,  color: 'text-red-500',     label: 'MinIO' },
  { match: /next\.js/,               Icon: Layers,    color: 'text-neutral-800 dark:text-neutral-200', label: 'Next.js' },
  { match: /facebook:react|:react/,  Icon: Layers,    color: 'text-blue-400',    label: 'React' },
  { match: /linux_kernel|debian/,    Icon: Server,    color: 'text-neutral-400', label: 'Linux' },
]

function parseCpe(cpe: string): CpeInfo {
  const parts = cpe.split(':').filter(p => p && !['cpe','a','o','h','*','-','2.3','/a','/o','/h','/'].includes(p))
  const version = parts.length >= 3 ? parts[2] : undefined
  for (const entry of CPE_MAP) {
    if (entry.match.test(cpe)) return { Icon: entry.Icon, color: entry.color, label: entry.label, version }
  }
  // inconnu : afficher vendor/product brut
  const label = parts.slice(0, 2).join('/') || cpe
  return { Icon: Package, color: 'text-neutral-400', label, version }
}

function CveBadge({ cve }: { cve: CveEntry }) {
  return (
    <a
      href={`https://cve.mitre.org/cgi-bin/cvename.cgi?name=${cve.id}`}
      target="_blank"
      rel="noopener noreferrer"
      title={`${cve.id} — publié le ${cve.published}`}
      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold border ${cveColor(cve.score)} hover:opacity-80 transition-opacity`}
    >
      {cve.score.toFixed(1)}
    </a>
  )
}

function FindingCells({ finding }: { finding: SecurityFinding }) {
  const sortedCves = [...finding.cves].sort((a, b) => b.score - a.score)

  return (
    <>
      {/* DNS */}
      <td className="px-2 py-1.5 text-xs">
        {finding.hostnames.length > 0 ? (
          <div className="flex items-center gap-1 flex-wrap">
            <Globe size={10} className="text-blue-400 shrink-0" />
            {finding.hostnames.map(h => (
              <span key={h} className="font-mono text-neutral-600 dark:text-neutral-400">{h}</span>
            ))}
          </div>
        ) : <span className="text-neutral-300 dark:text-neutral-600">—</span>}
      </td>

      {/* Ports */}
      <td className="px-2 py-1.5 text-xs">
        {finding.ports.length > 0 ? (
          <div className="flex items-center gap-1 flex-wrap">
            <Plug size={10} className="text-violet-400 shrink-0" />
            {finding.ports.map(p => (
              <span key={p} className="font-mono text-neutral-600 dark:text-neutral-400">{p}</span>
            ))}
          </div>
        ) : <span className="text-neutral-300 dark:text-neutral-600">—</span>}
      </td>

      {/* CPEs */}
      <td className="px-2 py-1.5 text-xs max-w-[220px]">
        {finding.cpes && finding.cpes.length > 0 ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            {finding.cpes.map(c => {
              const { Icon, color, label, version } = parseCpe(c)
              return (
                <span key={c} title={c} className="inline-flex items-center gap-0.5">
                  <Icon size={11} className={color} />
                  <span className="text-neutral-600 dark:text-neutral-400">{label}</span>
                  {version && <span className="text-neutral-400 dark:text-neutral-500 text-[10px]">{version}</span>}
                </span>
              )
            })}
          </div>
        ) : <span className="text-neutral-300 dark:text-neutral-600">—</span>}
      </td>

      {/* Résumé CVE par tier */}
      <td className="px-2 py-1.5 text-xs whitespace-nowrap">
        {sortedCves.length > 0
          ? <CveSummary cves={sortedCves} />
          : <span className="flex items-center gap-1"><Shield size={10} className="text-emerald-400" /><span className="text-emerald-600 dark:text-emerald-400 text-[10px]">OK</span></span>
        }
      </td>

      {/* CVEs détail */}
      <td className="px-2 py-1.5 text-xs">
        {sortedCves.length > 0 ? (
          <div className="flex items-center gap-1 flex-wrap">
            <ShieldAlert size={10} className="text-red-400 shrink-0" />
            {sortedCves.map(cve => <CveBadge key={cve.id} cve={cve} />)}
          </div>
        ) : <span className="text-neutral-300 dark:text-neutral-600">—</span>}
      </td>
    </>
  )
}

function ScanRows({ result, userLookup }: { result: SecurityScanResult; userLookup: UserLookup }) {
  const owner = userLookup.get(result.owner_id)
  const findings = result.findings.length > 0
    ? result.findings
    : [{ ip: result.ipv4 ?? result.ipv6 ?? '—', ports: [], hostnames: [], cpes: [], cves: [] }]

  return (
    <>
      {findings.map((finding, i) => (
        <tr key={finding.ip} className="hover:bg-neutral-50 dark:hover:bg-neutral-800/60 transition-colors border-b border-neutral-100 dark:border-neutral-800 last:border-0">
          {i === 0 && (
            <>
              <td rowSpan={findings.length} className="px-2 py-1.5 text-xs font-mono text-neutral-400 dark:text-neutral-500 align-top">
                #{result.vm_id}
              </td>
              <td rowSpan={findings.length} className="px-2 py-1.5 text-xs font-medium text-neutral-700 dark:text-neutral-300 align-top">
                {result.vm_name}
              </td>
              <td rowSpan={findings.length} className="px-2 py-1.5 text-xs text-neutral-600 dark:text-neutral-400 truncate max-w-[140px] align-top">
                {owner?.name ?? <span className="font-mono text-[10px] text-neutral-400">{result.owner_id}</span>}
              </td>
            </>
          )}
          <td className="px-2 py-1.5 text-xs font-mono text-neutral-600 dark:text-neutral-400">{finding.ip}</td>
          <FindingCells finding={finding} />
          {i === 0 && (
            <td rowSpan={findings.length} className="px-2 py-1.5 text-[10px] text-neutral-400 dark:text-neutral-500 whitespace-nowrap align-top">
              {formatDate(result.scanned_at)}
            </td>
          )}
        </tr>
      ))}
    </>
  )
}

export default function SecurityTab({ userLookup }: { userLookup: UserLookup }) {
  const { data, loading, error, refresh } = useSecurityScans()
  const [triggering, setTriggering] = useState(false)

  async function triggerScan() {
    setTriggering(true)
    try {
      await apiFetch('/api/admin/security/scan', { method: 'POST' })
      setTimeout(refresh, 2000)
    } finally {
      setTriggering(false)
    }
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <p className="text-sm text-red-500">{error}</p>
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-xs font-semibold cursor-pointer">
          <RefreshCw size={12} /> Réessayer
        </button>
      </div>
    )
  }

  const totalCritical = data.reduce((acc, r) => acc + r.findings.reduce((a, f) => a + f.cves.length, 0), 0)

  return (
    <div className="flex flex-col gap-3 h-full min-h-0">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-blue-400" />
          <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">Sécurité</h1>
          {!loading && (
            <span className="text-xs text-neutral-400 dark:text-neutral-500">
              ({data.length} VMs
              {totalCritical > 0 && <span className="text-red-500"> · {totalCritical} CVEs critiques</span>}
              )
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={triggerScan} disabled={triggering}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 disabled:opacity-50 text-white dark:text-neutral-900 text-xs font-semibold transition-colors cursor-pointer">
            {triggering ? <Loader size={12} className="animate-spin" /> : <Zap size={12} />}
            Scanner maintenant
          </button>
          <button onClick={refresh}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-medium transition-colors cursor-pointer">
            <RefreshCw size={12} /> Actualiser
          </button>
        </div>
      </div>

      <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm flex flex-col min-h-0 flex-1">
        <div className="overflow-x-auto overflow-y-auto flex-1">
        <table className="w-full text-sm border-collapse min-w-[1100px]">
          <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 sticky top-0 z-10">
            <tr>
              {[
                'ID', 'Nom', 'Propriétaire', 'IP',
                <span className="flex items-center gap-1"><Globe size={10} /> DNS</span>,
                <span className="flex items-center gap-1"><Plug size={10} /> Ports</span>,
                <span className="flex items-center gap-1"><Package size={10} /> CPEs</span>,
                <span className="flex items-center gap-1"><ShieldAlert size={10} /> Sévérité</span>,
                <span className="flex items-center gap-1"><ShieldAlert size={10} /> CVEs</span>,
                'Scan'
              ].map((col, i) => (
                <th key={i} className="px-2 py-2 text-left text-[10px] font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {loading && (
              <tr><td colSpan={10} className="px-4 py-10 text-center"><Loader size={14} className="animate-spin inline text-neutral-400" /></td></tr>
            )}
            {!loading && data.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-10 text-center text-neutral-400 text-xs">Aucun scan disponible</td></tr>
            )}
            {!loading && data.map(result => <ScanRows key={result.vm_id} result={result} userLookup={userLookup} />)}

          </tbody>
        </table>
        </div>
      </div>
    </div>
  )
}
