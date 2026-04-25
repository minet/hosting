import { useState } from 'react'
import { Loader, RefreshCw, Shield, ShieldAlert, ChevronDown, ChevronRight, Zap } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api'

interface CveEntry {
  id: string
  score: number
  published: string
}

interface SecurityFinding {
  ip: string
  ports: number[]
  hostnames: string[]
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
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 9 ? 'bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800'
    : 'bg-orange-50 dark:bg-orange-950 text-orange-600 dark:text-orange-400 border-orange-200 dark:border-orange-800'
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold border ${color}`}>
      {score.toFixed(1)}
    </span>
  )
}

function FindingRow({ finding }: { finding: SecurityFinding }) {
  const hasCves = finding.cves.length > 0
  return (
    <div className="pl-4 py-2 border-l-2 border-neutral-200 dark:border-neutral-700">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-xs text-neutral-700 dark:text-neutral-300">{finding.ip}</span>
        {finding.hostnames.length > 0 && (
          <span className="text-xs text-neutral-400 dark:text-neutral-500">
            {finding.hostnames.join(', ')}
          </span>
        )}
        {finding.ports.length > 0 && (
          <span className="text-[10px] text-neutral-400 dark:text-neutral-500">
            ports: {finding.ports.join(', ')}
          </span>
        )}
      </div>
      {hasCves && (
        <div className="mt-1.5 flex flex-col gap-1">
          {finding.cves.map(cve => (
            <div key={cve.id} className="flex items-center gap-2">
              <ScoreBadge score={cve.score} />
              <a
                href={`https://cve.mitre.org/cgi-bin/cvename.cgi?name=${cve.id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-mono text-blue-600 dark:text-blue-400 hover:underline"
              >
                {cve.id}
              </a>
              <span className="text-[10px] text-neutral-400 dark:text-neutral-500">{cve.published}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ScanRow({ result }: { result: SecurityScanResult }) {
  const [expanded, setExpanded] = useState(false)
  const totalCves = result.findings.reduce((acc, f) => acc + f.cves.length, 0)
  const hasFindings = result.findings.length > 0

  return (
    <>
      <tr
        className={`hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors ${hasFindings ? 'cursor-pointer' : ''}`}
        onClick={() => hasFindings && setExpanded(v => !v)}
      >
        <td className="px-3 py-2 text-xs font-mono text-neutral-500 dark:text-neutral-400">#{result.vm_id}</td>
        <td className="px-3 py-2 text-xs text-neutral-700 dark:text-neutral-300 font-medium">{result.vm_name}</td>
        <td className="px-3 py-2 text-xs font-mono text-neutral-500 dark:text-neutral-400 truncate max-w-[180px]">{result.owner_id}</td>
        <td className="px-3 py-2 text-xs font-mono text-neutral-600 dark:text-neutral-400">{result.ipv4 ?? '—'}</td>
        <td className="px-3 py-2 text-xs font-mono text-neutral-400 dark:text-neutral-500 truncate max-w-[160px]">{result.ipv6 ?? '—'}</td>
        <td className="px-3 py-2 text-xs text-neutral-500 dark:text-neutral-400">{formatDate(result.scanned_at)}</td>
        <td className="px-3 py-2">
          {totalCves > 0 ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800">
              <ShieldAlert size={10} /> {totalCves} CVE{totalCves > 1 ? 's' : ''}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
              <Shield size={10} /> OK
            </span>
          )}
        </td>
        <td className="px-3 py-2 text-xs text-neutral-400">
          {hasFindings && (expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />)}
        </td>
      </tr>
      {expanded && hasFindings && (
        <tr className="bg-neutral-50 dark:bg-neutral-800/50">
          <td colSpan={8} className="px-4 py-3">
            <div className="flex flex-col gap-2">
              {result.findings.map(f => <FindingRow key={f.ip} finding={f} />)}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function SecurityTab() {
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
        <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 text-white dark:text-neutral-900 text-xs font-semibold transition-colors cursor-pointer">
          <RefreshCw size={12} /> Réessayer
        </button>
      </div>
    )
  }

  const totalCritical = data.reduce((acc, r) => acc + r.findings.reduce((a, f) => a + f.cves.length, 0), 0)

  return (
    <div className="flex flex-col gap-4 h-full overflow-auto">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-blue-400" />
          <h1 className="text-base font-semibold text-neutral-800 dark:text-neutral-200">Sécurité</h1>
          {!loading && (
            <span className="text-xs text-neutral-400 dark:text-neutral-500">
              ({data.length} VMs
              {totalCritical > 0 && <span className="text-red-500 dark:text-red-400"> · {totalCritical} CVE{totalCritical > 1 ? 's' : ''} critiques</span>}
              )
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={triggerScan}
            disabled={triggering}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-700 dark:hover:bg-neutral-300 disabled:opacity-50 text-white dark:text-neutral-900 text-xs font-semibold transition-colors cursor-pointer"
          >
            {triggering ? <Loader size={12} className="animate-spin" /> : <Zap size={12} />}
            Scanner maintenant
          </button>
          <button onClick={refresh} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs font-medium transition-colors cursor-pointer">
            <RefreshCw size={12} /> Actualiser
          </button>
        </div>
      </div>

      <div className="border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden shadow-sm overflow-x-auto shrink-0">
        <table className="w-full text-sm border-collapse min-w-[960px]">
          <thead className="bg-neutral-50 dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700">
            <tr>
              {['VM ID', 'Nom', 'Propriétaire', 'IPv4', 'IPv6', 'Dernier scan', 'Statut', ''].map(col => (
                <th key={col} className="px-3 py-2 text-left text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-neutral-900 divide-y divide-neutral-100 dark:divide-neutral-800">
            {loading && (
              <tr><td colSpan={8} className="px-4 py-10 text-center"><Loader size={14} className="animate-spin inline text-neutral-400" /></td></tr>
            )}
            {!loading && data.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-neutral-400 dark:text-neutral-500 text-xs">Aucun scan disponible</td></tr>
            )}
            {!loading && data.map(result => <ScanRow key={result.vm_id} result={result} />)}
          </tbody>
        </table>
      </div>
    </div>
  )
}
