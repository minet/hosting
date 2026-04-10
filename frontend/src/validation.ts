const VM_NAME_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/
const USERNAME_RE = /^[a-z_][a-z0-9_-]*$/
const SSH_KEY_RE = /^(ssh-(rsa|ed25519)|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/]{43,}={0,3}(\s+\S.*)?$/
const DNS_LABEL_RE = /^[a-z0-9][a-z0-9-]{0,61}([a-z0-9])?$/

export function validateVmName(v: string): string | null {
  if (!v.trim()) return 'Le nom est requis'
  if (v.length > 64) return 'Le nom ne doit pas dépasser 64 caractères'
  if (!VM_NAME_RE.test(v)) return 'Caractères autorisés : lettres, chiffres, points, tirets, underscores (doit commencer par alphanumérique)'
  return null
}

export function validateUsername(v: string): string | null {
  if (!v.trim()) return "Le nom d'utilisateur est requis"
  if (v.length > 64) return "Le nom d'utilisateur ne doit pas dépasser 64 caractères"
  if (!USERNAME_RE.test(v)) return 'Caractères autorisés : minuscules, chiffres, tirets, underscores (doit commencer par une lettre ou _)'
  return null
}

export function validateSshKey(v: string, required: boolean): string | null {
  const trimmed = v.trim()
  if (!trimmed) return required ? 'La clé SSH est requise' : null
  if (!SSH_KEY_RE.test(trimmed)) return 'Format invalide (attendu : ssh-ed25519, ssh-rsa, ecdsa-sha2-...)'
  return null
}

export function validateDnsLabel(v: string): string | null {
  if (!v.trim()) return 'Le sous-domaine est requis'
  if (!DNS_LABEL_RE.test(v)) return 'Caractères autorisés : minuscules, chiffres, tirets (doit commencer et finir par alphanumérique)'
  return null
}
