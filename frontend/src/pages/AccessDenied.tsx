import { logoutUrl } from '../api'

export default function AccessDenied() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '1rem', fontFamily: 'sans-serif' }}>
      <img src="/assets/pinguins/PinguinPerdu.svg" alt="Pingouin perdu" width={200} height={200} />
      <h1 style={{ fontSize: '2rem', fontWeight: 700 }}>Accès refusé</h1>
      <p style={{ color: '#666', textAlign: 'center', maxWidth: 400 }}>
        Vous tentez d'accéder à une instance de pré-production du service d'hébergement.
        Votre compte ne dispose pas des droits nécessaires pour y accéder.
      </p>
      <a href={logoutUrl()} style={{ marginTop: '0.5rem', padding: '0.5rem 1.5rem', background: '#111', color: '#fff', borderRadius: '6px', textDecoration: 'none', fontWeight: 600 }}>
        Se déconnecter
      </a>
    </div>
  )
}
