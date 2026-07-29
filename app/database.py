"""Database schema, migrations, and seed data."""
import sqlite3
from passlib.hash import pbkdf2_sha256

from app.config import BASE_DIR
from app.db import get_db

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            mitra_nama TEXT,
            menu_access TEXT
        )
    """)
    try:
        c.execute("ALTER TABLE users ADD COLUMN mitra_nama TEXT")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN menu_access TEXT")
    except Exception:
        pass

    # Tagihan Mitra (core table matching Excel)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tagihan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            no TEXT,
            pengajuan TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            status TEXT,
            rekening TEXT,
            tanggal TEXT,
            atas_nama TEXT,
            nomor_rekening TEXT,
            bank TEXT,
            pos TEXT,
            kategori TEXT DEFAULT 'tagihan',
            upload_id INTEGER,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            pos TEXT,
            periode TEXT,
            record_count INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add pos column if upgrading old database
    try:
        c.execute("ALTER TABLE tagihan ADD COLUMN pos TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE tagihan ADD COLUMN upload_id INTEGER")
    except:
        pass
    try:
        c.execute("ALTER TABLE tagihan ADD COLUMN kategori TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE tagihan ADD COLUMN nota_path TEXT")
    except:
        pass
    for col in ("pict_path", "bukti_path", "ket"):
        try:
            c.execute(f"ALTER TABLE tagihan ADD COLUMN {col} TEXT")
        except:
            pass
    for col, typedef in [
        ("debit", "INTEGER DEFAULT 0"),
        ("kredit", "INTEGER DEFAULT 0"),
        ("saldo_akhir", "INTEGER"),
        ("tipe_transaksi", "TEXT"),
        ("approved_by", "INTEGER"),
        ("approved_at", "TEXT"),
        ("rejected_by", "INTEGER"),
        ("rejected_at", "TEXT"),
        ("rejection_note", "TEXT"),
        ("paid_by", "INTEGER"),
        ("paid_at", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE tagihan ADD COLUMN {col} {typedef}")
        except:
            pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER UNIQUE,
            nama_karyawan TEXT,
            divisi TEXT,
            saldo_awal INTEGER DEFAULT 0,
            sisa_dana INTEGER DEFAULT 0,
            total_digantikan INTEGER DEFAULT 0,
            payment_info TEXT,
            bank TEXT,
            nomor_rekening TEXT,
            atas_nama TEXT,
            periode TEXT,
            filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for col, typedef in [
        ("report_type", "TEXT DEFAULT 'reimbursement'"),
        ("total_debit", "INTEGER DEFAULT 0"),
        ("total_kredit", "INTEGER DEFAULT 0"),
        ("saldo_akhir", "INTEGER DEFAULT 0"),
        ("yang_menyetujui", "TEXT"),
        ("tanggal_ttd_pemohon", "TEXT"),
        ("tanggal_ttd_menyetujui", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE petty_cash_laporan ADD COLUMN {col} {typedef}")
        except:
            pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS gaji_relawan_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER UNIQUE,
            tanggal_pembayaran TEXT,
            rekening_sumber TEXT,
            jumlah_penerima INTEGER DEFAULT 0,
            total_gaji INTEGER DEFAULT 0,
            periode TEXT,
            bank TEXT DEFAULT 'MANDIRI',
            kota TEXT,
            filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS insentif_pic_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER UNIQUE,
            tanggal_pembayaran TEXT,
            rekening_sumber TEXT,
            jumlah_penerima INTEGER DEFAULT 0,
            total_gaji INTEGER DEFAULT 0,
            periode TEXT,
            bank TEXT DEFAULT 'MANDIRI',
            kota TEXT,
            filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS insentif_mitra_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER UNIQUE,
            tanggal_pembayaran TEXT,
            rekening_sumber TEXT,
            jumlah_penerima INTEGER DEFAULT 0,
            total_gaji INTEGER DEFAULT 0,
            periode TEXT,
            bank TEXT DEFAULT 'MANDIRI',
            kota TEXT,
            filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pengembalian_dana_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER UNIQUE,
            tanggal_pembayaran TEXT,
            rekening_sumber TEXT,
            jumlah_penerima INTEGER DEFAULT 0,
            total_gaji INTEGER DEFAULT 0,
            periode TEXT,
            bank TEXT DEFAULT 'MANDIRI',
            kota TEXT,
            filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pengajuan_dana_mitra_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER UNIQUE,
            tanggal_pembayaran TEXT,
            rekening_sumber TEXT,
            jumlah_penerima INTEGER DEFAULT 0,
            total_gaji INTEGER DEFAULT 0,
            periode TEXT,
            bank TEXT DEFAULT 'MANDIRI',
            kota TEXT,
            filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER NOT NULL,
            no TEXT,
            pengajuan TEXT NOT NULL,
            jumlah INTEGER DEFAULT 0,
            debit INTEGER DEFAULT 0,
            kredit INTEGER DEFAULT 0,
            saldo_akhir INTEGER,
            tipe_transaksi TEXT,
            tanggal TEXT,
            nota_path TEXT,
            ket TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        c.execute("ALTER TABLE petty_cash_items ADD COLUMN ket TEXT")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE petty_cash_items ADD COLUMN status TEXT DEFAULT 'DIAJUKAN'")
    except Exception:
        pass

    def _insert_user_if_missing(username: str, password: str, full_name: str, role: str) -> None:
        if c.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
            return
        c.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            (username, pbkdf2_sha256.hash(password), full_name, role),
        )

    c.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_by INTEGER,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipe TEXT NOT NULL,
            nama TEXT NOT NULL,
            no TEXT,
            atas_nama TEXT,
            nomor_rekening TEXT,
            bank TEXT,
            pos TEXT,
            aktif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS bgn_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            keterangan TEXT NOT NULL,
            jumlah INTEGER NOT NULL,
            no_referensi TEXT,
            periode TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ka_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tagihan_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            read_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        c.execute("UPDATE tagihan SET status = 'LUNAS' WHERE status IN ('DIBAYARKAN', 'TERBAYAR')")
    except Exception:
        pass

    # Seed users hanya saat tabel kosong — tidak menimpa password yang sudah ada.
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        default_users = [
            ("swhm", "A0312", "Adam Primaskoro", "admin"),
            ("admin", "admin123", "Admin Keuangan", "admin"),
            ("icha", "sppg123", "Icha Salsabila", "member"),
            ("ulil", "swh123", "Moch. Ulil Amri", "viewer"),
            ("wisma", "a123", "Bapak Herman", "viewer"),
            ("ka_sppg", "ka123", "Kepala SPPG", "ka_sppg"),
            ("maker", "maker123", "Maker Pembayaran VA", "maker"),
        ]
        for u, p, name, role in default_users:
            _insert_user_if_missing(u, p, name, role)
    else:
        if c.execute("SELECT id FROM users WHERE username = 'icha'").fetchone() is None:
            if c.execute("SELECT id FROM users WHERE username = 'member'").fetchone():
                c.execute(
                    "UPDATE users SET username = 'icha', full_name = 'Icha Salsabila', role = 'member' WHERE username = 'member'",
                )
            else:
                _insert_user_if_missing("icha", "sppg123", "Icha Salsabila", "member")
        _insert_user_if_missing("ulil", "swh123", "Moch. Ulil Amri", "viewer")
        _insert_user_if_missing("wisma", "a123", "Bapak Herman", "viewer")
        _insert_user_if_missing("ka_sppg", "ka123", "Kepala SPPG", "ka_sppg")
        _insert_user_if_missing("maker", "maker123", "Maker Pembayaran VA", "maker")

    conn.commit()
    conn.close()


def seed_initial_tagihan():
    """No longer auto-seeds demo data."""
    pass


def migrate_petty_cash_from_tagihan():
    """Pindahkan data petty cash lama dari tabel tagihan ke tabel terpisah."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM petty_cash_items")
    if c.fetchone()[0] > 0:
        conn.close()
        return
    rows = c.execute(
        "SELECT * FROM tagihan WHERE kategori = 'petty_cash' ORDER BY id"
    ).fetchall()
    for r in rows:
        c.execute("""
            INSERT INTO petty_cash_items
            (upload_id, no, pengajuan, jumlah, debit, kredit, saldo_akhir, tipe_transaksi, tanggal, nota_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["upload_id"] or 0,
            r["no"],
            r["pengajuan"],
            r["jumlah"],
            r["debit"] if "debit" in r.keys() else 0,
            r["kredit"] if "kredit" in r.keys() else 0,
            r["saldo_akhir"] if "saldo_akhir" in r.keys() else None,
            r["tipe_transaksi"] if "tipe_transaksi" in r.keys() else None,
            r["tanggal"],
            r["nota_path"] if "nota_path" in r.keys() else None,
            r["created_at"],
        ))
    if rows:
        c.execute("DELETE FROM tagihan WHERE kategori = 'petty_cash'")
    conn.commit()
    conn.close()
