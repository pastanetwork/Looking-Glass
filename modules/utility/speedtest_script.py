from __future__ import annotations

from typing import Optional

_LINUX_SCRIPT = """#!/bin/sh
# Test de débit Looking-Glass

url="__URL__"
total=__TOTAL__

body=$(mktemp)
stats=$(mktemp)

cleanup() {
    kill "$dl_pid" 2>/dev/null
    rm -f "$body" "$stats" 2>/dev/null
}
trap cleanup EXIT
trap 'exit 130' INT TERM

curl -s -o "$body" -w '%{speed_download} %{time_total} %{size_download}' "$url" >"$stats" &
dl_pid=$!

printf '\\033[2J\\033[H'
prev=0
while kill -0 "$dl_pid" 2>/dev/null; do
    sleep 0.5

    received=$(wc -c <"$body" 2>/dev/null || echo 0)
    percent=$((received * 100 / total))
    [ "$percent" -gt 100 ] && percent=100

    filled=$((percent * 24 / 100))
    bar=""
    i=0
    while [ "$i" -lt 24 ]; do
        if [ "$i" -lt "$filled" ]; then
            bar="${bar}█"
        else
            bar="${bar}░"
        fi
        i=$((i + 1))
    done

    speed=$(((received - prev) * 16 / 1000000))
    printf '\\r   __LIVE__ : %5d Mbit/s  ▕%s▏ %3d%%' "$speed" "$bar" "$percent"
    prev=$received
done

wait "$dl_pid"

printf '\\r%*s\\r' 64 ''
read -r speed_bps total_time total_bytes <"$stats"
awk -v s="$speed_bps" -v t="$total_time" -v z="$total_bytes" '
BEGIN {
    printf "\\n"
    printf "   __AVG__ : %.1f Mbit/s\\n", s * 8 / 1e6
    printf "   __VOL__ : %.0f __UNIT__\\n", z / 1e6
    printf "   __DUR__ : %.2f s\\n", t
}'
"""

_WINDOWS_SCRIPT = """# Test de débit Looking-Glass

$url   = '__URL__'
$total = __TOTAL__
$body  = "$env:TEMP\\lg_speedtest.bin"

if (Test-Path $body) {
    Remove-Item $body
}

$job = Start-Job -ArgumentList $url, $body -ScriptBlock {
    param($u, $b)
    curl.exe -s -o $b -w '%{speed_download};%{time_total};%{size_download}' $u
}

try {
    try { Clear-Host } catch {}

    $prev = 0
    while ($job.State -eq 'Running' -or $job.State -eq 'NotStarted') {
        Start-Sleep -Milliseconds 400

        $received = if (Test-Path $body) { (Get-Item $body).Length } else { 0 }
        $percent  = [Math]::Min(100, [int]($received * 100 / $total))

        # Construit une barre de progression de 24 caractères.
        $filled = [int]($percent * 24 / 100)
        $bar    = ('█' * $filled) + ('░' * (24 - $filled))

        $speed = [int](($received - $prev) * 16 / 1000000)
        Write-Host -NoNewline ("`r   __LIVE__ : {0,5} Mbit/s  ▕{1}▏ {2,3}%" -f $speed, $bar, $percent)
        $prev = $received
    }

    Wait-Job $job | Out-Null
    $stats = ((Receive-Job $job) -join '').Trim() -split ';'

    $avgSpeed = [double]$stats[0] * 8 / 1e6
    $volume   = [double]$stats[2] / 1e6
    $duration = [double]$stats[1]

    Write-Host -NoNewline ("`r{0}`r" -f (' ' * 64))
    Write-Host ""
    Write-Host ("   __AVG__ : {0:N1} Mbit/s" -f $avgSpeed)
    Write-Host ("   __VOL__ : {0:N0} __UNIT__" -f $volume)
    Write-Host ("   __DUR__ : {0:N2} s" -f $duration)
}
finally {
    Stop-Job   $job -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    Remove-Item $body -ErrorAction SilentlyContinue
}
"""

_TEMPLATES = {"linux": _LINUX_SCRIPT, "windows": _WINDOWS_SCRIPT}
SUPPORTED_OS = frozenset(_TEMPLATES)

def build_speedtest_script(
    os_name: str,
    *,
    download_url: str,
    total: int,
    live: str,
    avg: str,
    volume: str,
    duration: str,
    unit: str,
) -> Optional[str]:
    """
    Construit le script de test de débit pour le système d'exploitation demandé.

    Parameters:
        os_name (str): cible, « linux » (sh/bash/zsh) ou « windows » (PowerShell).
        download_url (str): URL signée du fichier de test à télécharger.
        total (int): taille totale du fichier, en octets, pour la barre de progression.
        live (str): libellé localisé de la ligne de débit en direct.
        avg (str): libellé localisé du débit moyen.
        volume (str): libellé localisé du volume téléchargé.
        duration (str): libellé localisé de la durée.
        unit (str): unité de volume localisée (« Mo » ou « MB »).

    Returns:
        Optional[str]: script prêt à exécuter, ou None si le système est inconnu.
    """
    template = _TEMPLATES.get(os_name)
    if template is None:
        return None

    width = max(len(avg), len(volume), len(duration))

    return (
        template
        .replace("__TOTAL__", str(total))
        .replace("__LIVE__", live)
        .replace("__AVG__", avg.ljust(width))
        .replace("__VOL__", volume.ljust(width))
        .replace("__DUR__", duration.ljust(width))
        .replace("__UNIT__", unit)
        .replace("__URL__", download_url)
    )
