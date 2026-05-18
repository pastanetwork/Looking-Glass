from __future__ import annotations

import copy
import os
import secrets
from pathlib import Path
from typing import Any

import orjson
from dotenv import load_dotenv

from modules.constants.ip_rules import CLOUDFLARE_NETS
from modules.constants.limits import (
    HARD_CEILINGS,
    SPEEDTEST_CONCURRENCY_CAP,
    SPEEDTEST_MAX_FILE_BYTES,
)

DEFAULTS: dict[str, Any] = {
    "nodes": [
        {
            "id": "local",
            "type": "local",
            "label": "Looking Glass (local)",
            "location": None,
            "ipv4": True,
            "ipv6": True,
            "tools": ["ping", "traceroute", "mtr"],
        },
    ],
    "targets": {
        "allow_list": [],
        "block_list": [],
        "block_private": True,
        "block_bogon": True,
        "allow_hostnames": True,
    },
    "limits": {
        "ping": {"count": 10, "timeout_seconds": 30, "max_lines": 60, "max_bytes": 16384},
        "traceroute": {"max_hops": 30, "timeout_seconds": 60, "max_lines": 120, "max_bytes": 32768},
        "mtr": {"report_cycles": 10, "timeout_seconds": 60, "max_lines": 120, "max_bytes": 32768},
    },
    "speedtest": {
        "enabled": False,
        "files": [
            {"id": "10mb", "label": "10 MB", "size_bytes": 10485760},
            {"id": "100mb", "label": "100 MB", "size_bytes": 104857600},
            {"id": "1gb", "label": "1 GB", "size_bytes": 1073741824},
            {"id": "10gb", "label": "10 GB", "size_bytes": 10737418240},
        ],
        "max_file_size_bytes": SPEEDTEST_MAX_FILE_BYTES,
    },
    "i18n": {"default_language": "fr", "available": ["fr", "en"]},
    "cors": {
        "allow_origin": [],
        "allow_credentials": False,
        "allow_methods": ["GET", "HEAD", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Turnstile-Token"],
        "expose_headers": ["Content-Length", "Retry-After"],
        "max_age": 600,
    },
    "cloudflare": {"enabled": False},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """
    Fusionne récursivement deux dictionnaires.

    Parameters:
        base (dict): dictionnaire de base (valeurs par défaut).
        override (dict): dictionnaire dont les valeurs priment.

    Returns:
        dict: nouveau dictionnaire fusionné.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_bool(name: str, default: bool) -> bool:
    """
    Lit une variable d'environnement booléenne.

    Parameters:
        name (str): nom de la variable.
        default (bool): valeur retenue si la variable est absente.

    Returns:
        bool: la valeur interprétée.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    """
    Lit une variable d'environnement entière.

    Parameters:
        name (str): nom de la variable.
        default (int): valeur retenue si la variable est absente ou invalide.

    Returns:
        int: la valeur interprétée.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_config() -> dict[str, Any]:
    """
    Charge la configuration complète de l'application.

    Returns:
        dict[str, Any]: la configuration prête à l'emploi.
    """
    load_dotenv()
    config: dict[str, Any] = copy.deepcopy(DEFAULTS)

    config_file = os.getenv("LG_CONFIG_FILE", "/config/config.json")
    path = Path(config_file)
    if path.is_file():
        config = _deep_merge(config, orjson.loads(path.read_bytes()))

    config["dev"] = os.getenv("DEV", "False") == "True"
    config["static_folder"] = "static_dev" if config["dev"] else "static"
    config["host"] = os.getenv("LG_HOST", "0.0.0.0")
    config["port"] = _env_int("LG_PORT", 8080)
    config["workers"] = _env_int("LG_WORKERS", 4)
    config["public_url"] = os.getenv("LG_PUBLIC_URL", "")
    config["db_path"] = os.getenv("LG_DB_PATH", "data/looking_glass.db")

    config["redis_host"] = os.getenv("REDIS_HOST", "127.0.0.1")
    config["redis_port"] = _env_int("REDIS_PORT", 6379)
    config["redis_password"] = os.getenv("REDIS_PASSWORD", "")

    config["ip_hash_salt"] = _resolve_ip_hash_salt(config["db_path"])

    config["turnstile"] = {
        "site_key": os.getenv("TURNSTILE_SITE_KEY", ""),
        "secret_key": os.getenv("TURNSTILE_SECRET_KEY", ""),
        "dev_bypass": _env_bool("TURNSTILE_DEV_BYPASS", False),
    }

    config["global_command_cap"] = _env_int("GLOBAL_COMMAND_CAP", 8)
    config["per_ip_command_cap"] = _env_int("PER_IP_COMMAND_CAP", 2)
    config["query_log_retention_days"] = _env_int("QUERY_LOG_RETENTION_DAYS", 90)

    trusted = os.getenv("TRUSTED_PROXY_HOSTS", "127.0.0.1")
    config["trusted_proxy_hosts"] = [h.strip() for h in trusted.split(",") if h.strip()]

    allowed = os.getenv("ALLOWED_HOSTS", "")
    config["allowed_hosts"] = [h.strip() for h in allowed.split(",") if h.strip()]

    # Origines CORS : liste vide = same-origin uniquement. L'env, si présente,
    # prime sur le fichier JSON ; absente, la valeur JSON (ou le défaut) est conservée.
    cors_origin = os.getenv("CORS_ALLOW_ORIGIN")
    if cors_origin is not None:
        config["cors"]["allow_origin"] = [o.strip() for o in cors_origin.split(",") if o.strip()]

    # Cloudflare : si activé, l'IP réelle du visiteur est lue dans l'en-tête
    # CF-Connecting-IP. cloudflare_nets sert de repli ; il est rafraîchi au
    # démarrage par un fetch des plages officielles (voir main.py).
    config["cloudflare"]["enabled"] = _env_bool("CLOUDFLARE_ENABLED", config["cloudflare"]["enabled"])
    config["cloudflare_nets"] = list(CLOUDFLARE_NETS)

    config["default_language"] = os.getenv("DEFAULT_LANGUAGE", config["i18n"]["default_language"])

    config["speedtest"]["enabled"] = _env_bool("SPEEDTEST_ENABLED", config["speedtest"]["enabled"])
    config["speedtest"]["daily_byte_budget"] = _env_int("SPEEDTEST_DAILY_BYTE_BUDGET", 0)
    config["speedtest"]["per_ip_byte_budget"] = _env_int("SPEEDTEST_PER_IP_BYTE_BUDGET", 0)
    config["speedtest"]["max_kbps"] = _env_int("SPEEDTEST_MAX_KBPS", 0)
    config["speedtest"]["concurrency"] = _env_int("SPEEDTEST_CONCURRENCY", SPEEDTEST_CONCURRENCY_CAP)

    _clamp_limits(config)
    _validate(config)
    return config


def _clamp_limits(config: dict) -> None:
    """
    Borne les limites du fichier JSON aux plafonds durs définis en code.

    Parameters:
        config (dict): configuration à borner.
    """
    for tool, ceilings in HARD_CEILINGS.items():
        tool_limits = config["limits"].get(tool, {})
        for key, ceiling in ceilings.items():
            if key in tool_limits:
                tool_limits[key] = min(int(tool_limits[key]), ceiling)
        config["limits"][tool] = tool_limits


def _resolve_ip_hash_salt(db_path: str) -> str:
    """
    Résout le sel de hachage des IP sources.

    Parameters:
        db_path (str): chemin de la base, qui indique le dossier du sel.

    Returns:
        str: le sel de hachage.
    """
    env_salt = os.getenv("IP_HASH_SALT", "").strip()
    if env_salt:
        return env_salt

    salt_file = Path(os.path.dirname(db_path) or ".") / ".ip_hash_salt"
    if salt_file.is_file():
        existing = salt_file.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    salt = secrets.token_hex(32)
    try:
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        salt_file.write_text(salt, encoding="utf-8")
    except OSError:
        pass  # non persistable : le sel reste valable pour la session courante

    return salt


def _validate(config: dict) -> None:
    """
    Valide la configuration Turnstile.

    Parameters:
        config (dict): configuration à vérifier.
    """
    turnstile = config["turnstile"]
    bypass = config["dev"] and turnstile["dev_bypass"]
    if not bypass and (not turnstile["site_key"] or not turnstile["secret_key"]):
        raise RuntimeError(
            "TURNSTILE_SITE_KEY et TURNSTILE_SECRET_KEY sont requis "
            "(sauf si DEV=True et TURNSTILE_DEV_BYPASS=True)."
        )
