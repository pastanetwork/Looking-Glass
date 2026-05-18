from __future__ import annotations

HARD_CEILINGS: dict[str, dict[str, int]] = {
    "ping": {"count": 30, "timeout_seconds": 60, "max_lines": 200, "max_bytes": 65536},
    "traceroute": {"max_hops": 64, "timeout_seconds": 120, "max_lines": 400, "max_bytes": 131072},
    "mtr": {"report_cycles": 30, "timeout_seconds": 120, "max_lines": 400, "max_bytes": 131072},
    "dns": {"timeout_seconds": 60, "max_lines": 400, "max_bytes": 131072},
}

# Tâche de nettoyage périodique du journal.
CLEANUP_INTERVAL_SECONDS = 86400      # 24 heures
CLEANUP_INITIAL_DELAY_SECONDS = 60    # délai avant le premier passage
CLEANUP_ERROR_DELAY_SECONDS = 300     # backoff après une erreur

# Suppression du journal par lots (évite de verrouiller la base).
QUERY_LOG_CLEANUP_BATCH = 5000

# Concurrence : durée de vie d'un slot Redis (filet de sécurité si un worker meurt).
CONCURRENCY_SLOT_TTL = 300

# Speedtest (fichiers de test de débit).
SPEEDTEST_CHUNK_SIZE = 65536        # 64 Kio par chunk
SPEEDTEST_CONCURRENCY_CAP = 4       # téléchargements simultanés maximum
SPEEDTEST_BUDGET_TTL = 93600        # ~26 h, expiration des compteurs journaliers
SPEEDTEST_FLUSH_EVERY = 16          # mise à jour des compteurs Redis tous les 16 chunks
SPEEDTEST_SLOT_TTL = 300            # durée de vie d'un slot de concurrence speedtest
SPEEDTEST_MAX_FILE_BYTES = 10737418240   # plafond par défaut de taille de fichier (10 Gio)

# Turnstile (vérification anti-robot Cloudflare).
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT_SECONDS = 2.5

# Résolution DNS des cibles.
DNS_RESOLVE_TIMEOUT_SECONDS = 5.0
