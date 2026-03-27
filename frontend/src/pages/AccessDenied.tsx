import { logoutUrl } from '../api'

interface Props {
  reason?: 'preprod' | 'restricted'
}

export default function AccessDenied({ reason = 'preprod' }: Props) {
  const message = reason === 'restricted'
    ? 'Seuls les comptes LDAP avec un accès production peuvent accéder à ce service.'
    : "Vous tentez d'accéder à une instance de pré-production du service d'hébergement. Votre compte ne dispose pas des droits nécessaires pour y accéder."

  return (
    <div className="flex flex-col items-center justify-center h-screen gap-4 font-sans bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100">
      <img src="/assets/pinguins/PinguinPerdu.svg" alt="Pingouin perdu" width={200} height={200} />
      <h1 className="text-3xl font-bold">Accès refusé</h1>
      <p className="text-neutral-500 dark:text-neutral-400 text-center max-w-[400px]">
        {message}
      </p>
      <a href={logoutUrl()} className="mt-2 px-6 py-2 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-md font-semibold no-underline hover:bg-neutral-700 dark:hover:bg-neutral-300 transition-colors">
        Se déconnecter
      </a>
    </div>
  )
}
