import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { type VMDetail } from '../types/vm'

export function useVMCredentials(vmId: string | undefined, vm: VMDetail | null) {
  const [credUsername, setCredUsername] = useState('')
  const [credPassword, setCredPassword] = useState('')
  const [credSshKey, setCredSshKey] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [credSaving, setCredSaving] = useState(false)
  const [credSuccess, setCredSuccess] = useState(false)

  useEffect(() => {
    if (!vm) return
    if (vm.username) setCredUsername(vm.username)
    if (vm.ssh_public_key) setCredSshKey(vm.ssh_public_key)
  }, [vm?.vm_id])

  async function doSaveCreds() {
    if (!vmId || !credUsername.trim() || credSaving) return
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
      setTimeout(() => setCredSuccess(false), 3000)
    } catch { /* ignore */ }
    setCredSaving(false)
  }

  return {
    credUsername, setCredUsername,
    credPassword, setCredPassword,
    credSshKey, setCredSshKey,
    showPassword, setShowPassword,
    credSaving, credSuccess,
    doSaveCreds,
  }
}
