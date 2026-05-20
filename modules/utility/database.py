from __future__ import annotations

import os
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    import logging


async def get_db_connection(db_path: str) -> aiosqlite.Connection:
    """
    Ouvre une connexion SQLite configurée en mode WAL.

    Parameters:
        db_path (str): chemin vers le fichier de base de données SQLite.

    Returns:
        aiosqlite.Connection: connexion prête à l'emploi avec row_factory configurée.
    """
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    db = await aiosqlite.connect(db_path, timeout=30.0)
    db.row_factory = aiosqlite.Row

    await db.execute("PRAGMA busy_timeout=30000")
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA cache_size=-8000")
    await db.execute("PRAGMA mmap_size=268435456")

    return db


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    """
    Ajoute une colonne à une table existante si elle est absente.

    Migration idempotente : sans effet si la colonne existe déjà.

    Parameters:
        db (aiosqlite.Connection): connexion SQLite ouverte.
        table (str): nom de la table à migrer.
        column (str): nom de la colonne à garantir.
        definition (str): type SQL de la colonne (ex. "INTEGER").
    """
    cursor = await db.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in await cursor.fetchall()}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def initialize_database(db: aiosqlite.Connection, logger: logging.Logger) -> None:
    """
    Crée le schéma SQLite initial (table et index du journal des requêtes).

    Parameters:
        db (aiosqlite.Connection): connexion SQLite ouverte.
        logger (logging.Logger): logger applicatif pour confirmer l'initialisation.
    """
    await db.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          node_id TEXT NOT NULL,
          command_type TEXT NOT NULL,
          target TEXT NOT NULL,
          family INTEGER,
          source_ip_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          exit_code INTEGER,
          duration_ms INTEGER,
          bytes_served INTEGER,
          created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    await _ensure_column(db, "query_log", "bytes_served", "INTEGER")
    await _ensure_column(db, "query_log", "session_id", "TEXT")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_query_log_created ON query_log(created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_query_log_type ON query_log(command_type)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_query_log_status ON query_log(status)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_query_log_session ON query_log(session_id)")
    await db.commit()

    logger.info("Schéma SQLite initialisé")
