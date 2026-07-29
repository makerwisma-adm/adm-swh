"""Dashboard aggregation helpers."""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.constants import ID_MONTH_NAMES, MODULE_ACCESS_GROUPS, PORTAL_MODULES
from app.services.tagihan import enrich_tagihan_item, get_all_tagihan, get_summary
from app.services.user_access import get_user_menu_keys
from app.utils.formatters import format_tanggal_display, format_tanggal_pengajuan
from app.db import get_db

PORTAL_BY_HREF = {m["href"]: m for m in PORTAL_MODULES}

BERANDA_KEYS = {"dashboard", "transfer_bgn", "laporan"}
LAPORAN_KEYS = {
    "tagihan", "petty_cash", "gaji_relawan", "gaji_staff", "insentif_pic",
    "insentif_mitra", "pengembalian_dana", "sewa_kendaraan",
}
MITRA_KEYS = {"portal_mitra", "pendapatan_mitra", "pengajuan_dana_mitra", "pengeluaran_mitra"}

DASHBOARD_MODULE = {
    "href": "/dashboard",
    "icon": "fa-chart-line",
    "title": "Dashboard Keuangan",
    "desc": "Ringkasan & analitik keuangan SPPG",
    "accent": "beranda",
    "key": "dashboard",
}

MODULE_HREF_KATEGORI = {m["href"]: m.get("key", "") for m in PORTAL_MODULES if m.get("key")}
MODULE_HREF_KATEGORI["/petty-cash"] = "petty_cash"

MODULE_ACCENTS = {
    "/transfer-bgn": "default",
    "/laporan": "default",
    "/portal-mitra": "mitra",
    "/tagihan": "tagihan",
    "/petty-cash": "petty",
    "/gaji-relawan": "gaji",
    "/gaji-staff": "staff",
    "/insentif-mitra": "insentif",
    "/insentif-pic": "insentif",
    "/pengembalian-dana": "refund",
    "/sewa-kendaraan": "sewa",
    "/pengajuan-dana-mitra": "mitra",
    "/pendapatan-mitra": "mitra",
    "/pengeluaran-mitra": "mitra",
}

MODULE_LABELS = {
    "tagihan": "Laporan Tagihan",
    "gaji_relawan": "Gaji Relawan",
    "gaji_staff": "Gaji Staff",
    "insentif_pic": "Insentif PIC",
    "insentif_mitra": "Insentif Mitra",
    "pengembalian_dana": "Pengembalian Dana",
    "sewa_kendaraan": "Sewa Kendaraan",
    "pengajuan_dana_mitra": "Pengajuan Dana Mitra",
    "pendapatan_mitra": "Pendapatan Mitra",
    "pengeluaran_mitra": "Pengeluaran Mitra",
    "petty_cash": "Petty Cash",
    "dashboard": "Dashboard",
    "transfer_bgn": "Transfer BGN",
    "laporan": "Laporan Keuangan",
    "portal_mitra": "Portal Mitra",
}


def _portal_entry_from_access_mod(mod: Dict[str, Any]) -> Dict[str, Any]:
    base = PORTAL_BY_HREF.get(mod["href"], {})
    return {
        "href": mod["href"],
        "icon": mod.get("icon") or base.get("icon", "fa-circle"),
        "title": base.get("title") or mod.get("label", ""),
        "desc": base.get("desc") or mod.get("label", ""),
        "key": mod["key"],
        "accent": MODULE_ACCENTS.get(mod["href"], "default"),
    }


def build_dashboard_module_lists(user: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Bangun daftar modul dashboard sesuai menu_access pengguna."""
    keys = get_user_menu_keys(user)
    beranda: List[Dict[str, Any]] = []
    laporan: List[Dict[str, Any]] = []
    mitra: List[Dict[str, Any]] = []

    for group in MODULE_ACCESS_GROUPS:
        for mod in group["modules"]:
            if mod["key"] not in keys:
                continue
            entry = _portal_entry_from_access_mod(mod)
            if group["id"] == "beranda":
                beranda.append(entry)
            elif group["id"] == "laporan":
                laporan.append(entry)
            elif group["id"] == "mitra":
                mitra.append(entry)

    return {
        "beranda_modules": beranda,
        "laporan_modules": laporan,
        "mitra_modules": mitra,
        "accessible_count": len(beranda) + len(laporan) + len(mitra),
    }


def format_bulan_chart(ym: str) -> str:
    if not ym or "-" not in ym:
        return ym or "—"
    year, month = ym.split("-", 1)
    try:
        idx = int(month)
        name = ID_MONTH_NAMES[idx] if 1 <= idx <= 12 else month
        return f"{name[:3]} '{year[2:]}"
    except ValueError:
        return ym


def parse_chart_date(value: Optional[str]) -> Optional[date]:
    if not value or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def default_chart_range(months: int = 6) -> Tuple[date, date]:
    today = date.today()
    month = today.month - (months - 1)
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1), today


def get_monthly_expenses(
    chart_dari: Optional[str] = None,
    chart_sampai: Optional[str] = None,
) -> Dict[str, Any]:
    default_start, default_end = default_chart_range()
    start = parse_chart_date(chart_dari) or default_start
    end = parse_chart_date(chart_sampai) or default_end
    if start > end:
        start, end = end, start

    conn = get_db()
    monthly_rows = conn.execute(
        """
        SELECT
            strftime('%Y-%m', COALESCE(tanggal, created_at)) AS bulan,
            COALESCE(SUM(jumlah), 0) AS total
        FROM tagihan
        WHERE (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')
          AND UPPER(COALESCE(status, '')) IN ('DIBAYARKAN', 'TERBAYAR')
          AND date(COALESCE(tanggal, created_at)) >= date(?)
          AND date(COALESCE(tanggal, created_at)) <= date(?)
        GROUP BY bulan
        ORDER BY bulan ASC
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    conn.close()

    monthly = [
        {"bulan": r[0], "label": format_bulan_chart(r[0]), "total": r[1]}
        for r in monthly_rows
    ]
    return {
        "monthly": monthly,
        "chart_dari": start.isoformat(),
        "chart_sampai": end.isoformat(),
        "chart_dari_display": format_tanggal_display(start.isoformat()),
        "chart_sampai_display": format_tanggal_display(end.isoformat()),
        "chart_total": sum(m["total"] for m in monthly),
        "chart_months": len(monthly),
    }


def get_dashboard_context(
    user: Dict[str, Any],
    chart_dari: str = "",
    chart_sampai: str = "",
) -> Dict[str, Any]:
    if hasattr(user, "keys"):
        user = dict(user)

    summary = get_summary()
    recent_raw = get_all_tagihan()[:6]
    recent = []
    for row in recent_raw:
        item = enrich_tagihan_item(row)
        item["tanggal_display"] = format_tanggal_display(item.get("tanggal") or "")
        recent.append(item)

    chart_data = get_monthly_expenses(chart_dari or None, chart_sampai or None)
    module_lists = build_dashboard_module_lists(user)

    conn = get_db()
    module_rows = conn.execute("""
        SELECT COALESCE(NULLIF(kategori, ''), 'tagihan') as kat, COUNT(*), COALESCE(SUM(jumlah), 0)
        FROM tagihan
        WHERE UPPER(COALESCE(status, '')) IN ('DIBAYARKAN', 'TERBAYAR')
        GROUP BY kat
        ORDER BY 3 DESC
    """).fetchall()
    pc_count = conn.execute("SELECT COUNT(*) FROM petty_cash_items").fetchone()[0] or 0
    conn.close()

    module_stats = [
        {
            "key": r[0],
            "label": MODULE_LABELS.get(r[0], r[0].replace("_", " ").title()),
            "count": r[1],
            "total": r[2],
        }
        for r in module_rows
    ]
    stats_by_kat = {s["key"]: s for s in module_stats}

    if pc_count and "petty_cash" not in stats_by_kat:
        stats_by_kat["petty_cash"] = {"key": "petty_cash", "count": pc_count, "total": 0}

    def _enrich_modules(modules: List[Dict]) -> List[Dict]:
        enriched = []
        for mod in modules:
            row = dict(mod)
            kat = row.get("key") or MODULE_HREF_KATEGORI.get(mod["href"], "")
            stat = stats_by_kat.get(kat, {})
            row["count"] = stat.get("count", 0)
            row["accent"] = MODULE_ACCENTS.get(mod["href"], row.get("accent", "default"))
            enriched.append(row)
        return enriched

    beranda_modules = _enrich_modules(module_lists["beranda_modules"])
    laporan_modules = _enrich_modules(module_lists["laporan_modules"])
    mitra_modules = _enrich_modules(module_lists["mitra_modules"])
    dashboard_module = dict(DASHBOARD_MODULE)
    dashboard_module["count"] = summary["jumlah_item"]

    today = date.today()
    pct_terbayar = round(summary["terbayar"] / summary["total"] * 100, 1) if summary["total"] else 0
    pct_diajukan = round(summary["diajukan"] / summary["total"] * 100, 1) if summary["total"] else 0

    role = (user.get("role") or "member").lower()
    if role == "admin":
        role_label = "Administrator"
    elif role == "viewer":
        role_label = "Viewer"
    elif role == "mitra":
        role_label = "Mitra"
    else:
        role_label = "Akuntan"

    return {
        "user": user,
        "summary": summary,
        "recent": recent,
        "monthly": chart_data["monthly"],
        "chart_dari": chart_data["chart_dari"],
        "chart_sampai": chart_data["chart_sampai"],
        "chart_dari_display": chart_data["chart_dari_display"],
        "chart_sampai_display": chart_data["chart_sampai_display"],
        "chart_total": chart_data["chart_total"],
        "chart_months": chart_data["chart_months"],
        "module_stats": module_stats,
        "dashboard_module": dashboard_module,
        "beranda_modules": beranda_modules,
        "laporan_modules": laporan_modules,
        "mitra_modules": mitra_modules,
        "accessible_module_count": module_lists["accessible_count"],
        "today": today.isoformat(),
        "today_display": format_tanggal_pengajuan(today.isoformat()),
        "pct_terbayar": pct_terbayar,
        "pct_diajukan": pct_diajukan,
        "role_label": role_label,
        "user_display_name": user.get("full_name") or user.get("username") or "Pengguna",
    }