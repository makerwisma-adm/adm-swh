#!/usr/bin/env python3
"""Salin data SQLite lokal ke Turso. Jalankan setelah buat database di turso.tech"""
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()
LOCAL_DB = os.path.join(BASE, "sppg_keuangan.db")

if not TURSO_URL or not TURSO_TOKEN:
    print("Set TURSO_DATABASE_URL dan TURSO_AUTH_TOKEN dulu.")
    print("Buat database gratis di https://turso.tech")
    sys.exit(1)

import libsql

src = sqlite3.connect(LOCAL_DB)
dst = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

tables = [r[0] for r in src.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchall()]

for table in tables:
    ddl = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()[0]
    dst.execute(f"DROP TABLE IF EXISTS {table}")
    dst.execute(ddl)
    cols = [d[1] for d in src.execute(f"PRAGMA table_info({table})").fetchall()]
    placeholders = ",".join("?" * len(cols))
    col_list = ",".join(cols)
    rows = src.execute(f"SELECT {col_list} FROM {table}").fetchall()
    if rows:
        dst.executemany(
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
            rows,
        )
    print(f"  {table}: {len(rows)} baris")

dst.commit()
src.close()
dst.close()
print("Migrasi selesai.")