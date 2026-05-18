from __future__ import annotations

from typing import Optional

_LINUX_SCRIPT = """#!/bin/sh
# Test de débit Looking-Glass

url="__URL__"
total=__TOTAL__
streams=4

work=$(mktemp -d)
dl_pids=""

cleanup() {
    kill $dl_pids 2>/dev/null
    rm -rf "$work" 2>/dev/null
}
trap cleanup EXIT
trap 'exit 130' INT TERM

n=1
while [ "$n" -le "$streams" ]; do
    curl -s -o /dev/null -w '%{speed_download} %{size_download} %{time_total}' "$url" >"$work/stats$n" &
    dl_pids="$dl_pids $!"
    n=$((n + 1))
done

any_running() {
    for pid in $dl_pids; do
        kill -0 "$pid" 2>/dev/null && return 0
    done
    return 1
}

printf '\\033[2J\\033[H'
grand_total=$((total * streams))
start_sec=$(date +%s)
last_sec=$start_sec
speed=0
while any_running; do
    sleep 0.2

    received=0
    for pid in $dl_pids; do
        if [ -r "/proc/$pid/io" ]; then
            w=$(awk '/^wchar:/ {print $2}' "/proc/$pid/io" 2>/dev/null)
            received=$((received + ${w:-0}))
        else
            received=$((received + total))
        fi
    done

    now_sec=$(date +%s)
    if [ "$now_sec" -gt "$last_sec" ]; then
        speed=$((received * 8 / (now_sec - start_sec) / 1000000))
        last_sec=$now_sec
    fi

    percent=$((received * 100 / grand_total))
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

    printf '\\r   __LIVE__ : %6d Mbit/s  ▕%s▏ %3d%%' "$speed" "$bar" "$percent"
done

wait $dl_pids

printf '\\r%*s\\r' 64 ''
awk -v streams="$streams" -v conn="__CONN__" -v total_label="__TOTLBL__" -v vol_label="__VOLLBL__" -v dur_label="__DURLBL__" -v unit="__UNIT__" -v w=__WIDTH__ -v sep="__SEP__" '
function pad(s) { while (length(s) < w) s = s " "; return s }
{
    speed[NR]  = $1
    sum_speed += $1
    sum_bytes += $2
    if ($3 > max_time) max_time = $3
}
END {
    printf "\\n"
    for (i = 1; i <= streams; i++)
        printf "   %s : %.1f Mbit/s\\n", pad(sprintf("%s %d", conn, i)), speed[i] * 8 / 1e6
    printf "   %s\\n", sep
    printf "   %s : %.1f Mbit/s\\n", pad(total_label), sum_speed * 8 / 1e6
    printf "   %s : %.0f %s\\n", pad(vol_label), sum_bytes / 1e6, unit
    printf "   %s : %.2f s\\n", pad(dur_label), max_time
}' "$work"/stats*
"""


_WINDOWS_SCRIPT = """# Test de débit Looking-Glass

$url     = '__URL__'
$total   = __TOTAL__
$streams = 4
$stats   = Join-Path $env:TEMP 'lg_speedtest.txt'

$curlArgs = @('-Z', '--parallel-immediate', '-s', '-w', '%{speed_download};%{size_download};%{time_total}\\n')
foreach ($k in 1..$streams) { $curlArgs += @('-o', 'NUL') }
foreach ($k in 1..$streams) { $curlArgs += $url }

$proc = Start-Process curl.exe -PassThru -NoNewWindow -RedirectStandardOutput $stats -ArgumentList $curlArgs

try {
    try { Clear-Host } catch {}

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $grandTotal = [int64]$total * $streams
    $received = 0
    while (-not $proc.HasExited) {
        Start-Sleep -Milliseconds 200

        $info = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue
        if ($info) { $received = [int64]$info.WriteTransferCount }
        $percent = [Math]::Min(100, [int]($received * 100 / $grandTotal))

        $filled = [int]($percent * 24 / 100)
        $bar    = ('█' * $filled) + ('░' * (24 - $filled))

        $elapsed = $watch.Elapsed.TotalSeconds
        $speed = if ($elapsed -gt 0) { [int](($received * 8) / $elapsed / 1e6) } else { 0 }

        Write-Host -NoNewline ("`r   __LIVE__ : {0,6} Mbit/s  ▕{1}▏ {2,3}%" -f $speed, $bar, $percent)
    }

    $proc.WaitForExit()
    Write-Host -NoNewline ("`r{0}`r" -f (' ' * 64))
    Write-Host ""

    $sumSpeed = 0.0
    $sumBytes = 0.0
    $maxTime  = 0.0
    $index = 0
    foreach ($line in @(Get-Content $stats -ErrorAction SilentlyContinue)) {
        $parts = $line.Trim() -split ';'
        if ($parts.Count -lt 3) { continue }
        $index++
        $mbps = [double]$parts[0] * 8 / 1e6
        $sumSpeed += $mbps
        $sumBytes += [double]$parts[1]
        if ([double]$parts[2] -gt $maxTime) { $maxTime = [double]$parts[2] }
        Write-Host ("   " + ("__CONN__ $index").PadRight(__WIDTH__) + (" : {0:N1} Mbit/s" -f $mbps))
    }
    Write-Host "   __SEP__"
    Write-Host ("   " + "__TOTLBL__".PadRight(__WIDTH__) + (" : {0:N1} Mbit/s" -f $sumSpeed))
    Write-Host ("   " + "__VOLLBL__".PadRight(__WIDTH__) + (" : {0:N0} __UNIT__" -f ($sumBytes / 1e6)))
    Write-Host ("   " + "__DURLBL__".PadRight(__WIDTH__) + (" : {0:N2} s" -f $maxTime))
}
finally {
    try { if (-not $proc.HasExited) { $proc.Kill() } } catch { }
    Remove-Item $stats -Force -ErrorAction SilentlyContinue
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
    conn: str,
    total_label: str,
    volume_label: str,
    duration_label: str,
    unit: str,
) -> Optional[str]:
    """
    Construit le script de test de débit pour le système d'exploitation demandé.

    Parameters:
        os_name (str): cible, « linux » (sh/bash/zsh) ou « windows » (PowerShell).
        download_url (str): URL signée du fichier de test à télécharger.
        total (int): taille d'une connexion, en octets, pour la barre de progression.
        live (str): libellé localisé de la ligne de débit en direct.
        conn (str): libellé localisé d'une connexion (« Connexion »).
        total_label (str): libellé localisé du débit total agrégé.
        volume_label (str): libellé localisé du volume téléchargé.
        duration_label (str): libellé localisé de la durée.
        unit (str): unité de volume localisée (« Mo » ou « MB »).

    Returns:
        Optional[str]: script prêt à exécuter, ou None si le système est inconnu.
    """
    template = _TEMPLATES.get(os_name)
    if template is None:
        return None

    width = max(len(conn) + 2, len(total_label), len(volume_label), len(duration_label))
    separator = "─" * (width + 17)

    return (
        template
        .replace("__TOTAL__", str(total))
        .replace("__WIDTH__", str(width))
        .replace("__SEP__", separator)
        .replace("__LIVE__", live)
        .replace("__CONN__", conn)
        .replace("__TOTLBL__", total_label)
        .replace("__VOLLBL__", volume_label)
        .replace("__DURLBL__", duration_label)
        .replace("__UNIT__", unit)
        .replace("__URL__", download_url)
    )
