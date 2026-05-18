from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from watchfiles import watch

ROOT = Path(__file__).resolve().parent

IMAGE_NAME = "looking-glass"
DOCKERFILE = "deploy/Dockerfile"

app = typer.Typer(
    help="Outils de build et de développement de la Looking Glass.",
    add_completion=False,
    no_args_is_help=True,
)


def _run(argv: list[str], env: Optional[dict[str, str]] = None) -> int:
    """
    Exécute une commande système, l'affiche et retourne son code de sortie.

    Parameters:
        argv (list[str]): commande et arguments à exécuter.
        env (Optional[dict[str, str]]): variables d'environnement à passer au processus.

    Returns:
        int: code de retour du processus (0 = succès, autre = erreur).
    """
    typer.secho("$ " + " ".join(argv), fg=typer.colors.BRIGHT_BLACK)
    try:
        return subprocess.run(argv, cwd=ROOT, env=env, check=False).returncode
    except FileNotFoundError:
        typer.secho(f"Commande introuvable : {argv[0]}", fg=typer.colors.RED)
        return 127


@app.command()
def build(
    tag: str = typer.Option("local", "--tag", "-t", help="Tag de l'image."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Build sans cache Docker."),
) -> None:
    """Construit l'image Docker depuis deploy/Dockerfile."""
    argv = ["docker", "build", "-f", DOCKERFILE, "-t", f"{IMAGE_NAME}:{tag}"]
    if no_cache:
        argv.append("--no-cache")
    argv.append(".")
    raise typer.Exit(_run(argv))


@app.command()
def dev(
    port: int = typer.Option(8080, "--port", "-p", help="Port d'écoute local."),
    no_bypass: bool = typer.Option(False, "--no-bypass", help="Ne pas bypasser Turnstile."),
) -> None:
    """Lance l'application en local avec rechargement automatique (sans Docker)."""
    env = os.environ.copy()
    env.setdefault("DEV", "True")
    if not no_bypass:
        env.setdefault("TURNSTILE_DEV_BYPASS", "True")
    env["LG_PORT"] = str(port)
    argv = [sys.executable, "-m", "hypercorn", "main:app", "--bind", f"127.0.0.1:{port}"]

    def _spawn() -> subprocess.Popen:
        typer.secho("$ " + " ".join(argv), fg=typer.colors.BRIGHT_BLACK)
        return subprocess.Popen(argv, cwd=ROOT, env=env)

    # Redémarrage complet du processus à chaque changement : le rechargement
    # interne de Hypercorn (--reload) corrompt le socket d'écoute sous Windows.
    proc = _spawn()
    try:
        for _ in watch(ROOT / "main.py", ROOT / "modules", ROOT / "i18n"):
            typer.secho("Changement détecté, redémarrage…", fg=typer.colors.YELLOW)
            proc.terminate()
            proc.wait()
            proc = _spawn()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        proc.wait()


@app.command()
def run(
    port: int = typer.Option(8080, "--port", "-p", help="Port hôte à mapper."),
    tag: str = typer.Option("local", "--tag", "-t", help="Tag de l'image à lancer."),
    env_file: str = typer.Option(".env", "--env-file", help="Fichier d'environnement."),
    config: str = typer.Option("", "--config", help="Dossier de config à monter sur /config."),
    detach: bool = typer.Option(False, "--detach", "-d", help="Lancer en arrière-plan."),
) -> None:
    """Lance l'image Docker construite avec les capabilities réseau requises."""
    argv = ["docker", "run", "--rm", "-p", f"{port}:8080",
            "--cap-drop", "ALL", "--cap-add", "NET_RAW"]
    if (ROOT / env_file).exists():
        argv += ["--env-file", env_file]
    else:
        typer.secho(f"Avertissement : {env_file} introuvable, lancement sans --env-file.",
                    fg=typer.colors.YELLOW)
    # L'image Docker est l'image de production : elle ne contient que les assets
    # minifiés (static/), pas static_dev/. On force donc le mode production,
    # quelle que soit la valeur de DEV dans le fichier d'environnement.
    argv += ["-e", "DEV=False"]
    if config:
        argv += ["-v", f"{Path(config).resolve()}:/config:ro"]
    if detach:
        argv.append("-d")
    argv.append(f"{IMAGE_NAME}:{tag}")
    raise typer.Exit(_run(argv))


@app.command()
def minify(
    watch: bool = typer.Option(False, "--watch", "-w", help="Re-minifie à chaque changement."),
    ci: bool = typer.Option(False, "--ci", help="Mode CI (échec strict)."),
) -> None:
    """Construit les assets statiques (static_dev/ -> static/)."""
    argv = [sys.executable, "minification/minify.py"]
    if watch:
        argv.append("--watch")
    if ci:
        argv.append("--ci")
    raise typer.Exit(_run(argv))


if __name__ == "__main__":
    app()
