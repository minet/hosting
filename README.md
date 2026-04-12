<div align="center">
  <img src="frontend/public/assets/logo/logo_hosting_dark.png" alt="Hosting MiNET" width="320" />

  Portail self-service d'hébergement de machines virtuelles pour les membres de [MiNET](https://minet.net).

  [![license](https://img.shields.io/badge/licence-MIT-green)](LICENSE)
</div>

**Backend**
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Keycloak](https://img.shields.io/badge/Keycloak-26-4D4D4D?logo=keycloak&logoColor=white)

**Frontend**
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)

**Infra**
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-VE-E57000?logo=proxmox&logoColor=white)
![PowerDNS](https://img.shields.io/badge/PowerDNS-Authoritative-informational)

> **Screenshots à venir**


---

## Stack

| Composant  | Techno                        |
|------------|-------------------------------|
| Backend    | Python 3.12 · FastAPI · Alembic |
| Frontend   | React · TypeScript · Vite     |
| Auth       | Keycloak 26                   |
| DNS        | PowerDNS (gpgsql)             |
| Hyperviseur| Proxmox                       |
| Base de données | PostgreSQL 16            |
| Orchestration | Docker Compose             |

---

## Lancer en local

### Prérequis

- Docker + Docker Compose
- Make
- Accès à un Proxmox (optionnel pour le dev — les routes VM fonctionneront pas sans)

### Démarrage

```bash
# 1. Copier le fichier d'environnement
make env

# 2. Remplir les variables obligatoires dans .env
#    (voir section Variables d'environnement ci-dessous)

# 3. Démarrer tous les services
make up

# 4. Appliquer les migrations de base de données
make db-migrate
```

L'app est accessible sur :
- Frontend : http://localhost:5173
- Backend (API) : http://localhost:8000
- Keycloak : http://localhost:8080

### Keycloak local — comptes de test

Le realm `hosting-dev` est importé automatiquement au démarrage de Keycloak.
Les comptes suivants sont disponibles sans configuration supplémentaire :

| Utilisateur      | Mot de passe     | Groupes                  | Cas testé                        |
|------------------|------------------|--------------------------|----------------------------------|
| `admin`          | `admin`          | `cluster-dev` + `admin`  | Administrateur, cotisation active |
| `user`           | `user`           | `cluster-dev`            | Membre normal, cotisation active  |
| `newuser`        | `newuser`        | `cluster-dev`            | Membre sans charte signée         |
| `expired`        | `expired`        | `cluster-dev`            | Cotisation expirée                |
| `recently_expired` | `recently_expired` | `cluster-dev`        | Cotisation expirée récemment      |
| `outsider`       | `outsider`       | *(aucun)*                | Utilisateur hors asso             |

Pour se connecter, cliquer sur **Se connecter** sur le frontend — la redirection vers Keycloak est automatique.

### Variables d'environnement

Les variables avec une valeur par défaut fonctionnent directement en dev.
Celles sans valeur par défaut sont obligatoires pour certaines fonctionnalités.

| Variable                  | Défaut dev                          | Description                              |
|---------------------------|-------------------------------------|------------------------------------------|
| `POSTGRES_DB`             | `hosting`                           |                                          |
| `POSTGRES_USER`           | `app`                               |                                          |
| `POSTGRES_PASSWORD`       | `devpassword`                       |                                          |
| `SESSION_SECRET`          | `dev-session-secret-change-me-in-prod` | Secret de session — **changer en prod** |
| `PROXMOX_TOKEN_ID`        | —                                   | Token API Proxmox (optionnel en dev)     |
| `PROXMOX_TOKEN_SECRET`    | —                                   | Secret du token Proxmox                  |
| `PDNS_API_KEY`            | `devkey`                            |                                          |
| `DNS_ZONE`                | `h.lan`                             | Zone DNS gérée par PowerDNS              |

---

## Commandes utiles

```bash
make up            # Démarrer tous les services
make down          # Arrêter tous les services
make logs          # Suivre les logs (tous les services)
make logs-back     # Logs backend uniquement
make logs-front    # Logs frontend uniquement

make db-migrate    # Appliquer les migrations Alembic
make db-revision MSG="description"  # Créer une nouvelle migration

make api-types     # Regénérer les types TypeScript depuis l'OpenAPI du backend

make back-lint     # Linter le backend (ruff)
make back-format   # Formatter le backend (ruff)
make front-lint    # Linter le frontend (eslint)

make help          # Lister toutes les commandes disponibles
```

---

## Signaler un bug ou demander une fonctionnalité

Les issues sont ouvertes :

Pour une demande de fonctionnalité, ouvrir une issue avec le label `feature` en décrivant :
- Le besoin (contexte, pourquoi c'est utile)
- Le comportement attendu
- Éventuellement une proposition d'implémentation

---

## Licence

Voir [LICENSE](LICENSE).
