# Pastanetwork Looking Glass

Un Looking Glass est une page de diagnostic réseau publique. Ce projet permet à
n'importe quel visiteur de lancer un ping, un traceroute ou un MTR depuis le réseau de
Pastanetwork vers l'adresse de son choix, et d'en suivre le résultat en direct.

Tout tient dans une seule image Docker (l'application et son Redis interne), à placer
derrière votre reverse proxy. Pas de compte, pas de service externe à gérer.

<p align="center">
  <img src=".github/assets/home.png" alt="Page d'accueil du Looking Glass" width="820">
</p>

## Fonctionnalités

- ping, traceroute et MTR, en IPv4 comme en IPv6
- résultat diffusé ligne par ligne (Server-Sent Events), comme dans un terminal
- journal des requêtes en SQLite et page de statistiques
- interface française et anglaise, thème clair et sombre
- fichiers de test de débit en option, désactivés par défaut

L'architecture sépare l'outil du nœud qui l'exécute. Un seul nœud aujourd'hui, mais
ajouter des points de présence distants ne demandera pas de tout réécrire.

## Aperçu

Chaque résultat se consulte de deux façons : une **vue visuelle** synthétique ou la
**console brute**, telle que la commande la produit.

### Ping

| Vue visuelle | Console |
|---|---|
| ![Ping — vue visuelle](.github/assets/ping-visuel.png) | ![Ping — console](.github/assets/ping-console.png) |

### Traceroute

| Vue visuelle | Console |
|---|---|
| ![Traceroute — vue visuelle](.github/assets/traceroute-visuel.png) | ![Traceroute — console](.github/assets/traceroute-console.png) |

### Test de débit

| Lancement | Résultat |
|---|---|
| ![Test de débit](.github/assets/debit.png) | ![Test de débit — résultat](.github/assets/debit-info.png) |

### Statistiques

| Chiffres clés et activité | Répartitions et débit | Requêtes récentes |
|---|---|---|
| ![Statistiques — chiffres clés](.github/assets/stats.png) | ![Statistiques — répartitions](.github/assets/stats-2.png) | ![Statistiques — requêtes récentes](.github/assets/stats-3.png) |

## Installation avec Docker

### Prérequis
- Docker
- Une paire de clés [Cloudflare Turnstile][turnstile], gratuites. La vérification
  anti-robot est **obligatoire en production** : sans ces clés, l'application refuse
  de démarrer.

### Mise en route rapide

```bash
cp .env.example .env
# Renseignez au minimum TURNSTILE_SITE_KEY et TURNSTILE_SECRET_KEY dans .env.

python lg.py build      # construit l'image Docker (looking-glass:local)
python lg.py run        # lance le conteneur sur le port 8080
```

`python lg.py run` est pratique pour un essai, mais lance le conteneur avec `--rm` et
**sans volume de données** : le journal des requêtes et le sel de hachage sont perdus à
l'arrêt. Pour une mise en production, préférez un `docker run` explicite (ci-dessous).

### Lancement en production

```bash
docker build -f deploy/Dockerfile -t looking-glass:local .

docker run -d --name looking-glass \
  -p 8080:8080 \
  --cap-drop ALL --cap-add NET_RAW \
  --env-file .env \
  -e DEV=False \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/config:/config:ro" \
  looking-glass:local
```

Points importants :

- `--cap-drop ALL --cap-add NET_RAW` : le conteneur tourne sans privilège, avec la seule
  capability nécessaire aux sockets ICMP. Le processus applicatif n'est pas root.
- `-v ./data:/app/data` : **persiste** la base SQLite (`looking_glass.db`) et le sel
  `.ip_hash_salt`. Sans ce volume, le journal et le sel repartent de zéro à chaque
  redémarrage.
- `-v ./config:/config:ro` : monte le `config.json` optionnel (voir plus bas). À omettre
  si vous n'en utilisez pas.
- `-e DEV=False` : l'image ne contient que les assets minifiés ; le mode développement
  n'y a pas de sens. `python lg.py run` force d'ailleurs cette valeur.

Un fichier `deploy/compose.yaml` est également fourni pour un déploiement via Docker
Compose (ou un gestionnaire de stacks comme Dockge), avec volumes nommés et capabilities
déjà configurés.

L'application écoute sur le port 8080. Le conteneur embarque son propre Redis, aucun
service externe n'est requis. Un endpoint `/api/v1/health` est exposé pour la
surveillance (et utilisé par le `HEALTHCHECK` Docker).

### Reverse proxy

Mettez votre reverse proxy devant le conteneur. Un exemple de vhost nginx est fourni
dans `deploy/nginx.conf.example`. Le **buffering doit être désactivé** sur les routes
`/api/v1/run` (streaming SSE) et `/api/v1/speedtest` (mesure de débit fidèle), et le
reverse proxy doit transmettre l'en-tête `X-Real-IP` (voir `TRUSTED_PROXY_HOSTS`).

[turnstile]: https://dash.cloudflare.com/?to=/:account/turnstile

## Configuration

La configuration provient de trois couches, appliquées dans cet ordre :

1. les **valeurs par défaut** intégrées au code
2. le fichier **`config.json`** optionnel, qui se superpose aux défauts
3. les **variables d'environnement**, qui priment sur tout le reste

Les clés Turnstile sont les seules valeurs obligatoires. `IP_HASH_SALT` et
`REDIS_PASSWORD` sont générés automatiquement s'ils sont absents.

### Variables d'environnement (`.env`)

Copiez `.env.example` en `.env`. Toutes les variables y sont commentées dans le
fichier. En voici le détail.

#### Général

| Variable | Défaut | Rôle |
|---|---|---|
| `DEV` | `False` | Mode développement (reload, bypass Turnstile possible). Laisser `False` en production. `python lg.py dev` l'active localement, `python lg.py run` force `False`. |
| `LG_CONFIG_FILE` | `/config/config.json` | Chemin du fichier `config.json` structuré. |

#### Serveur HTTP

| Variable | Défaut | Rôle |
|---|---|---|
| `LG_HOST` | `0.0.0.0` | Interface d'écoute de l'application. |
| `LG_PORT` | `8080` | Port d'écoute interne au conteneur. |
| `LG_WORKERS` | `4` | Nombre de workers Hypercorn. |
| `LG_PUBLIC_URL` | *(vide)* | URL publique canonique, utilisée pour le SEO et les balises des templates. Laisser vide en local. |
| `LG_DB_PATH` | `data/looking_glass.db` | Chemin de la base SQLite. À conserver dans le volume `/app/data`. |
| `TRUSTED_PROXY_HOSTS` | `127.0.0.1` | Hôtes (séparés par des virgules) autorisés à réécrire l'IP cliente via l'en-tête `X-Real-IP`. Mettez-y l'IP de votre reverse proxy. |
| `ALLOWED_HOSTS` | *(vide)* | Noms d'hôte acceptés dans l'en-tête `Host` (séparés par des virgules, motif `*.domaine` autorisé). Vide = tout accepter. Les hôtes loopback restent toujours acceptés. |

#### CORS

| Variable | Défaut | Rôle |
|---|---|---|
| `CORS_ALLOW_ORIGIN` | *(vide)* | Origines autorisées en CORS (séparées par des virgules, ex. `https://exemple.com`). Vide = same-origin uniquement : l'API n'est consommée que par le frontend du Looking Glass. |

Les autres réglages CORS (méthodes, en-têtes autorisés et exposés, `max-age`) se font
dans le fichier `config.json`, section `cors`.

#### Redis (interne au conteneur, éphémère)

| Variable | Défaut | Rôle |
|---|---|---|
| `REDIS_HOST` | `127.0.0.1` | Hôte Redis. |
| `REDIS_PORT` | `6379` | Port Redis. |
| `REDIS_PASSWORD` | *(auto)* | Mot de passe Redis. Généré automatiquement par l'entrypoint Docker si vide. |

#### Sécurité

| Variable | Défaut | Rôle |
|---|---|---|
| `IP_HASH_SALT` | *(auto)* | Sel de hachage SHA-256 des IP sources. Auto-généré puis persisté dans `data/.ip_hash_salt` s'il est absent. Renseignez-le pour un sel stable et explicite. |
| `TURNSTILE_SITE_KEY` | *(requis)* | Clé publique Cloudflare Turnstile. |
| `TURNSTILE_SECRET_KEY` | *(requis)* | Clé secrète Cloudflare Turnstile. |
| `TURNSTILE_DEV_BYPASS` | `False` | Court-circuite la vérification Turnstile. Sans effet sauf si `DEV=True`. |

#### Plafonds de concurrence (anti-abus)

| Variable | Défaut | Rôle |
|---|---|---|
| `GLOBAL_COMMAND_CAP` | `8` | Nombre maximum de commandes simultanées, tous clients confondus. |
| `PER_IP_COMMAND_CAP` | `2` | Nombre maximum de commandes simultanées par IP cliente. |

#### Speedtest (test de débit, désactivé par défaut)

Fonctionnalité opt-in. Les valeurs livrées dans `.env.example` sont des garde-fous
sûrs : si vous l'activez, le speedtest ne pourra pas faire déraper une facturation
transit au 95e centile ni votre volume mensuel.

| Variable | Défaut | Rôle |
|---|---|---|
| `SPEEDTEST_ENABLED` | `False` | Active la fonctionnalité de test de débit. |
| `SPEEDTEST_DAILY_BYTE_BUDGET` | `0` (illimité) | Volume total servi par jour, tous clients confondus. Une fois atteint, le speedtest est coupé jusqu'au lendemain — c'est LE garde-fou. `.env.example` propose `805306368000` (750 Gio/jour). |
| `SPEEDTEST_PER_IP_BYTE_BUDGET` | `0` (illimité) | Volume servi par IP et par jour. `.env.example` propose `32212254720` (30 Gio/jour). |
| `SPEEDTEST_MAX_KBPS` | `0` (non bridé) | Débit maximum par connexion, en kilo-octets/s. `0` laisse le client voir le vrai débit du lien. |
| `SPEEDTEST_CONCURRENCY` | `2` | Nombre de téléchargements speedtest simultanés, tous clients confondus. |

#### Divers

| Variable | Défaut | Rôle |
|---|---|---|
| `QUERY_LOG_RETENTION_DAYS` | `90` | Rétention du journal des requêtes, en jours. |
| `DEFAULT_LANGUAGE` | `fr` | Langue par défaut de l'interface (`fr`, `en`). |

### Fichier `config.json` (optionnel)

Ce qui est structuré ne se prête pas à des variables d'environnement : liste des nœuds,
listes d'autorisation et de blocage des cibles, plafonds par outil, fichiers de test de
débit. Tout cela vit dans un `config.json` optionnel.

Partez de `config.example.json`, placez votre version dans un dossier, et montez ce
dossier sur `/config` au lancement (`-v ./config:/config:ro`, ou
`python lg.py run --config ./config`). Le fichier est fusionné par-dessus les valeurs
par défaut. Vous ne renseignez donc que ce que vous voulez changer.

```jsonc
{
  // Nœuds qui exécutent les commandes. Un seul nœud "local" aujourd'hui.
  "nodes": [
    {
      "id": "local",                       // identifiant interne, unique
      "type": "local",                     // "local" : exécution dans le conteneur
      "label": "Pastanetwork (Paris)",     // nom affiché dans l'interface
      "location": "FR, Paris",             // localisation affichée
      "ipv4": true,                        // IPv4 proposée pour ce nœud
      "ipv6": true,                        // IPv6 proposée pour ce nœud
      "tools": ["ping", "traceroute", "mtr"]  // outils exposés (limités aux binaires présents)
    }
  ],

  // Politique de validation des cibles.
  "targets": {
    "allow_list": [],          // si non vide, SEULES ces cibles/plages sont autorisées
    "block_list": [],          // cibles/plages explicitement interdites
    "block_private": true,     // refuse les plages privées et réservées
    "block_bogon": true,       // refuse les plages bogon (non routables)
    "allow_hostnames": true    // autorise les noms d'hôte (résolus puis revérifiés)
  },

  // Plafonds par outil. Bornés en interne par des plafonds durs : une valeur
  // plus haute dans ce fichier est ramenée au maximum autorisé.
  "limits": {
    "ping":       { "count": 10,        "timeout_seconds": 30, "max_lines": 60,  "max_bytes": 16384 },
    "traceroute": { "max_hops": 30,     "timeout_seconds": 60, "max_lines": 120, "max_bytes": 32768 },
    "mtr":        { "report_cycles": 10, "timeout_seconds": 60, "max_lines": 120, "max_bytes": 32768 }
  },

  // Fichiers de test de débit. "enabled" et les budgets se pilotent aussi via
  // les variables d'environnement, qui priment.
  "speedtest": {
    "enabled": false,
    "files": [
      { "id": "10mb",  "label": "10 MB",  "size_bytes": 10485760 },
      { "id": "100mb", "label": "100 MB", "size_bytes": 104857600 },
      { "id": "1gb",   "label": "1 GB",   "size_bytes": 1073741824 },
      { "id": "10gb",  "label": "10 GB",  "size_bytes": 10737418240 }
    ],
    "max_file_size_bytes": 10737418240   // plafond appliqué à toute taille de fichier
  },

  // Internationalisation.
  "i18n": {
    "default_language": "fr",
    "available": ["fr", "en"]
  },

  // Politique CORS. allow_origin vide = same-origin uniquement ; l'env
  // CORS_ALLOW_ORIGIN, si définie, prime sur la valeur ci-dessous.
  "cors": {
    "allow_origin": [],                                    // origines cross-origin autorisées
    "allow_credentials": false,
    "allow_methods": ["GET", "HEAD", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "X-Turnstile-Token"],
    "expose_headers": ["Content-Length", "Retry-After"],
    "max_age": 600                                         // cache du préflight, en secondes
  }
}
```

> Le fichier réel doit être du JSON strict, sans commentaires. Les `//` ci-dessus sont
> là pour la documentation uniquement.

## Développement

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows. Sous Linux : source .venv/bin/activate
pip install -r requirements-dev.txt -r requirements-test.txt
npm install                     # outils de minification des assets

python lg.py dev                # lance l'application en local, rechargement automatique
python lg.py minify             # régénère static/ à partir de static_dev/
pytest                          # tests
ruff check                      # lint
```

`lg.py dev` démarre l'application sans Docker. Sous Windows, `ping` et `tracert`
fonctionnent mais `mtr` est absent. Le runtime visé reste Linux, et c'est là que les
commandes tournent en production.

`static_dev/` contient les sources des assets, CSS et JS. `static/` en est la version
construite, et n'est pas versionné.

## Architecture

L'application est écrite avec [Quart][quart] et servie par Hypercorn en plusieurs
workers. Chaque commande est exécutée dans un sous-processus dont la sortie est relayée
en SSE. Redis, interne au conteneur, porte le rate-limiting et les plafonds de
concurrence. SQLite conserve le journal des requêtes. L'interface utilise Tailwind CSS
et Alpine.js.

[quart]: https://quart.palletsprojects.com/

## Sécurité

L'outil exécute des commandes système à partir d'une saisie publique. Toutes les
protections sont appliquées dans l'application elle-même.

- aucune commande n'est passée à un shell, l'exécution se fait par liste d'arguments
- validation stricte des cibles avec le module `ipaddress` (plages privées, réservées
  et bogon refusées, IP revérifiées après résolution DNS pour contrer le DNS-rebinding)
- Cloudflare Turnstile est vérifié avant toute commande et avant tout test de débit
- plafonds de commandes simultanées globaux et par IP, délais d'expiration stricts,
  sortie bornée
- les sauts internes (IP privées et réservées) sont masqués dans la sortie de
  traceroute et MTR : la topologie interne n'est pas exposée
- le conteneur tourne sans privilège root, avec la seule capability `NET_RAW`
- les IP sources sont hachées en SHA-256 avant d'être journalisées, jamais en clair

## Licence

Distribué sous licence [MIT](LICENSE). © 2026 Pastanetwork.
