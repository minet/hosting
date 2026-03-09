import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useToast } from '../contexts/ToastContext'
import { type VMDetail } from '../types/vm'
import { validateUsername, validateSshKey } from '../validation'

export function useVMCredentials(vmId: string | undefined, vm: VMDetail | null) {
  const { toast } = useToast()
  const [credUsername, setCredUsername] = useState('')
  const [credPassword, setCredPassword] = useState('')
  const [credSshKey, setCredSshKey] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [credSaving, setCredSaving] = useState(false)
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

  async function doSaveCreds() {
    if (!vmId || credSaving) return
    if (!validateCreds()) return
    setCredSaving(true)
    setCredSuccess(false)
    try {
      await apiFetch(`/api/vms/${vmId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource: {
            username: credUsername.trim(),
            password: credPassword || null,
            ssh_public_key: credSshKey.trim() || null,
          },
        }),
      })
      setCredSuccess(true)
      setCredErrors({})
      setTimeout(() => setCredSuccess(false), 3000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Échec de la sauvegarde des accès'
      toast(msg)
    }
    setCredSaving(false)
  }

  return {
    credUsername, setCredUsername,
    credPassword, setCredPassword,
    credSshKey, setCredSshKey,
    showPassword, setShowPassword,
    credSaving, credSuccess, credErrors,
    doSaveCreds,
  }
}
