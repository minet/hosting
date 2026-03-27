import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { type VMDetail } from '../types/vm'
import { validateUsername, validateSshKey } from '../validation'
import { useMutationWithToast } from './useMutationWithToast'

export function useVMCredentials(vmId: string | undefined, vm: VMDetail | null) {
  const [credUsername, setCredUsername] = useState('')
  const [credPassword, setCredPassword] = useState('')
  const [credSshKey, setCredSshKey] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [credSuccess, setCredSuccess] = useState(false)
  const [credErrors, setCredErrors] = useState<{ username?: string; sshKey?: string }>({})

  useEffect(() => {
    if (!vm) return
    if (vm.username) setCredUsername(vm.username)
    if (vm.ssh_public_key) setCredSshKey(vm.ssh_public_key)
  }, [vm?.vm_id])

  function validateCreds(): boolean {
    const errors: { username?: string; sshKey?: string } = {}
    const usernameErr = validateUsername(credUsername)
    if (usernameErr) errors.username = usernameErr
    const sshErr = validateSshKey(credSshKey, false)
    if (sshErr) errors.sshKey = sshErr
    setCredErrors(errors)
    return Object.keys(errors).length === 0
  }

  const saveMutation = useMutationWithToast({
    mutationFn: () =>
      apiFetch(`/api/vms/${vmId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource: {
            username: credUsername.trim(),
            password: credPassword || null,
            ssh_public_key: credSshKey.trim() || null,
          },
        }),
      }),
    invalidate: [['vms']],
    onSuccess: () => {
      setCredSuccess(true)
      setCredErrors({})
      setTimeout(() => setCredSuccess(false), 3000)
    },
    fallbackError: 'Échec de la sauvegarde des accès',
  })

  async function doSaveCreds() {
    if (!vmId || saveMutation.isPending) return
    if (!validateCreds()) return
    setCredSuccess(false)
    await saveMutation.mutateAsync().catch(() => {})
  }

  return {
    credUsername, setCredUsername,
    credPassword, setCredPassword,
    credSshKey, setCredSshKey,
    showPassword, setShowPassword,
    credSaving: saveMutation.isPending, credSuccess, credErrors,
    doSaveCreds,
  }
}
