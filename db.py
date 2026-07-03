"""Koneksi database: SQLite lokal (dev) atau Turso (Vercel production)."""
import os
import sqlite3
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = os.getenv("VERCEL") == "1"

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()
USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)

if IS_VERCEL and not USE_TURSO:
    DB_PATH = "/tmp/sppg_keuangan.db"
else:
    DB_PATH = os.path.join(BASE_DIR, "sppg_keuangan.db")


class _TursoConnection:
    """Wrapper sync untuk libsql — API mirip sqlite3.Connection."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = self._conn.cursor()
        cur.executemany(sql, params_list)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    @property
    def total_changes(self):
        return self._conn.total_changes


def get_db() -> Any:
    if USE_TURSO:
        try:
            import libsql
        except ImportError as e:
            raise RuntimeError(
                "Turso aktif tapi paket libsql belum terpasang. "
                "Jalankan: pip install libsql"
            ) from e
        raw = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
        raw.row_factory = sqlite3.Row
        return raw

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def db_info() -> str:
    if USE_TURSO:
        return "turso"
    if IS_VERCEL:
        return "vercel-tmp"
    return "sqlite"