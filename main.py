#!/usr/bin/env python3
"""
Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun
Web app untuk pelaporan tagihan mitra (Maker SPPG)
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic
from starlette.middleware.sessions import SessionMiddleware
from passlib.hash import pbkdf2_sha256
from itsdangerous import URLSafeTimedSerializer, BadSignature
from dateutil import parser as date_parser

from db import get_db, db_info

# Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = os.getenv("VERCEL") == "1"
PUBLIC_APP_URL = os.getenv(
    "PUBLIC_APP_URL",
    "https://adm-swh.vercel.app" if IS_VERCEL else "http://localhost:8001",
).rstrip("/")
PUBLIC_LOGIN_URL = f"{PUBLIC_APP_URL}/login"
SECRET_KEY = os.getenv("SECRET_KEY", "sppg-wisma-haji-madiun-2026-super-secret-key-change-in-prod")
SESSION_COOKIE_NAME = "sppg_session"

# Auth (using pbkdf2 for better compatibility)
serializer = URLSafeTimedSerializer(SECRET_KEY)

# FastAPI
app = FastAPI(title="Pelaporan Keuangan SPPG Wisma Haji", version="1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=IS_VERCEL,
)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
# Vercel + Jinja2 3.x: nonaktifkan cache template (hindari TypeError unhashable dict)
templates.env.cache_size = 0
templates.env.cache = None
templates.env.auto_reload = True

# Static & uploads: di Vercel disajikan dari public/ oleh CDN
if not IS_VERCEL:
    if os.path.exists(os.path.join(BASE_DIR, "static")):
        app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
    _local_uploads = os.path.join(BASE_DIR, "uploads")
    if os.path.exists(_local_uploads):
        app.mount("/uploads", StaticFiles(directory=_local_uploads), name="uploads")

UPLOAD_DIR = "/tmp/sppg-uploads" if IS_VERCEL else os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "nota"), exist_ok=True)


@app.exception_handler(HTTPException)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    """Redirect ke login saat belum auth — hindari respons JSON {"detail":"Found"}."""
    if exc.status_code in (301, 302, 303, 307, 308):
        location = (exc.headers or {}).get("Location")
        if location:
            return RedirectResponse(url=location, status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# ===================== DATABASE =====================

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
            role TEXT DEFAULT 'user'
        )
    """)

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
    for col, typedef in [
        ("debit", "INTEGER DEFAULT 0"),
        ("kredit", "INTEGER DEFAULT 0"),
        ("saldo_akhir", "INTEGER"),
        ("tipe_transaksi", "TEXT"),
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

    # Seed users if empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        default_users = [
            ("swhm", "A0312", "Maker SWH", "admin"),
            ("admin", "sppg123", "Admin Keuangan", "admin"),  # backup
        ]
        for u, p, name, role in default_users:
            ph = pbkdf2_sha256.hash(p)
            c.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
                (u, ph, name, role)
            )

    c.execute(
        "UPDATE users SET password_hash = ? WHERE username = 'swhm'",
        (pbkdf2_sha256.hash("A0312"),),
    )

    conn.commit()
    conn.close()

def seed_initial_tagihan():
    """No longer auto-seeds demo data. User starts with empty data."""
    # Data is now empty by default. User will add/upload fresh data with proper categories.
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

init_db()
migrate_petty_cash_from_tagihan()
seed_initial_tagihan()

# ===================== HELPERS =====================

def format_rupiah(amount: int) -> str:
    if amount is None:
        return "Rp0"
    if amount < 0:
        return "-Rp" + f"{abs(amount):,.0f}".replace(",", ".")
    return "Rp" + f"{amount:,.0f}".replace(",", ".")

ID_MONTH_NAMES = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def format_tanggal_display(tgl_str: str) -> str:
    """Format tanggal: Tanggal - Bulan(huruf) - Tahun(angka), contoh 11 - Juni - 2026."""
    if not tgl_str:
        return "—"
    raw = tgl_str.strip()
    iso = raw if len(raw) == 10 and raw[4] == "-" and raw[7] == "-" else _parse_id_date(raw)
    if not iso:
        return tgl_str
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        bulan = ID_MONTH_NAMES[dt.month] if 1 <= dt.month <= 12 else str(dt.month)
        return f"{dt.day} - {bulan} - {dt.year}"
    except Exception:
        return tgl_str

def _parse_slash_date(tgl_str: str) -> Optional[str]:
    """Parse tanggal format M/D/YYYY dari tanda tangan PDF, contoh 6/10/2026."""
    if not tgl_str:
        return None
    raw = tgl_str.strip()
    for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_id_date(tgl_str: str) -> Optional[str]:
    if not tgl_str:
        return None
    import re
    norm = tgl_str.strip().lower()
    for indo, eng in [
        ("januari", "jan"), ("februari", "feb"), ("maret", "mar"), ("april", "apr"),
        ("mei", "may"), ("juni", "jun"), ("juli", "jul"), ("agustus", "aug"),
        ("september", "sep"), ("oktober", "oct"), ("november", "nov"), ("desember", "dec"),
    ]:
        norm = re.sub(r"\b" + indo + r"\b", eng, norm)
    try:
        dt = date_parser.parse(norm, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def _parse_rp_amount(text: str) -> int:
    import re
    m = re.search(r"Rp\s*([\d.,]+)", text)
    if not m:
        return 0
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except ValueError:
        return 0

def get_petty_cash_laporans() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, u.record_count, u.created_at as upload_at
        FROM petty_cash_laporan p
        LEFT JOIN uploads u ON u.id = p.upload_id
        ORDER BY p.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_petty_cash_items(upload_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM petty_cash_items
        WHERE upload_id = ?
        ORDER BY id ASC
    """, (upload_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def filter_petty_cash_items(
    items: List[Dict[str, Any]],
    search: str = "",
    tanggal: str = "",
    jenis: str = "",
) -> List[Dict[str, Any]]:
    """Filter petty cash rows by search, date, and transaction type."""
    result = items
    jenis = (jenis or "").strip().lower()
    if jenis == "pemasukan":
        result = [i for i in result if (i.get("debit") or 0) > 0]
    elif jenis == "pengeluaran":
        result = [
            i for i in result
            if (i.get("kredit") or 0) > 0
            or ((i.get("debit") or 0) == 0 and (i.get("jumlah") or 0) > 0)
        ]
    if tanggal:
        result = [i for i in result if (i.get("tanggal") or "") == tanggal]
    if search:
        s = search.strip().lower()
        result = [
            i for i in result
            if s in (i.get("pengajuan") or "").lower()
            or s in (i.get("tipe_transaksi") or "").lower()
        ]
    return result

def get_current_user(request: Request):
    """Ambil user dari session middleware saja — hindari konflik cookie ganda."""
    try:
        data = request.session.get("user")
        if not data or not data.get("user_id"):
            return None
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (data["user_id"],)).fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception:
        return None


PORTAL_MODULES = [
    {"href": "/dashboard", "icon": "fa-chart-line", "title": "Dashboard", "desc": "Ringkasan keuangan"},
    {"href": "/tagihan", "icon": "fa-file-invoice-dollar", "title": "Laporan Tagihan", "desc": "Data tagihan mitra"},
    {"href": "/petty-cash", "icon": "fa-wallet", "title": "Petty Cash", "desc": "Buku besar & reimbursement"},
    {"href": "/insentif-mitra", "icon": "fa-handshake", "title": "Laporan Insentif Mitra", "desc": "Pembayaran insentif mitra"},
    {"href": "/pengembalian-dana", "icon": "fa-rotate-left", "title": "Pengembalian Dana", "desc": "Pengembalian dana / refund"},
    {"href": "/pengajuan-dana-mitra", "icon": "fa-file-invoice", "title": "Pengajuan Dana Mitra", "desc": "Pengajuan dana mitra SPPG"},
    {"href": "/gaji-relawan", "icon": "fa-users", "title": "Gaji Relawan", "desc": "Pembayaran relawan"},
    {"href": "/insentif-pic", "icon": "fa-user-tie", "title": "Insentif PIC", "desc": "Pembayaran insentif PIC"},
]


def render_template(request: Request, name: str, context: Dict = None, status_code: int = 200):
    """Starlette baru: TemplateResponse(request, name, context)."""
    ctx = {k: v for k, v in (context or {}).items() if k != "request"}
    ctx.setdefault("public_app_url", PUBLIC_APP_URL)
    ctx.setdefault("public_login_url", PUBLIC_LOGIN_URL)
    ctx.setdefault("is_vercel", IS_VERCEL)
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def _login_context(**extra):
    return {
        "portal_modules": PORTAL_MODULES,
        "is_vercel": IS_VERCEL,
        "public_app_url": PUBLIC_APP_URL,
        "public_login_url": PUBLIC_LOGIN_URL,
        **extra,
    }


def _safe_next_url(next_url: str) -> str:
    """Hanya izinkan redirect internal."""
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/dashboard"
    if next_url.startswith("/login") or next_url.startswith("/logout"):
        return "/dashboard"
    return next_url


def require_login(request: Request):
    user = get_current_user(request)
    if not user:
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        from urllib.parse import quote
        location = f"/login?next={quote(next_path, safe='')}"
        raise HTTPException(status_code=302, headers={"Location": location})
    return user

def get_all_tagihan(filters: Dict = None) -> List[Dict]:
    conn = get_db()
    query = "SELECT * FROM tagihan"
    params = []
    where = []
    if filters and filters.get("kategori"):
        where.append("kategori = ?")
        params.append(filters["kategori"])
    else:
        where.append("(kategori IS NULL OR kategori = '' OR kategori = 'tagihan')")

    if filters:
        if filters.get("search"):
            where.append("(pengajuan LIKE ? OR atas_nama LIKE ? OR bank LIKE ?)")
            s = f"%{filters['search']}%"
            params.extend([s, s, s])
        if filters.get("status"):
            where.append("status = ?")
            params.append(filters["status"])
        if filters.get("rekening"):
            where.append("rekening = ?")
            params.append(filters["rekening"])
        if filters.get("tanggal"):
            where.append("tanggal = ?")
            params.append(filters["tanggal"])
        if filters.get("upload_id"):
            where.append("upload_id = ?")
            params.append(filters["upload_id"])

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY COALESCE(tanggal, '9999-12-31') DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_summary() -> Dict[str, Any]:
    conn = get_db()
    c = conn.cursor()
    exclude_pc = "WHERE (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')"

    # Total keseluruhan (tanpa petty cash)
    c.execute(f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan {exclude_pc}")
    total = c.fetchone()[0] or 0

    c.execute(f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan {exclude_pc} AND status = 'TERBAYAR'")
    terbayar = c.fetchone()[0] or 0

    c.execute(f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan {exclude_pc} AND status = 'DIAJUKAN'")
    diajukan = c.fetchone()[0] or 0

    c.execute(f"SELECT COUNT(*) FROM tagihan {exclude_pc}")
    jumlah_item = c.fetchone()[0] or 0

    # By rekening
    c.execute(f"""
        SELECT COALESCE(rekening, 'Belum Ditentukan') as r, COALESCE(SUM(jumlah),0) 
        FROM tagihan {exclude_pc} GROUP BY r ORDER BY 2 DESC
    """)
    by_rekening = [{"rekening": r[0], "total": r[1]} for r in c.fetchall()]

    # By status counts
    c.execute(f"SELECT status, COUNT(*), COALESCE(SUM(jumlah),0) FROM tagihan {exclude_pc} GROUP BY status")
    by_status = [{"status": r[0] or "Belum Ada Status", "count": r[1], "total": r[2]} for r in c.fetchall()]

    conn.close()

    return {
        "total": total,
        "terbayar": terbayar,
        "diajukan": diajukan,
        "jumlah_item": jumlah_item,
        "by_rekening": by_rekening,
        "by_status": by_status,
    }

# ===================== ROUTES =====================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")

@app.get("/masuk", response_class=HTMLResponse)
async def masuk_redirect(request: Request, next: str = ""):
    target = f"/login?next={next}" if next else "/login"
    return RedirectResponse(target, status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "", message: str = "", error: str = ""):
    if message:
        qs = f"?next={next}" if next else ""
        return RedirectResponse(f"/login{qs}", status_code=303)
    user = get_current_user(request)
    return render_template(request, "login.html", _login_context(
        user=user,
        error=error or None,
        message=None,
        next_url=_safe_next_url(next),
    ))


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/dashboard"),
):
    username = username.strip()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not pbkdf2_sha256.verify(password, user["password_hash"]):
        return render_template(request, "login.html", _login_context(
            user=None,
            error="Username atau password salah. Periksa kembali lalu coba lagi.",
            message=None,
            next_url=_safe_next_url(next),
            username_value=username,
        ), status_code=401)

    request.session.clear()
    request.session["user"] = {
        "user_id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
    }

    return RedirectResponse(_safe_next_url(next), status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_login)):
    summary = get_summary()
    recent = get_all_tagihan()[:6]

    # Monthly breakdown for chart (last 6 months)
    conn = get_db()
    monthly = conn.execute("""
        SELECT 
            strftime('%Y-%m', COALESCE(tanggal, created_at)) as bulan,
            COALESCE(SUM(jumlah), 0) as total
        FROM tagihan
        WHERE (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')
        GROUP BY bulan
        ORDER BY bulan DESC
        LIMIT 6
    """).fetchall()
    conn.close()

    monthly_data = [{"bulan": m[0], "total": m[1]} for m in reversed(monthly)]

    return render_template(request, "dashboard.html", {
        "user": user,
        "summary": summary,
        "recent": recent,
        "monthly": monthly_data,
        "format_rupiah": format_rupiah,
        "today": date.today().isoformat(),
    })

@app.get("/tagihan", response_class=HTMLResponse)
async def tagihan_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    kategori: str = "",
    message: str = "",
    success: bool = False
):
    if kategori == "petty_cash":
        return RedirectResponse("/petty-cash", status_code=303)
    if kategori == "gaji_relawan":
        return RedirectResponse("/gaji-relawan", status_code=303)
    if kategori == "insentif_pic":
        return RedirectResponse("/insentif-pic", status_code=303)
    if kategori == "insentif_mitra":
        return RedirectResponse("/insentif-mitra", status_code=303)
    if kategori == "pengembalian_dana":
        return RedirectResponse("/pengembalian-dana", status_code=303)
    if kategori == "pengajuan_dana_mitra":
        return RedirectResponse("/pengajuan-dana-mitra", status_code=303)
    if kategori in ("pic", "tagihan_bulanan"):
        return RedirectResponse("/tagihan", status_code=303)

    filters = {}
    if search: filters["search"] = search
    if status: filters["status"] = status
    if rekening: filters["rekening"] = rekening
    if tanggal: filters["tanggal"] = tanggal
    if kategori: filters["kategori"] = kategori

    data = get_all_tagihan(filters)

    # Compute main status automatically based on current filtered data
    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() == "TERBAYAR" for item in data)
        main_status = "Sukses" if all_terbayar else "Tertagih"

    # Get filter options
    conn = get_db()
    pc_exclude = "AND (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')"
    statuses = [r[0] for r in conn.execute(f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL {pc_exclude}").fetchall()]
    rekenings = [r[0] for r in conn.execute(f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL {pc_exclude}").fetchall()]
    kategori_list = []
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)

    return render_template(request, "tagihan.html", {
        "user": user,
        "tagihan": data,
        "total_filtered": total_filtered,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "filters": {"search": search, "status": status, "rekening": rekening, "tanggal": tanggal, "kategori": kategori},
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "kategori_options": sorted([k for k in kategori_list if k]),
        "message": message,
        "success": success,
    })

FEE_PAYROL_PER_ORANG = 2500
INSENTIF_MITRA_PER_HARI = 6_000_000
INSENTIF_MITRA_HARI = 6
INSENTIF_MITRA_JUMLAH = INSENTIF_MITRA_PER_HARI * INSENTIF_MITRA_HARI
PENGEMBALIAN_DANA_PER_HARI = 6_000_000
PENGEMBALIAN_DANA_HARI = 6
PENGEMBALIAN_DANA_JUMLAH = PENGEMBALIAN_DANA_PER_HARI * PENGEMBALIAN_DANA_HARI


def _sort_key_no(item: Dict) -> int:
    try:
        raw = str(item.get("no") or "").strip()
        return int(raw) if raw else 999_999
    except (ValueError, TypeError):
        return 999_999


def get_gaji_relawan(filters: Dict = None) -> List[Dict]:
    f = dict(filters or {})
    f["kategori"] = "gaji_relawan"
    rows = get_all_tagihan(f)
    return sorted(rows, key=_sort_key_no)


def calc_fee_payrol(item_count: int) -> int:
    return FEE_PAYROL_PER_ORANG * max(item_count, 0)


def get_gaji_relawan_laporans(active_only: bool = False) -> List[Dict[str, Any]]:
    """Daftar laporan gaji relawan. active_only=True: hanya upload yang masih punya data."""
    conn = get_db()
    query = """
        SELECT g.*, u.record_count, u.created_at AS upload_at,
               (SELECT COUNT(*) FROM tagihan t
                WHERE t.upload_id = g.upload_id AND t.kategori = 'gaji_relawan') AS item_count
        FROM gaji_relawan_laporan g
        LEFT JOIN uploads u ON u.id = g.upload_id
    """
    if active_only:
        query += """
        WHERE EXISTS (
            SELECT 1 FROM tagihan t
            WHERE t.upload_id = g.upload_id AND t.kategori = 'gaji_relawan'
        )
        """
    query += " ORDER BY g.id DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recalc_gaji_relawan_laporan(conn, upload_id: int):
    """Hitung ulang total laporan setelah hapus baris — metadata upload tetap ada."""
    if not upload_id:
        return
    rows = conn.execute(
        "SELECT jumlah FROM tagihan WHERE upload_id = ? AND kategori = 'gaji_relawan'",
        (upload_id,),
    ).fetchall()
    count = len(rows)
    total = sum(r[0] or 0 for r in rows)
    if count == 0:
        conn.execute("DELETE FROM gaji_relawan_laporan WHERE upload_id = ?", (upload_id,))
    else:
        conn.execute("""
            UPDATE gaji_relawan_laporan SET jumlah_penerima = ?, total_gaji = ?
            WHERE upload_id = ?
        """, (count, total, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (count, upload_id))


def _strip_nama_gelar(nama: str) -> str:
    """Hilangkan awalan gelar (IBU, BPK, BPA, SDRI, SDR, dll) dari nama relawan."""
    import re
    if not nama:
        return nama
    return re.sub(
        r"^(IBU|BPK|BPA|SDRI|SDR|TN|NY|NN)\.?\s+",
        "",
        nama.strip(),
        flags=re.I,
    ).strip()


def _parse_pic_periode(filename: str) -> Optional[str]:
    import re
    m = re.search(r"PERIODE\s*(\d+)", filename, re.I)
    if m:
        return f"Periode {m.group(1)}"
    m = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", filename.replace("_", " "), re.I)
    if m:
        return m.group(1)
    return None


def _parse_mandiri_csv_date(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return _parse_id_date(raw)


def parse_pic_transfer_csv(file_path: str, filename: str = "", default_label: str = "Gaji Relawan") -> Dict[str, Any]:
    """Parse CSV format transfer massal Mandiri (PIC), contoh CSV PIC PERIODE10."""
    import csv

    meta = {
        "tanggal_pembayaran": None,
        "rekening_sumber": None,
        "jumlah_penerima": 0,
        "total_gaji": 0,
        "periode": _parse_pic_periode(filename),
        "bank": "MANDIRI",
        "kota": "Madiun",
        "filename": filename,
    }
    items = []

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    if not rows:
        return {"meta": meta, "items": items}

    header = rows[0]
    if header and (header[0] or "").strip().upper() == "P":
        meta["tanggal_pembayaran"] = _parse_mandiri_csv_date(header[1] if len(header) > 1 else "")
        meta["rekening_sumber"] = (header[2] if len(header) > 2 else "").strip() or None
        try:
            meta["jumlah_penerima"] = int((header[3] if len(header) > 3 else "0").strip() or 0)
        except ValueError:
            meta["jumlah_penerima"] = 0
        try:
            meta["total_gaji"] = int((header[4] if len(header) > 4 else "0").strip() or 0)
        except ValueError:
            meta["total_gaji"] = 0
        data_rows = rows[1:]
    else:
        data_rows = rows

    for row in data_rows:
        if not row or not any(cell.strip() for cell in row if cell):
            continue
        nomor_rek = (row[0] if len(row) > 0 else "").strip()
        nama = _strip_nama_gelar((row[1] if len(row) > 1 else "").strip())
        if not nama and not nomor_rek:
            continue
        if not nama:
            continue

        try:
            jumlah = int((row[6] if len(row) > 6 else "0").strip().replace(".", "").replace(",", "") or 0)
        except ValueError:
            jumlah = 0
        if jumlah <= 0:
            continue

        bank = (row[11] if len(row) > 11 else "MANDIRI").strip() or "MANDIRI"
        kota = (row[12] if len(row) > 12 else "").strip() or meta.get("kota")
        if kota:
            meta["kota"] = kota

        atas_nama = nama
        periode_label = meta.get("periode") or default_label
        pengajuan = f"{nama} — {periode_label}"

        items.append({
            "no": str(len(items) + 1),
            "pengajuan": pengajuan,
            "atas_nama": atas_nama,
            "nomor_rekening": nomor_rek or None,
            "bank": bank,
            "jumlah": jumlah,
            "tanggal": meta.get("tanggal_pembayaran"),
            "rekening": "TRANSFER MASSAL",
            "status": "DIAJUKAN",
        })

    if items and not meta["total_gaji"]:
        meta["total_gaji"] = sum(i["jumlah"] for i in items)
    if items and not meta["jumlah_penerima"]:
        meta["jumlah_penerima"] = len(items)

    return {"meta": meta, "items": items}


def parse_gaji_relawan_csv(file_path: str, filename: str = "") -> Dict[str, Any]:
    return parse_pic_transfer_csv(file_path, filename, "Gaji Relawan")


def parse_insentif_pic_csv(file_path: str, filename: str = "") -> Dict[str, Any]:
    return parse_pic_transfer_csv(file_path, filename, "Insentif PIC")


def get_insentif_pic(filters: Dict = None) -> List[Dict]:
    f = dict(filters or {})
    f["kategori"] = "insentif_pic"
    rows = get_all_tagihan(f)
    return sorted(rows, key=_sort_key_no)


def get_insentif_pic_laporans(active_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_db()
    query = """
        SELECT g.*, u.record_count, u.created_at AS upload_at,
               (SELECT COUNT(*) FROM tagihan t
                WHERE t.upload_id = g.upload_id AND t.kategori = 'insentif_pic') AS item_count
        FROM insentif_pic_laporan g
        LEFT JOIN uploads u ON u.id = g.upload_id
    """
    if active_only:
        query += """
        WHERE EXISTS (
            SELECT 1 FROM tagihan t
            WHERE t.upload_id = g.upload_id AND t.kategori = 'insentif_pic'
        )
        """
    query += " ORDER BY g.id DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recalc_insentif_pic_laporan(conn, upload_id: int):
    if not upload_id:
        return
    rows = conn.execute(
        "SELECT jumlah FROM tagihan WHERE upload_id = ? AND kategori = 'insentif_pic'",
        (upload_id,),
    ).fetchall()
    count = len(rows)
    total = sum(r[0] or 0 for r in rows)
    if count == 0:
        conn.execute("DELETE FROM insentif_pic_laporan WHERE upload_id = ?", (upload_id,))
    else:
        conn.execute("""
            UPDATE insentif_pic_laporan SET jumlah_penerima = ?, total_gaji = ?
            WHERE upload_id = ?
        """, (count, total, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (count, upload_id))




def parse_insentif_mitra_csv(file_path: str, filename: str = "") -> Dict[str, Any]:
    return parse_pic_transfer_csv(file_path, filename, "Insentif Mitra")


def get_insentif_mitra(filters: Dict = None) -> List[Dict]:
    f = dict(filters or {})
    f["kategori"] = "insentif_mitra"
    rows = get_all_tagihan(f)
    return sorted(rows, key=_sort_key_no)


def get_insentif_mitra_laporans(active_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_db()
    query = """
        SELECT g.*, u.record_count, u.created_at AS upload_at,
               (SELECT COUNT(*) FROM tagihan t
                WHERE t.upload_id = g.upload_id AND t.kategori = 'insentif_mitra') AS item_count
        FROM insentif_mitra_laporan g
        LEFT JOIN uploads u ON u.id = g.upload_id
    """
    if active_only:
        query += """
        WHERE EXISTS (
            SELECT 1 FROM tagihan t
            WHERE t.upload_id = g.upload_id AND t.kategori = 'insentif_mitra'
        )
        """
    query += " ORDER BY g.id DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recalc_insentif_mitra_laporan(conn, upload_id: int):
    if not upload_id:
        return
    rows = conn.execute(
        "SELECT jumlah FROM tagihan WHERE upload_id = ? AND kategori = 'insentif_mitra'",
        (upload_id,),
    ).fetchall()
    count = len(rows)
    total = sum(r[0] or 0 for r in rows)
    if count == 0:
        conn.execute("DELETE FROM insentif_mitra_laporan WHERE upload_id = ?", (upload_id,))
    else:
        conn.execute("""
            UPDATE insentif_mitra_laporan SET jumlah_penerima = ?, total_gaji = ?
            WHERE upload_id = ?
        """, (count, total, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (count, upload_id))


def get_pengembalian_dana(filters: Dict = None) -> List[Dict]:
    f = dict(filters or {})
    f["kategori"] = "pengembalian_dana"
    rows = get_all_tagihan(f)
    return sorted(rows, key=_sort_key_no)


def get_pengembalian_dana_laporans(active_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_db()
    query = """
        SELECT g.*, u.record_count, u.created_at AS upload_at,
               (SELECT COUNT(*) FROM tagihan t
                WHERE t.upload_id = g.upload_id AND t.kategori = 'pengembalian_dana') AS item_count
        FROM pengembalian_dana_laporan g
        LEFT JOIN uploads u ON u.id = g.upload_id
    """
    if active_only:
        query += """
        WHERE EXISTS (
            SELECT 1 FROM tagihan t
            WHERE t.upload_id = g.upload_id AND t.kategori = 'pengembalian_dana'
        )
        """
    query += " ORDER BY g.id DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recalc_pengembalian_dana_laporan(conn, upload_id: int):
    if not upload_id:
        return
    rows = conn.execute(
        "SELECT jumlah FROM tagihan WHERE upload_id = ? AND kategori = 'pengembalian_dana'",
        (upload_id,),
    ).fetchall()
    count = len(rows)
    total = sum(r[0] or 0 for r in rows)
    if count == 0:
        conn.execute("DELETE FROM pengembalian_dana_laporan WHERE upload_id = ?", (upload_id,))
    else:
        conn.execute("""
            UPDATE pengembalian_dana_laporan SET jumlah_penerima = ?, total_gaji = ?
            WHERE upload_id = ?
        """, (count, total, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (count, upload_id))


def get_pengajuan_dana_mitra(filters: Dict = None) -> List[Dict]:
    f = dict(filters or {})
    f["kategori"] = "pengajuan_dana_mitra"
    rows = get_all_tagihan(f)
    return sorted(rows, key=_sort_key_no)


def get_pengajuan_dana_mitra_laporans(active_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_db()
    query = """
        SELECT g.*, u.record_count, u.created_at AS upload_at,
               (SELECT COUNT(*) FROM tagihan t
                WHERE t.upload_id = g.upload_id AND t.kategori = 'pengajuan_dana_mitra') AS item_count
        FROM pengajuan_dana_mitra_laporan g
        LEFT JOIN uploads u ON u.id = g.upload_id
    """
    if active_only:
        query += """
        WHERE EXISTS (
            SELECT 1 FROM tagihan t
            WHERE t.upload_id = g.upload_id AND t.kategori = 'pengajuan_dana_mitra'
        )
        """
    query += " ORDER BY g.id DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recalc_pengajuan_dana_mitra_laporan(conn, upload_id: int):
    if not upload_id:
        return
    rows = conn.execute(
        "SELECT jumlah FROM tagihan WHERE upload_id = ? AND kategori = 'pengajuan_dana_mitra'",
        (upload_id,),
    ).fetchall()
    count = len(rows)
    total = sum(r[0] or 0 for r in rows)
    if count == 0:
        conn.execute("DELETE FROM pengajuan_dana_mitra_laporan WHERE upload_id = ?", (upload_id,))
    else:
        conn.execute("""
            UPDATE pengajuan_dana_mitra_laporan SET jumlah_penerima = ?, total_gaji = ?
            WHERE upload_id = ?
        """, (count, total, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (count, upload_id))


@app.get("/gaji-relawan", response_class=HTMLResponse)
async def gaji_relawan_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    message: str = "",
    success: bool = False,
):
    periode_options = get_gaji_relawan_laporans(active_only=True)
    laporans = periode_options
    laporan = None
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    filters = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

    view_all = upload_id == 0

    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_gaji_relawan(filters)

    periode_map = {lap["upload_id"]: lap.get("periode") or lap.get("filename") for lap in laporans}
    for item in data:
        uid = item.get("upload_id")
        item["periode_label"] = periode_map.get(uid, "Input Manual") if uid else "Input Manual"

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() == "TERBAYAR" for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    gr_filter = "kategori = 'gaji_relawan'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {gr_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {gr_filter}"
        ).fetchall()
    ]
    conn.close()

    for item in data:
        item["fee_payrol"] = FEE_PAYROL_PER_ORANG
        item["total_bayar"] = (item.get("jumlah") or 0) + FEE_PAYROL_PER_ORANG

    total_filtered = sum(d["jumlah"] for d in data)
    total_fee_payrol = calc_fee_payrol(len(data))
    total_grand = total_filtered + total_fee_payrol
    avg_gaji = int(total_filtered / len(data)) if data else 0
    max_item = max(data, key=lambda x: x["jumlah"]) if data else None
    min_item = min(data, key=lambda x: x["jumlah"]) if data else None
    total_all_batches = sum(lap.get("total_gaji") or 0 for lap in laporans)
    total_all_relawan = sum(lap.get("jumlah_penerima") or lap.get("record_count") or 0 for lap in laporans)

    return render_template(request, "gaji_relawan.html", {
        "user": user,
        "items": data,
        "laporans": laporans,
        "laporan": laporan,
        "view_all": view_all,
        "selected_upload_id": upload_id if upload_id else 0,
        "total_filtered": total_filtered,
        "total_fee_payrol": total_fee_payrol,
        "total_grand": total_grand,
        "fee_payrol_amount": FEE_PAYROL_PER_ORANG,
        "total_all_batches": total_all_batches,
        "total_all_relawan": total_all_relawan,
        "avg_gaji": avg_gaji,
        "max_item": max_item,
        "min_item": min_item,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {"search": search, "status": status, "rekening": rekening, "tanggal": tanggal, "periode": upload_id},
        "periode_options": periode_options,
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "message": message,
        "success": success,
    })


@app.post("/gaji-relawan/upload")
async def gaji_relawan_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    """Upload CSV PIC / Excel daftar gaji relawan — format transfer massal Mandiri."""
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""

    conn = get_db()
    conn.execute(
        "INSERT INTO uploads (filename, created_by) VALUES (?, ?)",
        (file.filename, user["id"]),
    )
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        if ext == "csv":
            parsed = parse_gaji_relawan_csv(file_path, file.filename)
        else:
            parsed = parse_upload_file(file_path, file.filename, "gaji_relawan", upload_id)
            if isinstance(parsed, list):
                meta = {"periode": _parse_pic_periode(file.filename), "filename": file.filename}
                items = []
                for idx, row in enumerate(parsed, start=1):
                    nama = (
                        row.get("nama") or row.get("atas_nama") or row.get("atas nama")
                        or row.get("pengajuan") or row.get("nama relawan") or ""
                    )
                    if isinstance(nama, str):
                        nama = _strip_nama_gelar(nama.strip())
                    if not nama:
                        continue
                    try:
                        jumlah = int(float(row.get("jumlah") or row.get("total") or row.get("gaji") or 0))
                    except (TypeError, ValueError):
                        jumlah = 0
                    if jumlah <= 0:
                        continue
                    periode_label = meta.get("periode") or "Gaji Relawan"
                    items.append({
                        "no": str(idx),
                        "pengajuan": f"{nama} — {periode_label}",
                        "atas_nama": nama,
                        "nomor_rekening": str(row.get("nomor_rekening") or row.get("nomor rekening") or row.get("no rekening") or "").strip() or None,
                        "bank": str(row.get("bank") or "MANDIRI").strip(),
                        "jumlah": jumlah,
                        "tanggal": str(row.get("tanggal") or "").strip() or None,
                        "rekening": "TRANSFER MASSAL",
                        "status": "DIAJUKAN",
                    })
                parsed = {"meta": meta, "items": items}
    except Exception as e:
        conn.close()
        return RedirectResponse(f"/gaji-relawan?message=Error parsing file: {str(e)}", status_code=303)

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []
    gr_meta = parsed.get("meta", {}) if isinstance(parsed, dict) else {}

    if not item_list:
        conn.close()
        return RedirectResponse("/gaji-relawan?message=Tidak ada data yang bisa dibaca dari file", status_code=303)

    inserted = 0
    for item in item_list:
        pengajuan = item.get("pengajuan") or item.get("atas_nama") or ""
        if not pengajuan:
            continue
        jumlah = int(item.get("jumlah") or 0)
        if jumlah <= 0:
            continue

        dup = conn.execute("""
            SELECT 1 FROM tagihan
            WHERE upload_id = ? AND pengajuan = ? AND jumlah = ?
            LIMIT 1
        """, (upload_id, pengajuan, jumlah)).fetchone()
        if dup:
            continue

        conn.execute("""
            INSERT INTO tagihan
            (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, upload_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'gaji_relawan', ?, ?)
        """, (
            item.get("no"),
            pengajuan,
            jumlah,
            item.get("status") or "DIAJUKAN",
            item.get("rekening") or "TRANSFER MASSAL",
            item.get("tanggal") or gr_meta.get("tanggal_pembayaran"),
            item.get("atas_nama"),
            item.get("nomor_rekening"),
            item.get("bank"),
            upload_id,
            user["id"],
        ))
        inserted += 1

    conn.execute("""
        INSERT OR REPLACE INTO gaji_relawan_laporan
        (upload_id, tanggal_pembayaran, rekening_sumber, jumlah_penerima, total_gaji,
         periode, bank, kota, filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        upload_id,
        gr_meta.get("tanggal_pembayaran"),
        gr_meta.get("rekening_sumber"),
        gr_meta.get("jumlah_penerima") or inserted,
        gr_meta.get("total_gaji") or sum(i.get("jumlah", 0) for i in item_list),
        gr_meta.get("periode"),
        gr_meta.get("bank") or "MANDIRI",
        gr_meta.get("kota"),
        file.filename,
    ))
    conn.execute("UPDATE uploads SET record_count = ?, periode = ? WHERE id = ?",
                 (inserted, gr_meta.get("periode"), upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} data gaji relawan"
    if gr_meta.get("periode"):
        msg += f" ({gr_meta['periode']})"
    return RedirectResponse(f"/gaji-relawan?message={msg}&success=true", status_code=303)


@app.post("/gaji-relawan")
async def create_gaji_relawan(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'gaji_relawan', ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/gaji-relawan", status_code=303)


@app.post("/gaji-relawan/{item_id}/update")
async def update_gaji_relawan(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = 'gaji_relawan', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'gaji_relawan'
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/gaji-relawan", status_code=303)


@app.post("/gaji-relawan/{item_id}/delete")
async def delete_gaji_relawan(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'gaji_relawan'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'gaji_relawan'", (item_id,))
    if row and row[0]:
        recalc_gaji_relawan_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/gaji-relawan", status_code=303)


@app.post("/api/gaji-relawan/bulk-delete")
async def api_gaji_relawan_bulk_delete(request: Request, user=Depends(require_login)):
    """Hapus baris terpilih saja — upload & data periode lain tidak ikut terhapus."""
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"""SELECT DISTINCT upload_id FROM tagihan
                WHERE id IN ({placeholders}) AND kategori = 'gaji_relawan' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'gaji_relawan'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_gaji_relawan_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/gaji-relawan/bulk-update")
async def api_gaji_relawan_bulk_update(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"""UPDATE tagihan SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND kategori = 'gaji_relawan'""",
            [status] + ids,
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/export/gaji-relawan/csv")
async def export_gaji_relawan_csv(user=Depends(require_login)):
    import csv
    from io import StringIO

    data = get_gaji_relawan()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NO", "NAMA / KETERANGAN", "JUMLAH", "FEE PAYROL", "TOTAL", "STATUS", "REKENING", "TANGGAL", "ATAS NAMA REK.", "NOMOR REKENING", "BANK"])
    for d in data:
        fee = FEE_PAYROL_PER_ORANG
        writer.writerow([
            d["no"] or "",
            d["pengajuan"],
            d["jumlah"],
            fee,
            (d["jumlah"] or 0) + fee,
            d["status"] or "",
            d["rekening"] or "",
            d["tanggal"] or "",
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
        ])
    output.seek(0)
    filename = f"gaji_relawan_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/export/gaji-relawan/xlsx")
async def export_gaji_relawan_xlsx(user=Depends(require_login)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    data = get_gaji_relawan()
    wb = Workbook()
    ws = wb.active
    ws.title = "Gaji Relawan"

    header_fill = PatternFill(start_color="071E49", end_color="071E49", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.merge_cells("B1:L1")
    ws["B1"] = "GAJI RELAWAN - SPPG WISMA HAJI MADIUN"
    ws["B1"].font = Font(bold=True, size=14, color="071E49")
    ws["B1"].alignment = Alignment(horizontal="center")

    headers = ["NO", "NAMA / KETERANGAN", "JUMLAH", "FEE PAYROL", "TOTAL", "STATUS", "REKENING", "TANGGAL", "ATAS NAMA REK.", "NOMOR REKENING", "BANK"]
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for idx, d in enumerate(data, start=4):
        fee = FEE_PAYROL_PER_ORANG
        row_data = [
            d["no"] or "",
            d["pengajuan"],
            d["jumlah"],
            fee,
            (d["jumlah"] or 0) + fee,
            d["status"] or "",
            d["rekening"] or "",
            d["tanggal"] or "",
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
        ]
        for col, val in enumerate(row_data, start=2):
            cell = ws.cell(row=idx, column=col, value=val)
            cell.border = thin_border
            if col in (4, 5, 6):
                cell.number_format = "#,##0"
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    widths = [7, 35, 15, 12, 15, 16, 16, 14, 22, 18, 22]
    for i, w in enumerate(widths, start=2):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A4"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"Gaji_Relawan_SPPG_{date.today().isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/insentif-pic", response_class=HTMLResponse)
async def insentif_pic_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    message: str = "",
    success: bool = False,
):
    periode_options = get_insentif_pic_laporans(active_only=True)
    laporans = periode_options
    laporan = None
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    filters = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

    view_all = upload_id == 0

    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_insentif_pic(filters)

    periode_map = {lap["upload_id"]: lap.get("periode") or lap.get("filename") for lap in laporans}
    for item in data:
        uid = item.get("upload_id")
        item["periode_label"] = periode_map.get(uid, "Input Manual") if uid else "Input Manual"

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() == "TERBAYAR" for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    ip_filter = "kategori = 'insentif_pic'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    conn.close()

    for item in data:
        item["fee_payrol"] = FEE_PAYROL_PER_ORANG
        item["total_bayar"] = (item.get("jumlah") or 0) + FEE_PAYROL_PER_ORANG

    total_filtered = sum(d["jumlah"] for d in data)
    total_fee_payrol = calc_fee_payrol(len(data))
    total_grand = total_filtered + total_fee_payrol
    avg_gaji = int(total_filtered / len(data)) if data else 0
    max_item = max(data, key=lambda x: x["jumlah"]) if data else None
    min_item = min(data, key=lambda x: x["jumlah"]) if data else None
    total_all_batches = sum(lap.get("total_gaji") or 0 for lap in laporans)
    total_all_pic = sum(lap.get("jumlah_penerima") or lap.get("record_count") or 0 for lap in laporans)

    return render_template(request, "insentif_pic.html", {
        "user": user,
        "items": data,
        "laporans": laporans,
        "laporan": laporan,
        "view_all": view_all,
        "selected_upload_id": upload_id if upload_id else 0,
        "total_filtered": total_filtered,
        "total_fee_payrol": total_fee_payrol,
        "total_grand": total_grand,
        "fee_payrol_amount": FEE_PAYROL_PER_ORANG,
        "total_all_batches": total_all_batches,
        "total_all_pic": total_all_pic,
        "avg_gaji": avg_gaji,
        "max_item": max_item,
        "min_item": min_item,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {"search": search, "status": status, "rekening": rekening, "tanggal": tanggal, "periode": upload_id},
        "periode_options": periode_options,
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "message": message,
        "success": success,
    })


@app.post("/insentif-pic/upload")
async def insentif_pic_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""

    conn = get_db()
    conn.execute(
        "INSERT INTO uploads (filename, created_by) VALUES (?, ?)",
        (file.filename, user["id"]),
    )
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        if ext == "csv":
            parsed = parse_insentif_pic_csv(file_path, file.filename)
        else:
            parsed = parse_upload_file(file_path, file.filename, "insentif_pic", upload_id)
            if isinstance(parsed, list):
                meta = {"periode": _parse_pic_periode(file.filename), "filename": file.filename}
                items = []
                for idx, row in enumerate(parsed, start=1):
                    nama = (
                        row.get("nama") or row.get("atas_nama") or row.get("atas nama")
                        or row.get("pengajuan") or row.get("nama pic") or ""
                    )
                    if isinstance(nama, str):
                        nama = _strip_nama_gelar(nama.strip())
                    if not nama:
                        continue
                    try:
                        jumlah = int(float(row.get("jumlah") or row.get("total") or row.get("gaji") or 0))
                    except (TypeError, ValueError):
                        jumlah = 0
                    if jumlah <= 0:
                        continue
                    periode_label = meta.get("periode") or "Insentif PIC"
                    items.append({
                        "no": str(idx),
                        "pengajuan": f"{nama} — {periode_label}",
                        "atas_nama": nama,
                        "nomor_rekening": str(row.get("nomor_rekening") or row.get("nomor rekening") or row.get("no rekening") or "").strip() or None,
                        "bank": str(row.get("bank") or "MANDIRI").strip(),
                        "jumlah": jumlah,
                        "tanggal": str(row.get("tanggal") or "").strip() or None,
                        "rekening": "TRANSFER MASSAL",
                        "status": "DIAJUKAN",
                    })
                parsed = {"meta": meta, "items": items}
    except Exception as e:
        conn.close()
        return RedirectResponse(f"/insentif-pic?message=Error parsing file: {str(e)}", status_code=303)

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []
    ip_meta = parsed.get("meta", {}) if isinstance(parsed, dict) else {}

    if not item_list:
        conn.close()
        return RedirectResponse("/insentif-pic?message=Tidak ada data yang bisa dibaca dari file", status_code=303)

    inserted = 0
    for item in item_list:
        pengajuan = item.get("pengajuan") or item.get("atas_nama") or ""
        if not pengajuan:
            continue
        jumlah = int(item.get("jumlah") or 0)
        if jumlah <= 0:
            continue

        dup = conn.execute("""
            SELECT 1 FROM tagihan
            WHERE upload_id = ? AND pengajuan = ? AND jumlah = ?
            LIMIT 1
        """, (upload_id, pengajuan, jumlah)).fetchone()
        if dup:
            continue

        conn.execute("""
            INSERT INTO tagihan
            (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, upload_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_pic', ?, ?)
        """, (
            item.get("no"),
            pengajuan,
            jumlah,
            item.get("status") or "DIAJUKAN",
            item.get("rekening") or "TRANSFER MASSAL",
            item.get("tanggal") or ip_meta.get("tanggal_pembayaran"),
            item.get("atas_nama"),
            item.get("nomor_rekening"),
            item.get("bank"),
            upload_id,
            user["id"],
        ))
        inserted += 1

    conn.execute("""
        INSERT OR REPLACE INTO insentif_pic_laporan
        (upload_id, tanggal_pembayaran, rekening_sumber, jumlah_penerima, total_gaji,
         periode, bank, kota, filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        upload_id,
        ip_meta.get("tanggal_pembayaran"),
        ip_meta.get("rekening_sumber"),
        ip_meta.get("jumlah_penerima") or inserted,
        ip_meta.get("total_gaji") or sum(i.get("jumlah", 0) for i in item_list),
        ip_meta.get("periode"),
        ip_meta.get("bank") or "MANDIRI",
        ip_meta.get("kota"),
        file.filename,
    ))
    conn.execute("UPDATE uploads SET record_count = ?, periode = ? WHERE id = ?",
                 (inserted, ip_meta.get("periode"), upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} data insentif PIC"
    if ip_meta.get("periode"):
        msg += f" ({ip_meta['periode']})"
    return RedirectResponse(f"/insentif-pic?message={msg}&success=true", status_code=303)


@app.post("/insentif-pic")
async def create_insentif_pic(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_pic', ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-pic", status_code=303)


@app.post("/insentif-pic/{item_id}/update")
async def update_insentif_pic(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = 'insentif_pic', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'insentif_pic'
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-pic", status_code=303)


@app.post("/insentif-pic/{item_id}/delete")
async def delete_insentif_pic(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'insentif_pic'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'insentif_pic'", (item_id,))
    if row and row[0]:
        recalc_insentif_pic_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-pic", status_code=303)


@app.post("/api/insentif-pic/bulk-delete")
async def api_insentif_pic_bulk_delete(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"""SELECT DISTINCT upload_id FROM tagihan
                WHERE id IN ({placeholders}) AND kategori = 'insentif_pic' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'insentif_pic'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_insentif_pic_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/insentif-pic/bulk-update")
async def api_insentif_pic_bulk_update(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"""UPDATE tagihan SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND kategori = 'insentif_pic'""",
            [status] + ids,
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/export/insentif-pic/csv")
async def export_insentif_pic_csv(user=Depends(require_login)):
    import csv
    from io import StringIO

    data = get_insentif_pic()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NO", "NAMA / KETERANGAN", "JUMLAH", "FEE PAYROL", "TOTAL", "STATUS", "REKENING", "TANGGAL", "ATAS NAMA REK.", "NOMOR REKENING", "BANK"])
    for d in data:
        fee = FEE_PAYROL_PER_ORANG
        writer.writerow([
            d["no"] or "",
            d["pengajuan"],
            d["jumlah"],
            fee,
            (d["jumlah"] or 0) + fee,
            d["status"] or "",
            d["rekening"] or "",
            d["tanggal"] or "",
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
        ])
    output.seek(0)
    filename = f"insentif_pic_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/export/insentif-pic/xlsx")
async def export_insentif_pic_xlsx(user=Depends(require_login)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    data = get_insentif_pic()
    wb = Workbook()
    ws = wb.active
    ws.title = "Insentif PIC"

    header_fill = PatternFill(start_color="071E49", end_color="071E49", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.merge_cells("B1:L1")
    ws["B1"] = "INSENTIF PIC - SPPG WISMA HAJI MADIUN"
    ws["B1"].font = Font(bold=True, size=14, color="071E49")
    ws["B1"].alignment = Alignment(horizontal="center")

    headers = ["NO", "NAMA / KETERANGAN", "JUMLAH", "FEE PAYROL", "TOTAL", "STATUS", "REKENING", "TANGGAL", "ATAS NAMA REK.", "NOMOR REKENING", "BANK"]
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for idx, d in enumerate(data, start=4):
        fee = FEE_PAYROL_PER_ORANG
        row_data = [
            d["no"] or "",
            d["pengajuan"],
            d["jumlah"],
            fee,
            (d["jumlah"] or 0) + fee,
            d["status"] or "",
            d["rekening"] or "",
            d["tanggal"] or "",
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
        ]
        for col, val in enumerate(row_data, start=2):
            cell = ws.cell(row=idx, column=col, value=val)
            cell.border = thin_border
            if col in (4, 5, 6):
                cell.number_format = "#,##0"
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    widths = [7, 35, 15, 12, 15, 16, 16, 14, 22, 18, 22]
    for i, w in enumerate(widths, start=2):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A4"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"Insentif_PIC_SPPG_{date.today().isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/insentif-mitra", response_class=HTMLResponse)
async def insentif_mitra_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    message: str = "",
    success: bool = False,
):
    periode_options = get_insentif_mitra_laporans(active_only=True)
    laporans = periode_options
    laporan = None
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    filters = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

    view_all = upload_id == 0

    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_insentif_mitra(filters)

    periode_map = {lap["upload_id"]: lap.get("periode") or lap.get("filename") for lap in laporans}
    for item in data:
        uid = item.get("upload_id")
        item["periode_label"] = periode_map.get(uid, "Input Manual") if uid else "Input Manual"

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() == "TERBAYAR" for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    ip_filter = "kategori = 'insentif_mitra'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    conn.close()

    for item in data:
        item["fee_payrol"] = FEE_PAYROL_PER_ORANG
        item["total_bayar"] = (item.get("jumlah") or 0) + FEE_PAYROL_PER_ORANG

    total_filtered = sum(d["jumlah"] for d in data)
    total_fee_payrol = calc_fee_payrol(len(data))
    total_grand = total_filtered + total_fee_payrol
    avg_gaji = int(total_filtered / len(data)) if data else 0
    max_item = max(data, key=lambda x: x["jumlah"]) if data else None
    min_item = min(data, key=lambda x: x["jumlah"]) if data else None
    total_all_batches = sum(lap.get("total_gaji") or 0 for lap in laporans)
    total_all_mitra = sum(lap.get("jumlah_penerima") or lap.get("record_count") or 0 for lap in laporans)

    return render_template(request, "insentif_mitra.html", {
        "user": user,
        "items": data,
        "laporans": laporans,
        "laporan": laporan,
        "view_all": view_all,
        "selected_upload_id": upload_id if upload_id else 0,
        "total_filtered": total_filtered,
        "total_fee_payrol": total_fee_payrol,
        "total_grand": total_grand,
        "fee_payrol_amount": FEE_PAYROL_PER_ORANG,
        "insentif_mitra_jumlah": INSENTIF_MITRA_JUMLAH,
        "insentif_mitra_per_hari": INSENTIF_MITRA_PER_HARI,
        "insentif_mitra_hari": INSENTIF_MITRA_HARI,
        "total_all_batches": total_all_batches,
        "total_all_mitra": total_all_mitra,
        "avg_gaji": avg_gaji,
        "max_item": max_item,
        "min_item": min_item,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {"search": search, "status": status, "rekening": rekening, "tanggal": tanggal, "periode": upload_id},
        "periode_options": periode_options,
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "message": message,
        "success": success,
    })


@app.post("/insentif-mitra/upload")
async def insentif_mitra_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""

    conn = get_db()
    conn.execute(
        "INSERT INTO uploads (filename, created_by) VALUES (?, ?)",
        (file.filename, user["id"]),
    )
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        if ext == "csv":
            parsed = parse_insentif_mitra_csv(file_path, file.filename)
        else:
            parsed = parse_upload_file(file_path, file.filename, "insentif_mitra", upload_id)
            if isinstance(parsed, list):
                meta = {"periode": _parse_pic_periode(file.filename), "filename": file.filename}
                items = []
                for idx, row in enumerate(parsed, start=1):
                    nama = (
                        row.get("nama") or row.get("atas_nama") or row.get("atas nama")
                        or row.get("pengajuan") or row.get("nama mitra") or ""
                    )
                    if isinstance(nama, str):
                        nama = _strip_nama_gelar(nama.strip())
                    if not nama:
                        continue
                    try:
                        jumlah = int(float(row.get("jumlah") or row.get("total") or row.get("gaji") or 0))
                    except (TypeError, ValueError):
                        jumlah = 0
                    if jumlah <= 0:
                        continue
                    periode_label = meta.get("periode") or "Insentif Mitra"
                    items.append({
                        "no": str(idx),
                        "pengajuan": f"{nama} — {periode_label}",
                        "atas_nama": nama,
                        "nomor_rekening": str(row.get("nomor_rekening") or row.get("nomor rekening") or row.get("no rekening") or "").strip() or None,
                        "bank": str(row.get("bank") or "MANDIRI").strip(),
                        "jumlah": jumlah,
                        "tanggal": str(row.get("tanggal") or "").strip() or None,
                        "rekening": "TRANSFER MASSAL",
                        "status": "DIAJUKAN",
                    })
                parsed = {"meta": meta, "items": items}
    except Exception as e:
        conn.close()
        return RedirectResponse(f"/insentif-mitra?message=Error parsing file: {str(e)}", status_code=303)

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []
    ip_meta = parsed.get("meta", {}) if isinstance(parsed, dict) else {}

    if not item_list:
        conn.close()
        return RedirectResponse("/insentif-mitra?message=Tidak ada data yang bisa dibaca dari file", status_code=303)

    inserted = 0
    for item in item_list:
        pengajuan = item.get("pengajuan") or item.get("atas_nama") or ""
        if not pengajuan:
            continue
        jumlah = int(item.get("jumlah") or 0)
        if jumlah <= 0:
            continue

        dup = conn.execute("""
            SELECT 1 FROM tagihan
            WHERE upload_id = ? AND pengajuan = ? AND jumlah = ?
            LIMIT 1
        """, (upload_id, pengajuan, jumlah)).fetchone()
        if dup:
            continue

        conn.execute("""
            INSERT INTO tagihan
            (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, upload_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_mitra', ?, ?)
        """, (
            item.get("no"),
            pengajuan,
            jumlah,
            item.get("status") or "DIAJUKAN",
            item.get("rekening") or "TRANSFER MASSAL",
            item.get("tanggal") or ip_meta.get("tanggal_pembayaran"),
            item.get("atas_nama"),
            item.get("nomor_rekening"),
            item.get("bank"),
            upload_id,
            user["id"],
        ))
        inserted += 1

    conn.execute("""
        INSERT OR REPLACE INTO insentif_mitra_laporan
        (upload_id, tanggal_pembayaran, rekening_sumber, jumlah_penerima, total_gaji,
         periode, bank, kota, filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        upload_id,
        ip_meta.get("tanggal_pembayaran"),
        ip_meta.get("rekening_sumber"),
        ip_meta.get("jumlah_penerima") or inserted,
        ip_meta.get("total_gaji") or sum(i.get("jumlah", 0) for i in item_list),
        ip_meta.get("periode"),
        ip_meta.get("bank") or "MANDIRI",
        ip_meta.get("kota"),
        file.filename,
    ))
    conn.execute("UPDATE uploads SET record_count = ?, periode = ? WHERE id = ?",
                 (inserted, ip_meta.get("periode"), upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} data insentif mitra"
    if ip_meta.get("periode"):
        msg += f" ({ip_meta['periode']})"
    return RedirectResponse(f"/insentif-mitra?message={msg}&success=true", status_code=303)


@app.post("/insentif-mitra")
async def create_insentif_mitra(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_mitra', ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-mitra", status_code=303)


@app.post("/insentif-mitra/{item_id}/update")
async def update_insentif_mitra(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = 'insentif_mitra', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'insentif_mitra'
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-mitra", status_code=303)


@app.post("/insentif-mitra/{item_id}/delete")
async def delete_insentif_mitra(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'insentif_mitra'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'insentif_mitra'", (item_id,))
    if row and row[0]:
        recalc_insentif_mitra_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-mitra", status_code=303)


@app.post("/api/insentif-mitra/bulk-delete")
async def api_insentif_mitra_bulk_delete(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"""SELECT DISTINCT upload_id FROM tagihan
                WHERE id IN ({placeholders}) AND kategori = 'insentif_mitra' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'insentif_mitra'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_insentif_mitra_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/insentif-mitra/bulk-update")
async def api_insentif_mitra_bulk_update(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"""UPDATE tagihan SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND kategori = 'insentif_mitra'""",
            [status] + ids,
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/export/insentif-mitra/csv")
async def export_insentif_mitra_csv(user=Depends(require_login)):
    import csv
    from io import StringIO

    data = get_insentif_mitra()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NO", "TANGGAL", "KETERANGAN", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"])
    for d in data:
        writer.writerow([
            d["no"] or "",
            d["tanggal"] or "",
            d["pengajuan"],
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
            d["jumlah"],
            d["status"] or "",
        ])
    output.seek(0)
    filename = f"insentif_mitra_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/export/insentif-mitra/xlsx")
async def export_insentif_mitra_xlsx(user=Depends(require_login)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    data = get_insentif_mitra()
    wb = Workbook()
    ws = wb.active
    ws.title = "Insentif Mitra"

    header_fill = PatternFill(start_color="071E49", end_color="071E49", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.merge_cells("B1:I1")
    ws["B1"] = "INSENTIF MITRA - SPPG WISMA HAJI MADIUN"
    ws["B1"].font = Font(bold=True, size=14, color="071E49")
    ws["B1"].alignment = Alignment(horizontal="center")

    headers = ["NO", "TANGGAL", "KETERANGAN", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"]
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for idx, d in enumerate(data, start=4):
        row_data = [
            d["no"] or "",
            d["tanggal"] or "",
            d["pengajuan"],
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
            d["jumlah"],
            d["status"] or "",
        ]
        for col, val in enumerate(row_data, start=2):
            cell = ws.cell(row=idx, column=col, value=val)
            cell.border = thin_border
            if col == 8:
                cell.number_format = "#,##0"
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    widths = [7, 14, 35, 22, 18, 14, 15, 14]
    for i, w in enumerate(widths, start=2):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A4"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"Insentif_Mitra_SPPG_{date.today().isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/pengembalian-dana", response_class=HTMLResponse)
async def pengembalian_dana_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    message: str = "",
    success: bool = False,
):
    periode_options = get_pengembalian_dana_laporans(active_only=True)
    laporans = periode_options
    laporan = None
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    filters = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

    view_all = upload_id == 0

    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_pengembalian_dana(filters)

    periode_map = {lap["upload_id"]: lap.get("periode") or lap.get("filename") for lap in laporans}
    for item in data:
        uid = item.get("upload_id")
        item["periode_label"] = periode_map.get(uid, "Input Manual") if uid else "Input Manual"

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() == "TERBAYAR" for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    pd_filter = "kategori = 'pengembalian_dana'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {pd_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {pd_filter}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    avg_gaji = int(total_filtered / len(data)) if data else 0
    max_item = max(data, key=lambda x: x["jumlah"]) if data else None
    min_item = min(data, key=lambda x: x["jumlah"]) if data else None
    total_all_batches = sum(lap.get("total_gaji") or 0 for lap in laporans)
    total_all_mitra = sum(lap.get("jumlah_penerima") or lap.get("record_count") or 0 for lap in laporans)

    return render_template(request, "pengembalian_dana.html", {
        "user": user,
        "items": data,
        "laporans": laporans,
        "laporan": laporan,
        "view_all": view_all,
        "selected_upload_id": upload_id if upload_id else 0,
        "total_filtered": total_filtered,
        "pengembalian_dana_jumlah": PENGEMBALIAN_DANA_JUMLAH,
        "pengembalian_dana_per_hari": PENGEMBALIAN_DANA_PER_HARI,
        "pengembalian_dana_hari": PENGEMBALIAN_DANA_HARI,
        "total_all_batches": total_all_batches,
        "total_all_mitra": total_all_mitra,
        "avg_gaji": avg_gaji,
        "max_item": max_item,
        "min_item": min_item,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {"search": search, "status": status, "rekening": rekening, "tanggal": tanggal, "periode": upload_id},
        "periode_options": periode_options,
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "message": message,
        "success": success,
    })


@app.post("/pengembalian-dana")
async def create_pengembalian_dana(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pengembalian_dana', ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/pengembalian-dana", status_code=303)


@app.post("/pengembalian-dana/{item_id}/update")
async def update_pengembalian_dana(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = 'pengembalian_dana', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'pengembalian_dana'
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/pengembalian-dana", status_code=303)


@app.post("/pengembalian-dana/{item_id}/delete")
async def delete_pengembalian_dana(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'pengembalian_dana'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'pengembalian_dana'", (item_id,))
    if row and row[0]:
        recalc_pengembalian_dana_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/pengembalian-dana", status_code=303)


@app.post("/api/pengembalian-dana/bulk-delete")
async def api_pengembalian_dana_bulk_delete(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"""SELECT DISTINCT upload_id FROM tagihan
                WHERE id IN ({placeholders}) AND kategori = 'pengembalian_dana' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'pengembalian_dana'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_pengembalian_dana_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/pengembalian-dana/bulk-update")
async def api_pengembalian_dana_bulk_update(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"""UPDATE tagihan SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND kategori = 'pengembalian_dana'""",
            [status] + ids,
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/export/pengembalian-dana/csv")
async def export_pengembalian_dana_csv(user=Depends(require_login)):
    import csv
    from io import StringIO

    data = get_pengembalian_dana()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NO", "TANGGAL", "KETERANGAN", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"])
    for d in data:
        writer.writerow([
            d["no"] or "",
            d["tanggal"] or "",
            d["pengajuan"],
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
            d["jumlah"],
            d["status"] or "",
        ])
    output.seek(0)
    filename = f"pengembalian_dana_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/export/pengembalian-dana/xlsx")
async def export_pengembalian_dana_xlsx(user=Depends(require_login)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    data = get_pengembalian_dana()
    wb = Workbook()
    ws = wb.active
    ws.title = "Pengembalian Dana"

    header_fill = PatternFill(start_color="071E49", end_color="071E49", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.merge_cells("B1:I1")
    ws["B1"] = "PENGEMBALIAN DANA / REFUND - SPPG WISMA HAJI MADIUN"
    ws["B1"].font = Font(bold=True, size=14, color="071E49")
    ws["B1"].alignment = Alignment(horizontal="center")

    headers = ["NO", "TANGGAL", "KETERANGAN", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"]
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for idx, d in enumerate(data, start=4):
        row_data = [
            d["no"] or "",
            d["tanggal"] or "",
            d["pengajuan"],
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
            d["jumlah"],
            d["status"] or "",
        ]
        for col, val in enumerate(row_data, start=2):
            cell = ws.cell(row=idx, column=col, value=val)
            cell.border = thin_border
            if col == 8:
                cell.number_format = "#,##0"
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    widths = [7, 14, 35, 22, 18, 14, 15, 14]
    for i, w in enumerate(widths, start=2):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A4"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"Pengembalian_Dana_SPPG_{date.today().isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/pengajuan-dana-mitra", response_class=HTMLResponse)
async def pengajuan_dana_mitra_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    message: str = "",
    success: bool = False,
):
    periode_options = get_pengajuan_dana_mitra_laporans(active_only=True)
    laporans = periode_options
    laporan = None
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    filters = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

    view_all = upload_id == 0

    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_pengajuan_dana_mitra(filters)

    periode_map = {lap["upload_id"]: lap.get("periode") or lap.get("filename") for lap in laporans}
    for item in data:
        uid = item.get("upload_id")
        item["periode_label"] = periode_map.get(uid, "Input Manual") if uid else "Input Manual"

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() == "TERBAYAR" for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    pdm_filter = "kategori = 'pengajuan_dana_mitra'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {pdm_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {pdm_filter}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    avg_gaji = int(total_filtered / len(data)) if data else 0
    max_item = max(data, key=lambda x: x["jumlah"]) if data else None
    min_item = min(data, key=lambda x: x["jumlah"]) if data else None
    total_all_batches = sum(lap.get("total_gaji") or 0 for lap in laporans)
    total_all_mitra = sum(lap.get("jumlah_penerima") or lap.get("record_count") or 0 for lap in laporans)

    return render_template(request, "pengajuan_dana_mitra.html", {
        "user": user,
        "items": data,
        "laporans": laporans,
        "laporan": laporan,
        "view_all": view_all,
        "selected_upload_id": upload_id if upload_id else 0,
        "total_filtered": total_filtered,
        "total_all_batches": total_all_batches,
        "total_all_mitra": total_all_mitra,
        "avg_gaji": avg_gaji,
        "max_item": max_item,
        "min_item": min_item,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {"search": search, "status": status, "rekening": rekening, "tanggal": tanggal, "periode": upload_id},
        "periode_options": periode_options,
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "message": message,
        "success": success,
    })


@app.post("/pengajuan-dana-mitra")
async def create_pengajuan_dana_mitra(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pengajuan_dana_mitra', ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/pengajuan-dana-mitra", status_code=303)


@app.post("/pengajuan-dana-mitra/{item_id}/update")
async def update_pengajuan_dana_mitra(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = 'pengajuan_dana_mitra', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'pengajuan_dana_mitra'
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/pengajuan-dana-mitra", status_code=303)


@app.post("/pengajuan-dana-mitra/{item_id}/delete")
async def delete_pengajuan_dana_mitra(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'pengajuan_dana_mitra'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'pengajuan_dana_mitra'", (item_id,))
    if row and row[0]:
        recalc_pengajuan_dana_mitra_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/pengajuan-dana-mitra", status_code=303)


@app.post("/api/pengajuan-dana-mitra/bulk-delete")
async def api_pengajuan_dana_mitra_bulk_delete(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"""SELECT DISTINCT upload_id FROM tagihan
                WHERE id IN ({placeholders}) AND kategori = 'pengajuan_dana_mitra' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'pengajuan_dana_mitra'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_pengajuan_dana_mitra_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/pengajuan-dana-mitra/bulk-update")
async def api_pengajuan_dana_mitra_bulk_update(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"""UPDATE tagihan SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND kategori = 'pengajuan_dana_mitra'""",
            [status] + ids,
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/export/pengajuan-dana-mitra/csv")
async def export_pengajuan_dana_mitra_csv(user=Depends(require_login)):
    import csv
    from io import StringIO

    data = get_pengajuan_dana_mitra()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NO", "TANGGAL", "KETERANGAN", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"])
    for d in data:
        writer.writerow([
            d["no"] or "",
            d["tanggal"] or "",
            d["pengajuan"],
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
            d["jumlah"],
            d["status"] or "",
        ])
    output.seek(0)
    filename = f"pengajuan_dana_mitra_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/export/pengajuan-dana-mitra/xlsx")
async def export_pengajuan_dana_mitra_xlsx(user=Depends(require_login)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    data = get_pengajuan_dana_mitra()
    wb = Workbook()
    ws = wb.active
    ws.title = "Pengajuan Dana Mitra"

    header_fill = PatternFill(start_color="071E49", end_color="071E49", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.merge_cells("B1:I1")
    ws["B1"] = "PENGAJUAN DANA MITRA - SPPG WISMA HAJI MADIUN"
    ws["B1"].font = Font(bold=True, size=14, color="071E49")
    ws["B1"].alignment = Alignment(horizontal="center")

    headers = ["NO", "TANGGAL", "KETERANGAN", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"]
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for idx, d in enumerate(data, start=4):
        row_data = [
            d["no"] or "",
            d["tanggal"] or "",
            d["pengajuan"],
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
            d["jumlah"],
            d["status"] or "",
        ]
        for col, val in enumerate(row_data, start=2):
            cell = ws.cell(row=idx, column=col, value=val)
            cell.border = thin_border
            if col == 8:
                cell.number_format = "#,##0"
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    widths = [7, 14, 35, 22, 18, 14, 15, 14]
    for i, w in enumerate(widths, start=2):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A4"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"Pengajuan_Dana_Mitra_SPPG_{date.today().isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/petty-cash", response_class=HTMLResponse)
async def petty_cash_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    tanggal: str = "",
    jenis: str = "",
    message: str = "",
    success: bool = False,
):
    laporans = get_petty_cash_laporans()
    laporan = None
    all_items = []

    if upload_id:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM petty_cash_laporan WHERE upload_id = ?", (upload_id,)
        ).fetchone()
        conn.close()
        if row:
            laporan = dict(row)
            all_items = get_petty_cash_items(upload_id)
    elif laporans:
        laporan = laporans[0]
        all_items = get_petty_cash_items(laporan["upload_id"])

    tanggal_options = sorted(
        {i.get("tanggal") for i in all_items if i.get("tanggal")},
        reverse=True,
    )
    tanggal_min = tanggal_options[-1] if tanggal_options else ""
    tanggal_max = tanggal_options[0] if tanggal_options else ""
    has_filters = bool(search.strip() or tanggal or jenis.strip())
    items = filter_petty_cash_items(all_items, search, tanggal, jenis)

    total_pengeluaran = sum(i.get("kredit") or 0 for i in items)
    if not total_pengeluaran:
        total_pengeluaran = sum(
            i["jumlah"] for i in items if (i.get("debit") or 0) == 0
        )
    total_penerimaan = sum(i.get("debit") or 0 for i in items)

    total_pengeluaran_all = sum(i.get("kredit") or 0 for i in all_items)
    total_penerimaan_all = sum(i.get("debit") or 0 for i in all_items)
    is_reimbursement = laporan and (laporan.get("report_type") or "") == "reimbursement"
    if laporan and not has_filters:
        if is_reimbursement:
            total_pengeluaran = laporan.get("total_digantikan") or sum(i.get("jumlah") or 0 for i in all_items)
            total_penerimaan = 0
        else:
            if laporan.get("total_kredit"):
                total_pengeluaran = laporan.get("total_kredit")
            if laporan.get("total_debit"):
                total_penerimaan = laporan.get("total_debit")

    nota_count = sum(1 for i in all_items if i.get("nota_path"))

    return render_template(request, "petty_cash.html", {
        "user": user,
        "laporans": laporans,
        "laporan": laporan,
        "items": items,
        "all_items_count": len(all_items),
        "total_pengeluaran": total_pengeluaran,
        "total_penerimaan": total_penerimaan,
        "total_pengeluaran_all": total_pengeluaran_all or (laporan.get("total_kredit") if laporan else 0),
        "total_penerimaan_all": total_penerimaan_all or (laporan.get("total_debit") if laporan else 0),
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "selected_upload_id": laporan["upload_id"] if laporan else 0,
        "filters": {"search": search, "tanggal": tanggal, "jenis": jenis},
        "tanggal_options": tanggal_options,
        "tanggal_min": tanggal_min,
        "tanggal_max": tanggal_max,
        "has_filters": has_filters,
        "is_reimbursement": is_reimbursement,
        "nota_count": nota_count,
        "message": message,
        "success": success,
    })

@app.post("/petty-cash/upload")
async def petty_cash_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
    periode: str = Form(""),
):
    """Upload PDF petty cash — terpisah dari modul Tagihan."""
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    conn = get_db()
    conn.execute("""
        INSERT INTO uploads (filename, periode, created_by)
        VALUES (?, ?, ?)
    """, (file.filename, periode or None, user["id"]))
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        parsed = parse_petty_cash_pdf(file_path, upload_id, file.filename)
    except Exception as e:
        conn.close()
        return RedirectResponse(f"/petty-cash?message=Error parsing file: {str(e)}", status_code=303)

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []
    petty_meta = parsed.get("meta", {}) if isinstance(parsed, dict) else {}

    if not item_list:
        conn.close()
        return RedirectResponse("/petty-cash?message=Tidak ada data yang bisa dibaca dari file", status_code=303)

    inserted = 0
    for item in item_list:
        pengajuan = item.get("pengajuan") or item.get("deskripsi") or ""
        if not pengajuan:
            continue
        try:
            debit_val = int(item.get("debit") or 0)
            kredit_val = int(item.get("kredit") or 0)
            jumlah = int(item.get("jumlah") or 0)
        except Exception:
            debit_val = kredit_val = jumlah = 0
        if not jumlah:
            jumlah = kredit_val if kredit_val > 0 else debit_val
        if jumlah <= 0 and debit_val <= 0 and kredit_val <= 0:
            continue

        no = str(item.get("no") or "").strip() or None
        tanggal = str(item.get("tanggal") or "").strip() or None
        nota_path = item.get("nota_path")
        saldo_akhir = item.get("saldo_akhir")
        tipe_transaksi = item.get("tipe_transaksi") or item.get("tipe")

        dup = conn.execute("""
            SELECT 1 FROM petty_cash_items
            WHERE upload_id = ? AND COALESCE(no,'') = COALESCE(?, '') AND pengajuan = ?
            LIMIT 1
        """, (upload_id, no, pengajuan)).fetchone()
        if dup:
            continue

        conn.execute("""
            INSERT INTO petty_cash_items
            (upload_id, no, pengajuan, jumlah, debit, kredit, saldo_akhir, tipe_transaksi, tanggal, nota_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            upload_id, no, pengajuan, jumlah, debit_val, kredit_val,
            saldo_akhir, tipe_transaksi, tanggal, nota_path,
        ))
        inserted += 1

    if petty_meta:
        conn.execute("""
            INSERT OR REPLACE INTO petty_cash_laporan
            (upload_id, nama_karyawan, divisi, saldo_awal, sisa_dana, total_digantikan,
             payment_info, bank, nomor_rekening, atas_nama, yang_menyetujui,
             tanggal_ttd_pemohon, tanggal_ttd_menyetujui, periode, filename,
             report_type, total_debit, total_kredit, saldo_akhir)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            upload_id,
            petty_meta.get("nama_karyawan"),
            petty_meta.get("divisi"),
            petty_meta.get("saldo_awal") or 0,
            petty_meta.get("sisa_dana") or petty_meta.get("saldo_akhir") or 0,
            petty_meta.get("total_digantikan") or petty_meta.get("total_kredit") or 0,
            petty_meta.get("payment_info"),
            petty_meta.get("bank"),
            petty_meta.get("nomor_rekening"),
            petty_meta.get("atas_nama"),
            petty_meta.get("yang_menyetujui"),
            petty_meta.get("tanggal_ttd_pemohon"),
            petty_meta.get("tanggal_ttd_menyetujui"),
            petty_meta.get("periode") or periode,
            file.filename,
            petty_meta.get("report_type") or "reimbursement",
            petty_meta.get("total_debit") or 0,
            petty_meta.get("total_kredit") or 0,
            petty_meta.get("saldo_akhir") or petty_meta.get("sisa_dana") or 0,
        ))

    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (inserted, upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} baris data Petty Cash"
    return RedirectResponse(f"/petty-cash?upload_id={upload_id}&message={msg}&success=true", status_code=303)

@app.post("/tagihan")
async def create_tagihan(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
    kategori: str = Form("tagihan"),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        kategori or "tagihan",
        user["id"]
    ))
    conn.commit()
    conn.close()

    # If AJAX request, return JSON
    if request.headers.get("hx-request"):
        return JSONResponse({"success": True})

    return RedirectResponse("/tagihan", status_code=303)

@app.post("/tagihan/{tagihan_id}/update")
async def update_tagihan(
    tagihan_id: int,
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
    kategori: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?,
            pengajuan = ?,
            jumlah = ?,
            status = ?,
            rekening = ?,
            tanggal = ?,
            atas_nama = ?,
            nomor_rekening = ?,
            bank = ?,
            kategori = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        kategori or None,
        tagihan_id
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/tagihan", status_code=303)

@app.post("/tagihan/{tagihan_id}/delete")
async def delete_tagihan(tagihan_id: int, user=Depends(require_login)):
    conn = get_db()
    conn.execute("DELETE FROM tagihan WHERE id = ?", (tagihan_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/tagihan", status_code=303)

# Bulk actions
def recalc_petty_cash_laporan(conn, upload_id: int):
    """Hitung ulang total laporan setelah hapus transaksi."""
    rows = conn.execute(
        "SELECT debit, kredit, saldo_akhir FROM petty_cash_items WHERE upload_id = ? ORDER BY id",
        (upload_id,),
    ).fetchall()
    total_debit = sum(r[0] or 0 for r in rows)
    total_kredit = sum(r[1] or 0 for r in rows)
    saldo_akhir = rows[-1][2] if rows else 0
    conn.execute("""
        UPDATE petty_cash_laporan SET
            total_debit = ?, total_kredit = ?, total_digantikan = ?,
            sisa_dana = ?, saldo_akhir = ?
        WHERE upload_id = ?
    """, (total_debit, total_kredit, total_kredit, saldo_akhir, saldo_akhir, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (len(rows), upload_id))

ALLOWED_NOTA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}


def _delete_nota_file(nota_path: str):
    if not nota_path:
        return
    full = os.path.join(UPLOAD_DIR, nota_path)
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


@app.post("/api/petty-cash/{item_id}/nota")
async def api_petty_cash_upload_nota(
    item_id: int,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_NOTA_EXT:
        return JSONResponse({"error": "Format file tidak didukung"}, status_code=400)

    conn = get_db()
    row = conn.execute(
        "SELECT id, upload_id, nota_path FROM petty_cash_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)

    nota_dir = os.path.join(UPLOAD_DIR, "nota", str(row["upload_id"]))
    os.makedirs(nota_dir, exist_ok=True)
    safe_ext = ".jpg" if ext in (".jpg", ".jpeg") else ext
    fname = f"nota_item_{item_id}{safe_ext}"
    rel_path = f"nota/{row['upload_id']}/{fname}"
    full_path = os.path.join(UPLOAD_DIR, rel_path)

    if row["nota_path"] and row["nota_path"] != rel_path:
        _delete_nota_file(row["nota_path"])

    content = await file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    conn.execute(
        "UPDATE petty_cash_items SET nota_path = ? WHERE id = ?", (rel_path, item_id)
    )
    conn.commit()
    conn.close()
    return JSONResponse({"success": True, "nota_path": rel_path})


@app.patch("/api/petty-cash/{item_id}/ket")
async def api_petty_cash_update_ket(
    item_id: int,
    request: Request,
    user=Depends(require_login),
):
    try:
        data = await request.json()
        ket = (data.get("ket") or "").strip() or None
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM petty_cash_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)
        conn.execute(
            "UPDATE petty_cash_items SET ket = ? WHERE id = ?", (ket, item_id)
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "ket": ket or ""})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/petty-cash/{item_id}/nota")
async def api_petty_cash_delete_nota(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT nota_path FROM petty_cash_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)

    if row["nota_path"]:
        _delete_nota_file(row["nota_path"])

    conn.execute("UPDATE petty_cash_items SET nota_path = NULL WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"success": True})


@app.post("/api/petty-cash/bulk-delete")
async def api_petty_cash_bulk_delete(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"SELECT DISTINCT upload_id FROM petty_cash_items WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        conn.execute(f"DELETE FROM petty_cash_items WHERE id IN ({placeholders})", ids)
        for row in upload_rows:
            recalc_petty_cash_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/tagihan/bulk-delete")
async def api_bulk_delete(request: Request):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM tagihan WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/tagihan/bulk-update")
async def api_bulk_update(request: Request):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        pos = data.get("pos")
        status = data.get("status")
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        if pos is not None:
            conn.execute(f"UPDATE tagihan SET pos = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [pos] + ids)
        if status is not None:
            print(f"[DEBUG BULK] Updating status to {status} for ids {ids}")
            conn.execute(f"UPDATE tagihan SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [status] + ids)
            print(f"[DEBUG BULK] Rows affected: {conn.total_changes}")
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ===================== API for dynamic UI =====================

@app.get("/api/tagihan")
async def api_tagihan(user=Depends(require_login)):
    data = get_all_tagihan()
    return [{"id": d["id"], **d, "jumlah_fmt": format_rupiah(d["jumlah"])} for d in data]

@app.get("/api/summary")
async def api_summary(user=Depends(require_login)):
    return get_summary()

# ===================== Export =====================

@app.get("/export/csv")
async def export_csv(user=Depends(require_login)):
    import csv
    from io import StringIO

    data = get_all_tagihan()
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["NO", "KETERANGAN", "JUMLAH", "STATUS", "REKENING", "TANGGAL", "ATAS NAMA REK.", "NOMOR REKENING", "BANK"])

    for d in data:
        writer.writerow([
            d["no"] or "",
            d["pengajuan"],
            d["jumlah"],
            d["status"] or "",
            d["rekening"] or "",
            d["tanggal"] or "",
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
        ])

    output.seek(0)
    filename = f"tagihan_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/export/xlsx")
async def export_xlsx(user=Depends(require_login)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    data = get_all_tagihan()

    wb = Workbook()
    ws = wb.active
    ws.title = "Tagihan Mitra"

    # Header styling similar to original
    header_fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )

    # Title row
    ws.merge_cells('B1:J1')
    ws['B1'] = "TAGIHAN MITRA - SPPG WISMA HAJI MADIUN"
    ws['B1'].font = Font(bold=True, size=14, color="0F766E")
    ws['B1'].alignment = Alignment(horizontal='center')

    # Headers (row 3 to match original structure)
    headers = ["NO", "KETERANGAN", "JUMLAH", "STATUS", "REKENING", "TANGGAL", "ATAS NAMA REK.", "NOMOR REKENING", "BANK"]
    for col, header in enumerate(headers, start=2):
        cell = ws.cell(row=3, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    # Data rows
    for idx, d in enumerate(data, start=4):
        row_data = [
            d["no"] or "",
            d["pengajuan"],
            d["jumlah"],
            d["status"] or "",
            d["rekening"] or "",
            d["tanggal"] or "",
            d["atas_nama"] or "",
            d["nomor_rekening"] or "",
            d["bank"] or "",
        ]
        for col, val in enumerate(row_data, start=2):
            cell = ws.cell(row=idx, column=col, value=val)
            cell.border = thin_border
            if col == 4:  # JUMLAH column
                cell.number_format = '#,##0'
            cell.alignment = Alignment(vertical='center', wrap_text=True)

    # Column widths (close to original)
    widths = [7, 35, 15, 16, 16, 14, 22, 18, 22]
    for i, w in enumerate(widths, start=2):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Freeze header
    ws.freeze_panes = 'A4'

    # Total row
    total_row = 4 + len(data)
    ws.cell(row=total_row, column=2, value="TOTAL").font = Font(bold=True)
    total_formula = f"=SUM(D4:D{total_row-1})"
    total_cell = ws.cell(row=total_row, column=4, value=f"=SUM(D4:D{total_row-1})")
    total_cell.font = Font(bold=True)
    total_cell.number_format = '#,##0'

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"Tagihan_Mitra_SPPG_{date.today().isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ===================== UPLOAD LAPORAN =====================

def _parse_ledger_amount(text: str) -> int:
    """Parse Accurate ledger amounts (e.g. 5.000.000 or -1.228.456)."""
    import re
    raw = text.strip().replace(".", "").replace(",", "")
    try:
        return int(raw)
    except ValueError:
        m = re.search(r"-?[\d.,]+", text)
        if m:
            try:
                return int(m.group(0).replace(".", "").replace(",", ""))
            except ValueError:
                return 0
        return 0


def _extract_buku_besar_lines(pdf_path: str) -> List[str]:
    """Extract clean text lines from Accurate Buku Besar PDF."""
    import pdfplumber
    skip_exact = {
        "SPPG WISMA HAJI", "Rincian Buku Besar", "Filter berdasarkan : Kode Perkiraan",
        "Tanggal Tipe Transaksi Keterangan Debit Kredit Saldo Akhir", "11010101",
    }
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for raw in (page.extract_text() or "").split("\n"):
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("ACCURATE") or "Halaman" in line or "Tercetak" in line:
                    continue
                if line in skip_exact:
                    continue
                lines.append(line)
    return lines


def parse_buku_besar_petty_cash(pdf_path: str, upload_id: int, filename: str = "") -> Dict[str, Any]:
    """Parse Accurate 'Rincian Buku Besar' PDF untuk akun PETTY CASH (11010101)."""
    import re

    meta = {
        "report_type": "buku_besar",
        "nama_karyawan": "11010101 — PETTY CASH",
        "divisi": "SPPG Wisma Haji Madiun",
        "saldo_awal": 0,
        "sisa_dana": 0,
        "saldo_akhir": 0,
        "total_digantikan": 0,
        "total_debit": 0,
        "total_kredit": 0,
        "payment_info": "Sumber: Accurate Accounting — Rincian Buku Besar",
        "bank": None,
        "nomor_rekening": None,
        "atas_nama": None,
        "periode": None,
        "filename": filename,
    }

    all_lines = _extract_buku_besar_lines(pdf_path)
    for line in all_lines:
        if line.startswith("Dari ") and "s/d" in line:
            meta["periode"] = line.replace("Dari ", "").strip()
            break
    if not meta["periode"]:
        periode_m = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", filename.replace("_", " "), re.I)
        if periode_m:
            meta["periode"] = periode_m.group(1)

    tx_re = re.compile(
        r"^(\d{1,2}\s+\w{3}\s+\d{4})\s+(.+?)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)$"
    )

    items = []
    pending = None

    def _commit_pending():
        nonlocal pending
        if not pending or "debit" not in pending:
            pending = None
            return
        pending["no"] = str(len(items) + 1)
        pending["status"] = "DIAJUKAN"
        pending["rekening"] = "PETTY CASH"
        pending["jumlah"] = pending["kredit"] if pending["kredit"] > 0 else pending["debit"]
        items.append(pending)
        pending = None

    for line in all_lines:
        if line.startswith("11010101 -"):
            continue
        if re.match(r"^Dari \d", line):
            continue

        if re.match(r"^\d{1,2}\s+\w{3}\s+\d{4}\s+Saldo per", line):
            nums = re.findall(r"-?[\d.,]+", line)
            if nums:
                meta["saldo_awal"] = _parse_ledger_amount(nums[-1])
            continue

        if re.match(r"^[\d.,]+\s+[\d.,]+$", line) and len(line.split()) == 2:
            parts = line.split()
            meta["total_debit"] = _parse_ledger_amount(parts[0])
            meta["total_kredit"] = _parse_ledger_amount(parts[1])
            continue

        m = tx_re.match(line)
        if m:
            _commit_pending()
            tanggal_raw = m.group(1)
            body = m.group(2).strip()
            debit = _parse_ledger_amount(m.group(3))
            kredit = _parse_ledger_amount(m.group(4))
            saldo = _parse_ledger_amount(m.group(5))

            tipe = "Jurnal Umum"
            keterangan = body
            if body.startswith("Transfer Bank"):
                tipe = "Transfer Bank"
                keterangan = re.sub(r"^Transfer Bank\s*", "", body).strip()
            elif body.startswith("Jurnal Umum"):
                keterangan = body.replace("Jurnal Umum", "", 1).strip()

            pending = {
                "tanggal": _parse_id_date(tanggal_raw),
                "tanggal_display": tanggal_raw,
                "tipe_transaksi": tipe,
                "pengajuan": keterangan,
                "debit": debit,
                "kredit": kredit,
                "saldo_akhir": saldo,
            }
            continue

        if pending and "pengajuan" in pending:
            pending["pengajuan"] = (pending["pengajuan"] + " " + line).strip()

    _commit_pending()

    if items:
        meta["saldo_akhir"] = items[-1].get("saldo_akhir") or 0
        meta["sisa_dana"] = meta["saldo_akhir"]
    if not meta["total_kredit"]:
        meta["total_kredit"] = sum(i["kredit"] for i in items)
    if not meta["total_debit"]:
        meta["total_debit"] = sum(i["debit"] for i in items)
    meta["total_digantikan"] = meta["total_kredit"]

    return {"meta": meta, "items": items}


def _extract_nota_images_from_pdf(pdf_path: str, start_page: int = 1) -> List[Any]:
    """Ekstrak foto nota dari halaman lampiran (portrait, urutan baca)."""
    from io import BytesIO
    from pypdf import PdfReader
    from PIL import Image

    images = []
    try:
        reader = PdfReader(pdf_path)
        for pno in range(start_page, len(reader.pages)):
            for img_obj in reader.pages[pno].images:
                try:
                    im = Image.open(BytesIO(img_obj.data))
                    w, h = im.size
                    if min(w, h) < 400:
                        continue
                    if h >= w * 0.95:
                        images.append(im)
                except Exception:
                    pass
    except Exception as e:
        print("Nota image extract error:", e)
    return images


def parse_reimbursement_petty_cash(pdf_path: str, upload_id: int, filename: str = "") -> Dict[str, Any]:
    """Parse FORM REIMBURSEMENT / FORM PETTY CASH + lampiran nota per transaksi."""
    import re
    import pdfplumber

    meta = {
        "report_type": "reimbursement",
        "nama_karyawan": None,
        "divisi": None,
        "saldo_awal": 0,
        "sisa_dana": 0,
        "saldo_akhir": 0,
        "total_digantikan": 0,
        "total_debit": 0,
        "total_kredit": 0,
        "payment_info": None,
        "bank": None,
        "nomor_rekening": None,
        "atas_nama": None,
        "yang_menyetujui": None,
        "tanggal_ttd_pemohon": None,
        "tanggal_ttd_menyetujui": None,
        "periode": None,
        "filename": filename,
    }

    import re
    fname_norm = filename.replace("_", " ")
    periode_m = re.search(
        r"(?:FORM\s+PETTY\s+CASH|REIMBURSEMENT|FORM)\s+(\d{1,2}\s+\w+\s+\d{4})",
        fname_norm, re.IGNORECASE,
    )
    if not periode_m:
        periode_m = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", fname_norm, re.IGNORECASE)
    if periode_m:
        meta["periode"] = periode_m.group(1)

    skip_prefixes = (
        "FORM REIMBURSEMENT", "Tanggal Deskripsi", "PAYMENT",
    )
    awaiting_approver = False
    ttd_date_re = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")
    tx_re = re.compile(
        r"^(\d{1,2}\s+\w+\s+\d{4})\s+(.+?)\s+(Rp\s*[\d.,]+)$",
        re.IGNORECASE,
    )

    items = []
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return {"meta": meta, "items": items}
        lines = [l.strip() for l in (pdf.pages[0].extract_text() or "").split("\n") if l.strip()]

    for line in lines:
        if line.startswith("Nama Karyawan"):
            meta["nama_karyawan"] = line.replace("Nama Karyawan", "").strip()
        elif line.startswith("Divisi"):
            meta["divisi"] = line.replace("Divisi", "").strip()
        elif line.startswith("Saldo"):
            meta["saldo_awal"] = _parse_rp_amount(line)
        elif line.startswith("Sisa Dana"):
            amt = _parse_rp_amount(line.replace("-", ""))
            meta["sisa_dana"] = -amt if "-" in line else amt
        elif "Total yang Digantikan" in line:
            meta["total_digantikan"] = _parse_rp_amount(line)
        elif line.upper().startswith("PAYMENT"):
            meta["payment_info"] = line
            bm = re.search(r"(MANDIRI|BRI|BCA|BSI|BNI)\s+(\d+)", line, re.I)
            if bm:
                meta["bank"] = bm.group(1).upper()
                meta["nomor_rekening"] = bm.group(2)
            am = re.search(r"AN\s+(.+)$", line, re.I)
            if am:
                meta["atas_nama"] = am.group(1).strip()
            continue
        elif "Tanda Tangan Pemohon" in line:
            dm = ttd_date_re.search(line)
            if dm:
                meta["tanggal_ttd_pemohon"] = _parse_slash_date(dm.group(1))
            continue
        elif "yang menyetujui" in line.lower():
            dm = ttd_date_re.search(line)
            if dm:
                meta["tanggal_ttd_menyetujui"] = _parse_slash_date(dm.group(1))
            awaiting_approver = True
            continue
        elif awaiting_approver and not meta["yang_menyetujui"]:
            if not line.startswith("Tanda Tangan"):
                meta["yang_menyetujui"] = line.strip()
            awaiting_approver = False
            continue

        if any(line.startswith(p) for p in skip_prefixes):
            continue
        if line.startswith("Tanda Tangan"):
            continue
        if meta["nama_karyawan"] and line.upper() == meta["nama_karyawan"].upper():
            continue

        m = tx_re.match(line)
        if m:
            amt = _parse_rp_amount(m.group(3))
            if amt <= 0:
                continue
            desc = m.group(2).strip()
            items.append({
                "no": str(len(items) + 1),
                "tanggal": _parse_id_date(m.group(1)),
                "tanggal_display": m.group(1),
                "deskripsi": desc,
                "pengajuan": desc,
                "jumlah": amt,
                "kredit": amt,
                "debit": 0,
                "status": "DIAJUKAN",
                "rekening": "PETTY CASH",
                "tipe_transaksi": "Pengeluaran",
            })

    meta["total_kredit"] = sum(i["kredit"] for i in items)
    if not meta["total_digantikan"]:
        meta["total_digantikan"] = meta["total_kredit"]
    meta["saldo_akhir"] = meta["sisa_dana"]

    nota_dir = os.path.join(UPLOAD_DIR, "nota", str(upload_id))
    os.makedirs(nota_dir, exist_ok=True)
    nota_images = _extract_nota_images_from_pdf(pdf_path, start_page=1)

    for idx, item in enumerate(items):
        if idx < len(nota_images):
            fname = f"nota_{idx + 1:02d}.jpg"
            fpath = os.path.join(nota_dir, fname)
            nota_images[idx].convert("RGB").save(fpath, "JPEG", quality=88)
            item["nota_path"] = f"nota/{upload_id}/{fname}"

    return {"meta": meta, "items": items}


def parse_petty_cash_pdf(pdf_path: str, upload_id: int, filename: str = "") -> Dict[str, Any]:
    """Auto-detect format petty cash: Buku Besar Accurate atau Form Reimbursement."""
    import pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return {"meta": {}, "items": []}
            first_text = pdf.pages[0].extract_text() or ""
    except Exception as e:
        print("Petty cash PDF open error:", e)
        return {"meta": {}, "items": []}

    fname_up = filename.upper()
    if "FORM REIMBURSEMENT" in first_text or "FORM PETTY CASH" in fname_up or "REIMBURSEMENT" in fname_up:
        return parse_reimbursement_petty_cash(pdf_path, upload_id, filename)
    if "Rincian Buku Besar" in first_text or "11010101 - PETTY CASH" in first_text:
        return parse_buku_besar_petty_cash(pdf_path, upload_id, filename)
    return parse_reimbursement_petty_cash(pdf_path, upload_id, filename)

def parse_faktur_belum_lunas(pdf_path: str):
    """Parse the specific SPPG 'Faktur Belum Lunas' PDF (Accurate format).
    Automatically detects the header date "Per Tgl. DD Mon YYYY" (as shown in the faktur header image)
    and uses it for item['tanggal'] so that all records from the upload are filed/sorted
    into the Tanggal column on the /tagihan page.
    Falls back to per-line dates only if header date not found.
    Handles Indonesian months (Jun, Mei, etc).
    """
    import pdfplumber
    import re
    from dateutil import parser as date_parser

    items = []
    current_supplier = None

    def _parse_date(tgl_str: str):
        if not tgl_str:
            return None
        tgl = tgl_str.strip()
        # Normalize Indonesian months to English equivalents for dateutil
        norm = tgl.lower()
        for indo, eng in [('mei', 'may'), ('agu', 'aug'), ('agt', 'aug'), ('okt', 'oct'), ('des', 'dec')]:
            norm = norm.replace(indo, eng)
        try:
            dt = date_parser.parse(norm, dayfirst=True, fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        # Manual fallback (supports both ID/EN short months)
        try:
            p = tgl.lower().split()
            d = int(p[0])
            mon_str = p[1][:3]
            mon_map = {
                'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'mei':5,
                'jun':6,'jul':7,'aug':8,'agu':8,'sep':9,
                'oct':10,'okt':10,'nov':11,'dec':12,'des':12
            }
            mon = mon_map.get(mon_str, 1)
            y = int(p[2])
            return f"{y:04d}-{mon:02d}-{d:02d}"
        except Exception:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        all_lines = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_lines.extend([l.strip() for l in text.split("\n") if l.strip()])

    # Detect the header "Per Tgl. 20 Jun 2026" (or similar) — this is the date to use for the web Tanggal column
    header_tanggal = None
    for line in all_lines:
        if "per tgl" in line.lower():
            m = re.search(r'Per Tgl\.?\s*(\d{1,2}\s+\w+\s+\d{4})', line, re.IGNORECASE)
            if m:
                header_tanggal = _parse_date(m.group(1))
                break

    for line in all_lines:
        line = line.strip()
        if not line:
            continue

        skip_keywords = ["SPPG WISMA HAJI", "Faktur Belum Lunas", "ACCURATE", "Tercetak", "Halaman",
                         "Indonesian", "Nomor #", "Cabang :", "Per Tgl", "Total Utang", "Rupiah"]
        if any(kw.lower() in line.lower() for kw in skip_keywords):
            continue

        # Supplier lines appear immediately before PI. lines (company / pemasok name)
        if not line.startswith("PI."):
            if len(line) > 2 and not re.match(r'^\d', line):
                low = line.lower()
                if not any(kw in low for kw in ["pembelian", "total", "peb", "report", "0 0", "rupiah"]):
                    # Skip keterangan continuation lines (short, commas, mixed numbers/abbr)
                    if re.search(r'\d', line) and len(line) < 28:
                        pass  # do not treat as supplier e.g. "THINWALL 120 ML, DLL"
                    elif ',' in line and len(line) < 30:
                        pass
                    else:
                        current_supplier = line
            continue

        # Match PI. line (we still parse per-line date only as fallback)
        # Example: PI.2026.06.00005 02 Jun 2026 02 Jun 2026 PEMBELIAN ... 4.464.000 ...
        m = re.match(r'^(PI\.\d{4}\.\d{2}\.\d{5})\s+(\d{1,2}\s+\w+\s+\d{4})\s+(.+)$', line)
        if not m:
            m = re.match(r'^(PI\.\d{4}\.\d{2}\.\d{5})\s+(\d{1,2}\s+\w+\s+\d{4})', line)
            if not m:
                continue
            rest = line[len(m.group(0)):].strip()
        else:
            rest = m.group(3).strip()

        no = m.group(1)
        tgl_str = m.group(2)
        # Prefer the header "Per Tgl." date (from the faktur cover/header image) for the web Tanggal column.
        # This ensures all items from one "Faktur Belum Lunas" upload share the report date for easy filtering/sorting.
        tanggal = header_tanggal or _parse_date(tgl_str)

        # Extract JUMLAH: first realistic dotted amount (e.g. 4.464.000), NOT year '2026'
        amount_match = re.search(r'(\d{1,3}(?:\.\d{3})+(?:\.\d{3})*)', rest)
        jumlah = 0
        if amount_match:
            try:
                jumlah = int(amount_match.group(1).replace(".", "").replace(",", ""))
            except:
                jumlah = 0
        if jumlah <= 0:
            # last resort
            amt2 = re.search(r'([\d\.,]{6,})', rest)
            if amt2:
                try:
                    jumlah = int(amt2.group(1).replace(".", "").replace(",", ""))
                except:
                    jumlah = 0
        if jumlah <= 0:
            continue

        # Bank + nomor rekening (appears near end)
        bank = ""
        rek = ""
        bank_match = re.search(r'\b(MANDIRI|BRI|BCA|BSI|VA|BNI)\s+(\d{5,})', rest + " " + line, re.IGNORECASE)
        if bank_match:
            bank = bank_match.group(1).upper()
            rek = bank_match.group(2)

        # Keterangan = description between the due-date and the amount
        keterangan = rest
        if amount_match:
            keterangan = rest[:amount_match.start()].strip()
        keterangan = re.sub(r'\s+', ' ', keterangan).strip()
        # Trim any leftover leading date in the slice
        keterangan = re.sub(r'^\d{1,2}\s+\w+\s+\d{4}\s*', '', keterangan).strip()

        # Supplier priority:
        # 1. The line immediately preceding this PI. (pemasok header)
        # 2. Trailing name after the rekening number on THIS line itself (helps across page breaks)
        supplier = current_supplier or ""
        # Prefer or fallback to trailing name on the PI line (handles page-breaks / missing header lines)
        trail_m = re.search(r'(\d{5,})\s+([A-Za-z][A-Za-z\'\s]{2,})$', line)
        trailing = trail_m.group(2).strip() if trail_m else ""
        if (not supplier) or len(supplier) < 3 or re.search(r'\d', supplier) or ',' in supplier:
            if trailing:
                supplier = trailing

        pengajuan = (keterangan + " - " + supplier).strip(" -") if supplier else keterangan
        if not pengajuan:
            pengajuan = f"Tagihan {no}"

        items.append({
            "no": no,
            "pengajuan": pengajuan,
            "jumlah": jumlah,
            "tanggal": tanggal,
            "bank": bank,
            "nomor_rekening": rek,
            "atas_nama": supplier or None,
            "status": "DIAJUKAN"
        })
        current_supplier = None  # prevent stale carry-over from continuation lines / page breaks for next PI

    return items

def parse_upload_file(file_path: str, filename: str, kategori: str = "tagihan", upload_id: int = 0):
    """Parse Excel, CSV or PDF. Use special parser per kategori."""
    rows = []
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''

    if ext == 'csv' and kategori == "gaji_relawan":
        try:
            return parse_gaji_relawan_csv(file_path, filename)
        except Exception as e:
            print("Gaji relawan CSV parse error:", e)
            return {"meta": {}, "items": []}

    if ext == 'csv' and kategori == "insentif_pic":
        try:
            return parse_insentif_pic_csv(file_path, filename)
        except Exception as e:
            print("Insentif PIC CSV parse error:", e)
    if ext == 'csv' and kategori == "insentif_mitra":
        try:
            return parse_insentif_mitra_csv(file_path, filename)
        except Exception as e:
            print("Insentif Mitra CSV parse error:", e)
            return {"meta": {}, "items": []}

    if ext == 'pdf' and kategori == "petty_cash":
        try:
            result = parse_petty_cash_pdf(file_path, upload_id, filename)
            return result
        except Exception as e:
            print("Petty cash PDF parse error:", e)
            return {"meta": {}, "items": []}

    if ext == 'pdf':
        # Always try the special parser for known template PDFs first
        try:
            special = parse_faktur_belum_lunas(file_path)
            if special and any(item.get("jumlah", 0) > 0 for item in special):
                rows = special
            else:
                # General fallback for other PDFs: try to pull amounts from text
                import pdfplumber
                import re
                with pdfplumber.open(file_path) as pdf:
                    all_text = ""
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            all_text += t + "\n"
                    lines = [l.strip() for l in all_text.split("\n") if l.strip()]
                    for line in lines[:20]:
                        m = re.search(r"([\d\.,]{4,})", line)  # look for reasonably sized numbers
                        if m:
                            try:
                                amt = int(m.group(1).replace(".", "").replace(",", ""))
                            except:
                                amt = None
                            if amt and amt > 100:
                                rows.append({
                                    "pengajuan": line[:200],
                                    "jumlah": amt,
                                    "tanggal": None,
                                    "status": "DIAJUKAN"
                                })
                    if not rows:
                        pengajuan = "Laporan dari PDF: " + " | ".join(lines[:3])
                        rows.append({
                            "pengajuan": pengajuan[:200],
                            "jumlah": 0,
                            "tanggal": None,
                            "status": "DIAJUKAN"
                        })
        except Exception as e:
            print("PDF parse error:", e)
            rows = []
    elif ext in ['xlsx', 'xls']:
        from openpyxl import load_workbook
        wb = load_workbook(file_path)
        ws = wb.active
        headers = []
        for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
            if row_idx == 1:
                headers = [str(h).strip().lower() if h else '' for h in row]
                continue
            if not any(row):
                continue
            item = {}
            for i, h in enumerate(headers):
                val = row[i] if i < len(row) else None
                item[h] = val
            rows.append(item)
    else:
        # CSV
        import csv
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({k.strip().lower(): v for k, v in row.items() if k})

    return rows

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, user=Depends(require_login), message: str = "", success: bool = False, pos: str = "", upload_id: int = 0):
    return render_template(request, "upload.html", {
        "user": user,
        "message": message,
        "success": success,
        "pos": pos,
        "upload_id": upload_id
    })

@app.post("/upload", response_class=HTMLResponse)
async def upload_laporan(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
    pos: str = Form(""),
    pos_other: str = Form(""),
    periode: str = Form(""),
    kategori: str = Form("tagihan")
):
    if kategori == "petty_cash":
        return RedirectResponse(
            "/petty-cash?message=Upload Petty Cash hanya melalui halaman Petty Cash",
            status_code=303,
        )

    final_pos = (pos_other.strip() if pos_other.strip() else pos.strip()) or None

    # Save file
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    conn = get_db()

    # Create upload record first (needed for petty cash nota folder)
    conn.execute("""
        INSERT INTO uploads (filename, pos, periode, created_by)
        VALUES (?, ?, ?, ?)
    """, (file.filename, final_pos, periode or None, user["id"]))
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Parse
    try:
        parsed = parse_upload_file(file_path, file.filename, kategori or "tagihan", upload_id)
    except Exception as e:
        conn.close()
        if kategori == "gaji_relawan":
            return RedirectResponse(f"/gaji-relawan?message=Error parsing file: {str(e)}", status_code=303)
        return RedirectResponse(f"/tagihan?kategori={kategori or 'tagihan'}&message=Error parsing file: {str(e)}", status_code=303)

    item_list = parsed if parsed else []

    if not item_list:
        conn.close()
        if kategori == "gaji_relawan":
            return RedirectResponse("/gaji-relawan?message=Tidak ada data yang bisa dibaca dari file", status_code=303)
        return RedirectResponse(f"/tagihan?kategori={kategori or 'tagihan'}&message=Tidak ada data yang bisa dibaca dari file", status_code=303)

    inserted = 0
    for item in item_list:
        pengajuan = item.get('pengajuan') or item.get('deskripsi') or item.get('penajuan') or item.get('keterangan') or ''
        if not pengajuan:
            continue

        try:
            debit_val = int(item.get('debit') or 0)
            kredit_val = int(item.get('kredit') or 0)
            jumlah = int(float(item.get('jumlah') or item.get('total') or 0))
        except Exception:
            debit_val = kredit_val = jumlah = 0
        if not jumlah:
            jumlah = kredit_val if kredit_val > 0 else debit_val
        if jumlah <= 0 and debit_val <= 0 and kredit_val <= 0:
            continue

        no = str(item.get('no') or '').strip() or None
        status = str(item.get('status') or 'DIAJUKAN').strip() or 'DIAJUKAN'
        rekening = str(item.get('rekening') or 'PETTY CASH').strip() or 'PETTY CASH'
        tanggal = str(item.get('tanggal') or '').strip() or None
        atas_nama = str(item.get('atas nama rek') or item.get('atas_nama') or item.get('atas nama') or '').strip() or None
        nomor_rek = str(item.get('nomor rekening') or item.get('nomor_rekening') or item.get('no rekening') or '').strip() or None
        bank = str(item.get('bank') or '').strip() or None
        nota_path = item.get('nota_path')
        saldo_akhir = item.get('saldo_akhir')
        tipe_transaksi = item.get('tipe_transaksi') or item.get('tipe')

        dup_check = conn.execute("""
            SELECT 1 FROM tagihan 
            WHERE COALESCE(no,'') = COALESCE(?, '') 
              AND pengajuan = ? 
              AND jumlah = ? 
              AND COALESCE(tanggal,'') = COALESCE(?, '') 
              AND kategori = ?
            LIMIT 1
        """, (no, pengajuan, jumlah, tanggal, kategori or "tagihan")).fetchone()

        if dup_check:
            continue

        conn.execute("""
            INSERT INTO tagihan 
            (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, upload_id, nota_path, debit, kredit, saldo_akhir, tipe_transaksi, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            no, pengajuan, jumlah, status, rekening, tanggal,
            atas_nama, nomor_rek, bank,
            kategori or "tagihan", upload_id, nota_path,
            debit_val, kredit_val, saldo_akhir, tipe_transaksi,
            user["id"]
        ))
        inserted += 1

    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (inserted, upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} baris data"
    if final_pos:
        msg += f" untuk Pos: {final_pos}"

    if kategori == "gaji_relawan":
        return RedirectResponse(f"/gaji-relawan?message={msg}&success=true", status_code=303)
    if kategori == "insentif_mitra":
        return RedirectResponse(f"/insentif-mitra?message={msg}&success=true", status_code=303)

    return RedirectResponse(f"/tagihan?kategori={kategori or 'tagihan'}&message={msg}&success=true", status_code=303)


# Need to import Response
from fastapi.responses import Response

# ===================== RUN =====================
if __name__ == "__main__":
    import uvicorn
    print("🚀 Menjalankan Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun")
    print("   Akses: http://localhost:8001")
    print("   Login: swhm / A0312   (atau admin / sppg123 backup)")
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
