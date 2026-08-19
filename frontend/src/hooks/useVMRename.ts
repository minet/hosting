import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { type VMDetail } from '../types/vm'
import { validateVmName } from '../validation'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMRename(
  vmId: string | undefined,
  vm: VMDetail | null,
  onRenamed: (newName: string) => void,
) {
  const { t } = useTranslation('vm')
  const [renameModalOpen, setRenameModalOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)

  useEffect(() => {
    if (vm) {
      setNewName(vm.name)
      setRenameError(null)
    }
  }, [vm?.vm_id, vm?.name, renameModalOpen])

  const renameMutation = useMutationWithToast({
    mutationFn: () =>
      apiFetch<{ vm_id: number; action: string; status: string; name?: string }>(`/api/vms/${vmId}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() }),
      }),
    invalidate: [['vms'], ['vm', vmId ?? '']],
    successMessage: t('rename.success'),
    onSuccess: () => {
      onRenamed(newName.trim())
      setRenameModalOpen(false)
      setRenameError(null)
    },
    fallbackError: 'Échec du renommage de la VM',
  })

  async function doRename() {
    if (!vmId || renameMutation.isPending || !vm) return
    const err = validateVmName(newName)
    if (err) {
      setRenameError(err)
      return
    }
    setRenameError(null)
    await renameMutation.mutateAsync().catch(() => {})
  }

  return {
    renameModalOpen,
    setRenameModalOpen,
    newName,
    setNewName,
    renameError,
    setRenameError,
    renameSaving: renameMutation.isPending,
    doRename,
  }
}
