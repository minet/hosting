export interface VMDetail {
  vm_id: number
  username?: string | null
  ssh_public_key?: string | null
  name: string
  cpu_cores: number
  ram_mb: number
  disk_gb: number
  template: { template_id: number; name: string; is_active: boolean }
  network: { ipv4: string | null; ipv6: string | null; mac: string | null }
  current_user_role: 'owner' | 'shared' | 'admin'
  dns: string | null
  pending_changes: string[] | null
}

export interface VMTask {
  upid: string | null
  type: string | null
  status: string | null
  exitstatus: string | null
  starttime: number | null
  endtime: number | null
}

export type VMRequest = {
  id: number
  type: string
  dns_label: string | null
  status: string
  created_at: string
}
