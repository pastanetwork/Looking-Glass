#!/usr/bin/env bash
# ============================================================================
#  Looking Glass — Création des fichiers sparse pour le speedtest
# ============================================================================
#
# Tailles synchronisées avec config.example.json :
#   10mb.bin  =  10 485 760 octets
#   100mb.bin = 104 857 600 octets
#   1gb.bin   = 1 073 741 824 octets
#   10gb.bin  = 10 737 418 240 octets
#
# Doit être lancé en root (chown) sur un filesystem supportant les sparse files
# (ext4, xfs, btrfs, zfs : standard sur Linux).
# ============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Ce script doit être exécuté en root (chown nginx)." >&2
    exit 1
fi

DEFAULT_DIR="/var/www/lg-speedtest"
read -rp "Dossier de stockage des fichiers speedtest [${DEFAULT_DIR}] : " DIR
DIR="${DIR:-${DEFAULT_DIR}}"

mkdir -p "${DIR}"

declare -A FILES=(
    ["10mb"]=10485760
    ["100mb"]=104857600
    ["1gb"]=1073741824
    ["10gb"]=10737418240
)

echo ""
for fid in "${!FILES[@]}"; do
    size="${FILES[$fid]}"
    path="${DIR}/${fid}.bin"
    printf 'Création de %s (%s octets, sparse)...\n' "${path}" "${size}"
    truncate -s "${size}" "${path}"
done

chmod 644 "${DIR}"/*.bin

NGINX_USER=""
for u in www-data nginx http; do
    if id "${u}" >/dev/null 2>&1; then
        NGINX_USER="${u}"
        break
    fi
done

if [[ -n "${NGINX_USER}" ]]; then
    chown -R "${NGINX_USER}":"${NGINX_USER}" "${DIR}"
    echo ""
    echo "Propriétaire défini : ${NGINX_USER}"
else
    echo ""
    echo "AVERTISSEMENT : utilisateur nginx introuvable (www-data / nginx / http)."
    echo "Ajustez le propriétaire manuellement avant de redémarrer nginx."
fi

cat <<EOF

============================================================
Terminé. Fichiers créés dans : ${DIR}

Espace disque réellement utilisé (sparse) :
$(du -sh "${DIR}")

Contenu :
$(ls -lh "${DIR}"/*.bin)

============================================================
EOF
