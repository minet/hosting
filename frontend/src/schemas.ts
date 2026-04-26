/**
 * Zod schemas for API response validation.
 *
 * Mirrors the backend Pydantic models. Any shape mismatch between backend
 * and frontend is caught at fetch time with a clear ZodError rather than
 * silently producing undefined behaviour deeper in the component tree.
 */
import { z } from 'zod'

// ─── Auth ────────────────────────────────────────────────────────────────────

export const MeSchema = z.object({
  sub: z.string().nullable(),
  user_id: z.string().nullable(),
  username: z.string().nullable(),
  email: z.string().nullable(),
  nom: z.string().nullable(),
  prenom: z.string().nullable(),
  departure_date: z.string().nullable(),
  groups: z.array(z.string()),
  is_admin: z.boolean(),
  cotise_end_ms: z.number().nullable(),
  date_signed_hosting: z.string().nullable(),
  ldap_login: z.string().nullable().optional(),
  maintenance: z.boolean().optional(),
  permanent: z.boolean().optional(),
  wifi_only: z.boolean().optional(),
})

export type Me = z.infer<typeof MeSchema>

// ─── Resources ───────────────────────────────────────────────────────────────

const ResourceLimitsSchema = z.object({
  cpu_cores: z.number(),
  ram_mb: z.number(),
  disk_gb: z.number(),
})

export const ResourcesSchema = z.object({
  usage: z.object({
    vm_count: z.number(),
    cpu_cores: z.number(),
    ram_mb: z.number(),
    disk_gb: z.number(),
  }),
  limits: ResourceLimitsSchema,
  remaining: ResourceLimitsSchema,
  minimums: ResourceLimitsSchema.nullable().optional(),
})

export type Resources = z.infer<typeof ResourcesSchema>

// ─── Templates ───────────────────────────────────────────────────────────────

export const TemplateSchema = z.object({
  template_id: z.number(),
  name: z.string(),
  version: z.string().nullable().optional(),
  min_cpu_cores: z.number().optional().default(1),
  min_ram_gb: z.number().optional().default(2),
  min_disk_gb: z.number().optional().default(10),
  comment: z.string().nullable().optional(),
})

export const TemplateListSchema = z.object({
  items: z.array(TemplateSchema),
  count: z.number().optional(),
})

// ─── VMs ─────────────────────────────────────────────────────────────────────

const VMRoleSchema = z.enum(['owner', 'shared', 'admin'])

export const VMListItemSchema = z.object({
  vm_id: z.number(),
  name: z.string(),
  role: VMRoleSchema,
  cpu_cores: z.number().optional(),
  ram_mb: z.number().optional(),
  disk_gb: z.number().optional(),
  template_id: z.number().optional(),
  template_name: z.string().optional(),
  ipv4: z.string().nullable().optional(),
  ipv6: z.string().nullable().optional(),
  mac: z.string().nullable().optional(),
  owner_id: z.string().nullable().optional(),
  dns: z.string().nullable().optional(),
})

export const VMListSchema = z.object({
  items: z.array(VMListItemSchema),
  count: z.number().optional(),
})

export const VMDetailSchema = z.object({
  vm_id: z.number(),
  name: z.string(),
  cpu_cores: z.number(),
  ram_mb: z.number(),
  disk_gb: z.number(),
  template: z.object({
    template_id: z.number(),
    name: z.string(),
  }),
  network: z.object({
    ipv4: z.string().nullable(),
    ipv6: z.string().nullable(),
    mac: z.string().nullable(),
  }),
  current_user_role: VMRoleSchema,
  username: z.string().nullable().optional(),
  ssh_public_key: z.string().nullable().optional(),
})

export type VMDetail = z.infer<typeof VMDetailSchema>

// ─── Requests ────────────────────────────────────────────────────────────────

export const VMRequestSchema = z.object({
  id: z.number(),
  vm_id: z.number(),
  user_id: z.string(),
  type: z.enum(['ipv4', 'dns']),
  dns_label: z.string().nullable().optional(),
  status: z.enum(['pending', 'approved', 'rejected']),
  created_at: z.string(),
  vm_name: z.string().nullable().optional(),
})

export const VMRequestListSchema = z.object({
  items: z.array(VMRequestSchema),
  count: z.number().optional(),
})

// ─── Access ───────────────────────────────────────────────────────────────────

export const VMAccessListSchema = z.object({
  vm_id: z.number().optional(),
  users: z.array(z.object({
    user_id: z.string(),
    role: VMRoleSchema,
  })),
  count: z.number().optional(),
})
