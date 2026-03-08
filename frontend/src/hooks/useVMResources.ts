import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { type VMDetail } from '../types/vm'

type Resources = { remaining: { cpu_cores: number; ram_mb: number; disk_gb: number } } | null

export function useVMResources(
  vmId: string | undefined,
  vm: VMDetail | null,
  resources: Resources,
  onSaved: (updated: Pick<VMDetail, 'cpu_cores' | 'ram_mb' | 'disk_gb'>) => void,
) {
  const [resModalOpen, setResModalOpen] = useState(false)
  const [newCpu, setNewCpu] = useState(1)
  const [newRam, setNewRam] = useState(1)
  const [newDisk, setNewDisk] = useState(10)
  const [resSaving, setResSaving] = useState(false)

  useEffect(() => {
    if (!vm) return
    setNewCpu(vm.cpu_cores)
    setNewRam(Math.round(vm.ram_mb / 1024))
    setNewDisk(vm.disk_gb)
  }, [vm?.vm_id])

  async function doSaveResources() {
    if (!vmId || resSaving || !vm) return
    setResSaving(true)
    try {
      await apiFetch(`/api/vms/${vmId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cpu_cores: newCpu, ram_gb: newRam, disk_gb: newDisk }),
      })
      onSaved({ cpu_cores: newCpu, ram_mb: newRam * 1024, disk_gb: newDisk })
      setResModalOpen(false)
    } catch { /* ignore */ }
    setResSaving(false)
  }

  const maxCpu  = vm ? vm.cpu_cores  + (resources?.remaining.cpu_cores ?? 0) : 1
  const maxRam  = vm ? Math.round(vm.ram_mb / 1024) + Math.round((resources?.remaining.ram_mb ?? 0) / 1024) : 1
  const maxDisk = vm ? vm.disk_gb + (resources?.remaining.disk_gb ?? 0) : 10

  return {
    resModalOpen, setResModalOpen,
    newCpu, setNewCpu,
    newRam, setNewRam,
    newDisk, setNewDisk,
    resSaving, doSaveResources,
    maxCpu, maxRam, maxDisk,
  }
}
