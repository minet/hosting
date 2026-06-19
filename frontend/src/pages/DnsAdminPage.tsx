import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { useAdminRequests, type AdminRequest } from '../hooks/useAdminRequests'
import { RequestDialog } from '../components/admin/RequestBadge'
import ConfirmModal from '../components/ConfirmModal'

type DnsTab = 'pending' | 'approved'

/** Empty state: a faded sad penguin with the message underneath (no overlap). */
function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex-1 min-h-64 flex flex-col items-center justify-center gap-3">
      <img
        src="/assets/pinguins/PinguinTriste.svg"
        alt=""
        aria-hidden
        className="h-32 w-32 opacity-25 pointer-events-none select-none"
      />
      <span className="text-xs text-neutral-400 dark:text-neutral-500">{label}</span>
    </div>
  )
}

/**
 * Reduced admin page for "dev" validators (AUTH_DEV_GROUPS).
 *
 * Two tabs, DNS only: pending requests to validate/reject, and already-approved
 * DNS with a revoke action. No IP, owner, Proxmox or other admin data is
 * exposed; the backend additionally enforces DNS-only access for devs.
 */
export default function DnsAdminPage() {
  const { t } = useTranslation('admin')
  const tc = useTranslation().t
  const qc = useQueryClient()
  const { toast } = useToast()
  const { requests, updateRequest } = useAdminRequests()
  const [tab, setTab] = useState<DnsTab>('pending')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<AdminRequest | null>(null)
  // Request deep-linked from a Discord alert (#req-<id> or legacy #vm-<id>).
  const [hashRequest, setHashRequest] = useState<AdminRequest | null>(null)

  const pendingDns = useMemo(
    () => requests.filter((r): r is AdminRequest => r.status === 'pending' && r.type === 'dns'),
    [requests],
  )

  const { data: approvedDns = [] } = useQuery({
    queryKey: ['admin-dns-approved'],
    queryFn: async () => {
      const data = await apiFetch<{ items: AdminRequest[] }>('/api/dns')
      return data.items
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/dns/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-dns-approved'] }),
    onError: (err: Error) => toast(err.message ?? t('dns.revokeFailed', 'Échec de la révocation')),
  })

  // updateRequest only refreshes the pending list. Refresh the approved list too —
  // even on error, since the backend commits the DNS status before the
  // (best-effort) PowerDNS record creation.
  const runUpdate = useCallback(async (id: number, status: 'approved' | 'rejected') => {
    try {
      await updateRequest(id, status)
    } finally {
      qc.invalidateQueries({ queryKey: ['admin-dns-approved'] })
    }
  }, [updateRequest, qc])

  async function act(id: number, status: 'approved' | 'rejected') {
    setBusyId(id)
    try {
      await runUpdate(id, status)
    } finally {
      setBusyId(null)
    }
  }

  // Open the validation modal when arriving from a Discord deep-link. Re-runs
  // when requests load (data is async) and on hash changes.
  useEffect(() => {
    function resolveFromHash() {
      const hash = window.location.hash
      const reqMatch = hash.match(/^#req-(\d+)$/)
      const vmMatch = hash.match(/^#vm-(\d+)$/)
      if (reqMatch) {
        const found = pendingDns.find(r => r.id === Number(reqMatch[1]))
        if (found) setHashRequest(found)
      } else if (vmMatch) {
        const found = pendingDns.find(r => r.vm_id === Number(vmMatch[1]))
        if (found) setHashRequest(found)
      }
    }
    resolveFromHash()
    window.addEventListener('hashchange', resolveFromHash)
    return () => window.removeEventListener('hashchange', resolveFromHash)
  }, [pendingDns])

  const closeHashRequest = useCallback(() => {
    setHashRequest(null)
    history.replaceState(null, '', window.location.pathname + window.location.search)
  }, [])

  const tabs: { id: DnsTab; label: string; count: number }[] = [
    { id: 'pending', label: t('dns.pendingTab', 'Demandes'), count: pendingDns.length },
    { id: 'approved', label: t('dns.approvedTab', 'Déjà acceptées'), count: approvedDns.length },
  ]

  const btn = 'px-3 py-1 text-xs font-semibold rounded-md transition-colors disabled:opacity-50 cursor-pointer'

  return (
    <div className="flex flex-col gap-4 h-full w-full">
      <div className="shrink-0">
        <h1 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
          {t('dns.devTitle', 'Demandes DNS')}
        </h1>
        <div className="flex items-center gap-2 mt-3 border-b border-neutral-200 dark:border-neutral-700">
          {tabs.map((tb) => (
            <button
              key={tb.id}
              onClick={() => setTab(tb.id)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-t-md transition-colors -mb-px border-b-2 cursor-pointer ${
                tab === tb.id
                  ? 'border-neutral-900 dark:border-neutral-100 text-neutral-900 dark:text-neutral-100'
                  : 'border-transparent text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200'
              }`}
            >
              {tb.label}
              <span className="ml-1.5 font-mono text-neutral-400 dark:text-neutral-500">{tb.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {tab === 'pending' && (
          pendingDns.length === 0 ? (
            <EmptyState label={t('dns.emptyPending', 'Aucune demande DNS en attente.')} />
          ) : (
            <div className="rounded-md border border-neutral-200 dark:border-neutral-700 overflow-hidden shadow-sm">
              <table className="w-full text-sm border-collapse">
                <thead className="bg-neutral-50 dark:bg-neutral-800 text-xs uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold">{t('dns.dnsLabelCol', 'Label DNS')}</th>
                    <th className="px-4 py-2 text-left font-semibold">{t('dns.vmNameCol', 'Nom VM')}</th>
                    <th className="px-4 py-2 text-left font-semibold">{t('dns.createdAtCol', 'Créé le')}</th>
                    <th className="px-4 py-2 text-right font-semibold w-56" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800 bg-white dark:bg-neutral-900">
                  {pendingDns.map((r) => (
                    <tr key={r.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors">
                      <td className="px-4 py-2 font-mono text-neutral-900 dark:text-neutral-100">{r.dns_label ?? '—'}</td>
                      <td className="px-4 py-2 text-neutral-600 dark:text-neutral-400">
                        {r.vm_name ? `${r.vm_name} ` : ''}<span className="text-neutral-400 dark:text-neutral-500">#{r.vm_id}</span>
                      </td>
                      <td className="px-4 py-2 text-neutral-500 dark:text-neutral-400 text-xs">
                        {new Date(r.created_at).toLocaleString('fr-FR')}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            disabled={busyId !== null}
                            onClick={() => act(r.id, 'approved')}
                            className={`${btn} bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60 hover:bg-emerald-100 dark:hover:bg-emerald-900/40`}
                          >
                            {t('dns.approve', 'Valider')}
                          </button>
                          <button
                            disabled={busyId !== null}
                            onClick={() => act(r.id, 'rejected')}
                            className={`${btn} bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800/60 hover:bg-red-100 dark:hover:bg-red-900/40`}
                          >
                            {t('dns.reject', 'Refuser')}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}

        {tab === 'approved' && (
          approvedDns.length === 0 ? (
            <EmptyState label={t('dns.emptyApproved', 'Aucun DNS accepté pour l\'instant.')} />
          ) : (
            <div className="rounded-md border border-neutral-200 dark:border-neutral-700 overflow-hidden shadow-sm">
              <table className="w-full text-sm border-collapse">
                <thead className="bg-neutral-50 dark:bg-neutral-800 text-xs uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold">{t('dns.dnsLabelCol', 'Label DNS')}</th>
                    <th className="px-4 py-2 text-left font-semibold">{t('dns.vmNameCol', 'Nom VM')}</th>
                    <th className="px-4 py-2 text-left font-semibold">{t('dns.createdAtCol', 'Créé le')}</th>
                    <th className="px-4 py-2 text-right font-semibold w-32" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800 bg-white dark:bg-neutral-900">
                  {approvedDns.map((r) => (
                    <tr key={r.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors">
                      <td className="px-4 py-2 font-mono text-neutral-900 dark:text-neutral-100">{r.dns_label ?? '—'}</td>
                      <td className="px-4 py-2 text-neutral-600 dark:text-neutral-400">
                        {r.vm_name ? `${r.vm_name} ` : ''}<span className="text-neutral-400 dark:text-neutral-500">#{r.vm_id}</span>
                      </td>
                      <td className="px-4 py-2 text-neutral-500 dark:text-neutral-400 text-xs">
                        {new Date(r.created_at).toLocaleString('fr-FR')}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <button
                          disabled={revokeMutation.isPending}
                          onClick={() => setRevokeTarget(r)}
                          className={`${btn} bg-neutral-100 dark:bg-neutral-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950 border border-neutral-200 dark:border-neutral-700`}
                        >
                          {t('dns.revoke', 'Révoquer')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>

      {hashRequest && (
        <RequestDialog request={hashRequest} onClose={closeHashRequest} onUpdate={runUpdate} />
      )}

      {revokeTarget && (
        <ConfirmModal
          title={t('dns.revoke', 'Révoquer')}
          confirmLabel={t('dns.revoke', 'Révoquer')}
          cancelLabel={tc('cancel')}
          danger
          loading={revokeMutation.isPending}
          onConfirm={async () => {
            await revokeMutation.mutateAsync(revokeTarget.id)
            setRevokeTarget(null)
          }}
          onClose={() => setRevokeTarget(null)}
        >
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            {t('dns.revokeConfirm', { label: revokeTarget.dns_label ?? '', defaultValue: 'Révoquer le DNS {{label}} ? Le CNAME sera supprimé.' })}
          </p>
        </ConfirmModal>
      )}
    </div>
  )
}
