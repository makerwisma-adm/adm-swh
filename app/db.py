"""Koneksi database: SQLite lokal, Turso (cloud), atau Blob persist di Vercel."""
import os
import sqlite3
import threading
import urllib.error
import urllib.request
from typing import Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_VERCEL = os.getenv("VERCEL") == "1"

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()
USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)

BLOB_DB_PATHNAME = "database/sppg_keuangan.db"
BLOB_API = "https://blob.vercel-storage.com"

if IS_VERCEL and not USE_TURSO:
    DB_PATH = "/tmp/sppg_keuangan.db"
else:
    DB_PATH = os.path.join(BASE_DIR, "sppg_keuangan.db")

_blob_lock = threading.Lock()
_db_restored = False


def _blob_token() -> str:
    return os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()


def _blob_store_host() -> Optional[str]:
    """Derive private blob host from read-write token (vercel_blob_rw_{storeId}_...)."""
    token = _blob_token()
    if not token.startswith("vercel_blob_rw_"):
        return None
    parts = token.split("_")
    store_id = parts[3] if len(parts) >= 5 and parts[:3] == ["vercel", "blob", "rw"] else ""
    if not store_id:
        return None
    return f"{store_id.lower()}.private.blob.vercel-storage.com"


def _blob_download_url() -> Optional[str]:
    host = _blob_store_host()
    if host:
        return f"https://{host}/{BLOB_DB_PATHNAME}"
    return None


def use_blob_persist() -> bool:
    return IS_VERCEL and not USE_TURSO and bool(_blob_token())


def _blob_put(pathname: str, data: bytes):
    token = _blob_token()
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN tidak tersedia")
    req = urllib.request.Request(
        f"{BLOB_API}/{pathname}",
        data=data,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "x-api-version": "7",
            "x-vercel-blob-access": "private",
            "x-content-type": "application/x-sqlite3",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
        },
    )
    return urllib.request.urlopen(req, timeout=90)


def sync_db_from_blob() -> bool:
    """Unduh SQLite dari Vercel Blob ke /tmp (sekali per proses)."""
    global _db_restored
    if not use_blob_persist() or _db_restored:
        return _db_restored
    with _blob_lock:
        if _db_restored:
            return True
        url = _blob_download_url()
        if not url:
            _db_restored = True
            return False
        try:
            req = urllib.request.Request(
                url,
                method="GET",
                headers={"Authorization": f"Bearer {_blob_token()}"},
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if data:
                with open(DB_PATH, "wb") as f:
                    f.write(data)
                _db_restored = True
                return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                _db_restored = True
                return False
            print(f"⚠️  sync_db_from_blob HTTP {e.code}: {e}")
            _db_restored = True
            return False
        except Exception as exc:
            print(f"⚠️  sync_db_from_blob gagal: {exc}")
            _db_restored = True
            return False
    return False


def sync_db_to_blob() -> bool:
    """Unggah SQLite ke Vercel Blob setelah perubahan data."""
    if not use_blob_persist() or not os.path.exists(DB_PATH):
        return False
    with _blob_lock:
        try:
            with open(DB_PATH, "rb") as f:
                data = f.read()
            if not data:
                return False
            _blob_put(BLOB_DB_PATHNAME, data)
            return True
        except Exception as exc:
            # Jangan gagalkan request/startup jika Blob sementara error
            print(f"⚠️  sync_db_to_blob gagal: {exc}")
            return False


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


class _PersistingConnection:
    """SQLite connection yang menyimpan ke Blob setelah commit."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return self._conn.execute(sql, params)

    def executemany(self, sql, params_list):
        return self._conn.executemany(sql, params_list)

    def commit(self):
        self._conn.commit()
        sync_db_to_blob()

    def close(self):
        self._conn.close()

    def cursor(self):
        return self._conn.cursor()

    @property
    def total_changes(self):
        return self._conn.total_changes

    def __getattr__(self, name):
        return getattr(self._conn, name)


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
        return _TursoConnection(raw)

    if use_blob_persist():
        sync_db_from_blob()

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if use_blob_persist():
        return _PersistingConnection(conn)
    return conn


def db_info() -> str:
    if USE_TURSO:
        return "turso"
    if use_blob_persist():
        return "vercel-blob"
    if IS_VERCEL:
        return "vercel-tmp"
    return "sqlite"
