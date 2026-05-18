from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static_dev"
DEST = ROOT / "static"
WHITELIST_FILE = ROOT / "minification" / "console-whitelist.json"
TAILWIND_INPUT = SRC / "assets" / "css" / "tailwind-input.css"
TAILWIND_OUTPUT = DEST / "assets" / "css" / "tailwind.min.css"
TAILWIND_CONFIG = ROOT / "tailwind.config.js"


def _npx() -> list[str]:
    """
    Retourne le prefixe portable pour invoquer npx.

    Sous Windows, npx est un .cmd qui necessite d'etre appele via cmd /c.

    Returns:
        list[str]: liste de tokens formant le prefixe de commande npx.
    """
    if shutil.which("npx") is None:
        sys.exit("Erreur : npx introuvable. Installez Node.js puis lancez 'npm ci'.")
    # Sous Windows npx est un .cmd que CreateProcess ne sait pas exécuter
    # directement : on passe par cmd /c. Aucune interpolation shell (argv liste).
    if os.name == "nt":
        return ["cmd", "/c", "npx"]
    return ["npx"]


def _load_whitelist() -> set[str]:
    """
    Charge la liste des fichiers JS exempts de suppression des appels console.*.

    Returns:
        set[str]: ensemble de chemins relatifs a la racine du projet (separateur "/").
    """
    if not WHITELIST_FILE.exists():
        return set()
    try:
        data = json.loads(WHITELIST_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {str(p).replace("\\", "/") for p in data.get("whitelistedFiles", [])}


def _minify_js(npx: list[str], src: Path, dest: Path, *, keep_console: bool) -> bool:
    """
    Minifie un fichier JavaScript avec terser.

    Parameters:
        npx (list[str]): prefixe de commande npx (resultat de _npx()).
        src (Path): chemin du fichier source.
        dest (Path): chemin du fichier de destination.
        keep_console (bool): si True, les appels console.* ne sont pas supprimes.

    Returns:
        bool: True si la minification a reussi, False sinon.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    compress = "drop_debugger=true"
    if not keep_console:
        compress += ",drop_console=true"
    argv = [*npx, "terser", str(src), "--compress", compress,
            "--mangle", "--output", str(dest)]
    ok = subprocess.run(argv, check=False).returncode == 0
    print(f"  [js]  {src.relative_to(ROOT)}{'' if ok else '   ECHEC'}")
    return ok


def _minify_css(npx: list[str], src: Path, dest: Path) -> bool:
    """
    Minifie un fichier CSS avec csso.

    Parameters:
        npx (list[str]): prefixe de commande npx (resultat de _npx()).
        src (Path): chemin du fichier source.
        dest (Path): chemin du fichier de destination.

    Returns:
        bool: True si la minification a reussi, False sinon.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    argv = [*npx, "csso", "-i", str(src), "-o", str(dest)]
    ok = subprocess.run(argv, check=False).returncode == 0
    print(f"  [css] {src.relative_to(ROOT)}{'' if ok else '   ECHEC'}")
    return ok


def _build_tailwind(npx: list[str]) -> bool:
    """
    Compile le fichier Tailwind CSS source en CSS minifie.

    Parameters:
        npx (list[str]): prefixe de commande npx (resultat de _npx()).

    Returns:
        bool: True si la compilation a reussi, False sinon.
    """
    if not TAILWIND_INPUT.exists():
        print(f"  [tw]  {TAILWIND_INPUT.name} absent - ignoré")
        return True
    TAILWIND_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    argv = [*npx, "tailwindcss", "-c", str(TAILWIND_CONFIG),
            "-i", str(TAILWIND_INPUT), "-o", str(TAILWIND_OUTPUT), "--minify"]
    ok = subprocess.run(argv, check=False).returncode == 0
    print(f"  [tw]  tailwind.min.css{'' if ok else '   ECHEC'}")
    return ok


def _copy_tree(name: str) -> None:
    """
    Copie un dossier d'assets (fonts, img) tel quel de static_dev/ vers static/.

    Parameters:
        name (str): nom du sous-dossier a copier (ex. "fonts", "img").
    """
    src_dir = SRC / "assets" / name
    if not src_dir.is_dir():
        return
    dest_dir = DEST / "assets" / name
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)
    print(f"  [cp]  assets/{name}/")


def _clean_orphans() -> None:
    """Supprime les fichiers JS/CSS de static/ dont la source dans static_dev/ a disparu."""
    for ext, sub in (("*.js", "js"), ("*.css", "css")):
        dest_dir = DEST / "assets" / sub
        if not dest_dir.is_dir():
            continue
        for dest_file in dest_dir.rglob(ext):
            if dest_file == TAILWIND_OUTPUT:
                continue  # généré depuis tailwind-input.css (nom différent)
            src_file = SRC / dest_file.relative_to(DEST)
            if not src_file.exists():
                dest_file.unlink()
                print(f"  [rm]  {dest_file.relative_to(ROOT)} (orphelin)")


def build() -> int:
    """
    Construit static/ depuis static_dev/ (JS, CSS, Tailwind, fonts, img).

    Returns:
        int: nombre d'erreurs rencontrees pendant le build (0 = succes complet).
    """
    npx = _npx()
    whitelist = _load_whitelist()
    DEST.mkdir(exist_ok=True)
    errors = 0

    print("=== Tailwind ===")
    if not _build_tailwind(npx):
        errors += 1

    print("=== JavaScript ===")
    js_dir = SRC / "assets" / "js"
    if js_dir.is_dir():
        for src in sorted(js_dir.rglob("*.js")):
            rel = str(src.relative_to(ROOT)).replace("\\", "/")
            dest = DEST / src.relative_to(SRC)
            if not _minify_js(npx, src, dest, keep_console=rel in whitelist):
                errors += 1

    print("=== CSS ===")
    css_dir = SRC / "assets" / "css"
    if css_dir.is_dir():
        for src in sorted(css_dir.rglob("*.css")):
            if src == TAILWIND_INPUT:
                continue  # compilé par Tailwind, pas par csso
            dest = DEST / src.relative_to(SRC)
            if not _minify_css(npx, src, dest):
                errors += 1

    print("=== Fonts & images ===")
    _copy_tree("fonts")
    _copy_tree("img")

    print("=== Nettoyage des orphelins ===")
    _clean_orphans()

    if errors:
        print(f"\nBuild terminé avec {errors} erreur(s).")
    else:
        print("\nBuild terminé avec succès.")
    return errors


def _snapshot() -> dict[Path, float]:
    """
    Photographie les dates de modification de tous les fichiers de static_dev/.

    Returns:
        dict[Path, float]: dictionnaire associant chaque chemin a son mtime.
    """
    return {p: p.stat().st_mtime for p in SRC.rglob("*") if p.is_file()}


def main() -> int:
    """
    Point d'entree du script de minification.

    Lance un premier build, puis surveille static_dev/ en boucle si --watch est active.

    Returns:
        int: 0 si le build est un succes, 1 sinon.
    """
    parser = argparse.ArgumentParser(description="Minifie les assets statiques.")
    parser.add_argument("--watch", "-w", action="store_true",
                        help="Re-minifie à chaque changement de static_dev/.")
    parser.add_argument("--ci", action="store_true", help="Mode CI (échec strict).")
    args = parser.parse_args()

    errors = build()
    if not args.watch:
        return 1 if errors else 0

    print("\nMode watch actif. Ctrl+C pour arrêter.")
    last = _snapshot()
    try:
        while True:
            time.sleep(1.0)
            current = _snapshot()
            if current != last:
                last = current
                print("\n--- Changement détecté, re-build ---")
                build()
    except KeyboardInterrupt:
        print("\nArrêt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
