"""Ringkasan keuangan: transfer BGN, pengeluaran semua modul, laporan gabungan."""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.constants import ID_MONTH_NAMES
from app.utils.formatters import format_tanggal_display
from app.db import get_db

MODULE_REPORTS = [
    {
        "key": "tagihan",
        "label": "Laporan Tagihan",
        "href": "/tagihan",
        "icon": "fa-file-invoice-dollar",
        "accent": "tagihan",
    },
    {
        "key": "petty_cash",
        "label": "Petty Cash",
        "href": "/petty-cash",
        "icon": "fa-wallet",
        "accent": "petty",
    },
    {
        "key": "gaji_relawan",
        "label": "Gaji Relawan",
        "href": "/gaji-relawan",
        "icon": "fa-users",
        "accent": "gaji",
    },
    {
        "key": "gaji_staff",
        "label": "Gaji Staff",
        "href": "/gaji-staff",
        "icon": "fa-id-badge",
        "accent": "staff",
    },
    {
        "key": "insentif_pic",
        "label": "Insentif PIC",
        "href": "/insentif-pic",
        "icon": "fa-user-tie",
        "accent": "insentif",
    },
    {
        "key": "insentif_mitra",
        "label": "Insentif Mitra",
        "href": "/insentif-mitra",
        "icon": "fa-handshake",
        "accent": "insentif",
    },
    {
        "key": "pendapatan_mitra",
        "label": "Pendapatan Mitra",
        "href": "/pendapatan-mitra",
        "icon": "fa-sack-dollar",
        "accent": "mitra",
        "derived_from": "insentif_mitra",
    },
    {
        "key": "pengembalian_dana",
        "label": "Pengembalian Dana",
        "href": "/pengembalian-dana",
        "icon": "fa-rotate-left",
        "accent": "refund",
    },
    {
        "key": "sewa_kendaraan",
        "label": "Sewa Kendaraan",
        "href": "/sewa-kendaraan",
        "icon": "fa-car",
        "accent": "sewa",
    },
    {
        "key": "pengajuan_dana_mitra",
        "label": "Pengajuan Dana Mitra",
        "href": "/pengajuan-dana-mitra",
        "icon": "fa-file-invoice",
        "accent": "mitra",
    },
    {
        "key": "pengeluaran_mitra",
        "label": "Pengeluaran Mitra",
        "href": "/pengeluaran-mitra",
        "icon": "fa-money-bill-transfer",
        "accent": "mitra",
    },
]

MODULE_BY_KEY = {m["key"]: m for m in MODULE_REPORTS}

# Saldo BGN hanya berkurang untuk pengeluaran yang sudah DIBAYARKAN (kas riil keluar).
from app.constants import PAID_STATUS_SQL  # noqa: E402 — used below
PENDING_STATUS_SQL = "UPPER(COALESCE(status, '')) IN ('DIAJUKAN', 'DISETUJUI')"


def _date_range_clauses(
    start: Optional[date],
    end: Optional[date],
    *,
    date_col: str = "COALESCE(tanggal, created_at)",
) -> Tuple[List[str], List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if start:
        clauses.append(f"date({date_col}) >= date(?)")
        params.append(start.isoformat())
    if end:
        clauses.append(f"date({date_col}) <= date(?)")
        params.append(end.isoformat())
    return clauses, params


def parse_range_date(value: Optional[str]) -> Optional[date]:
    if not value or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def default_report_range(months: int = 6) -> Tuple[date, date]:
    today = date.today()
    month = today.month - (months - 1)
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1), today


def resolve_date_range(
    dari: Optional[str],
    sampai: Optional[str],
    *,
    use_default: bool = True,
) -> Tuple[Optional[date], Optional[date]]:
    has_input = bool((dari or "").strip() or (sampai or "").strip())
    if not has_input and not use_default:
        return None, None
    default_start, default_end = default_report_range()
    start = parse_range_date(dari) or (default_start if use_default or (sampai or "").strip() else None)
    end = parse_range_date(sampai) or (default_end if use_default or (dari or "").strip() else None)
    if start and end and start > end:
        start, end = end, start
    return start, end


def format_bulan_label(ym: str) -> str:
    if not ym or "-" not in ym:
        return ym or "—"
    year, month = ym.split("-", 1)
    try:
        idx = int(month)
        name = ID_MONTH_NAMES[idx] if 1 <= idx <= 12 else month
        return f"{name} {year}"
    except ValueError:
        return ym


def _petty_expense_amount(row: Dict[str, Any]) -> int:
    kredit = int(row.get("kredit") or 0)
    if kredit > 0:
        return kredit
    return int(row.get("jumlah") or 0)


def get_tagihan_expense_by_kategori(
    start: Optional[date] = None,
    end: Optional[date] = None,
    *,
    paid_only: bool = True,
) -> Dict[str, Dict[str, Any]]:
    conn = get_db()
    query = """
        SELECT COALESCE(NULLIF(TRIM(kategori), ''), 'tagihan') AS kat,
               COUNT(*) AS cnt,
               COALESCE(SUM(jumlah), 0) AS total
        FROM tagihan
    """
    where: List[str] = []
    params: List[Any] = []
    if paid_only:
        where.append(PAID_STATUS_SQL)
    date_clauses, date_params = _date_range_clauses(start, end)
    where.extend(date_clauses)
    params.extend(date_params)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " GROUP BY kat"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {r[0]: {"count": r[1], "total": r[2]} for r in rows}


def get_pending_expense_totals(
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Dict[str, int]:
    """Total DIAJUKAN + DISETUJUI — belum mengurangi saldo kas."""
    conn = get_db()
    where = [PENDING_STATUS_SQL]
    date_clauses, date_params = _date_range_clauses(start, end)
    where.extend(date_clauses)
    row = conn.execute(
        f"""
        SELECT COUNT(*), COALESCE(SUM(jumlah), 0)
        FROM tagihan
        WHERE {" AND ".join(where)}
        """,
        date_params,
    ).fetchone()
    conn.close()
    return {"count": int(row[0] or 0), "total": int(row[1] or 0)}


def get_petty_cash_expense(start: Optional[date] = None, end: Optional[date] = None) -> Dict[str, Any]:
    conn = get_db()
    query = """
        SELECT id, pengajuan, jumlah, kredit, debit, tanggal, created_at
        FROM petty_cash_items
    """
    params: List[Any] = []
    where = []
    if start:
        where.append("date(COALESCE(tanggal, created_at)) >= date(?)")
        params.append(start.isoformat())
    if end:
        where.append("date(COALESCE(tanggal, created_at)) <= date(?)")
        params.append(end.isoformat())
    if where:
        query += " WHERE " + " AND ".join(where)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    total = sum(_petty_expense_amount(dict(r)) for r in rows)
    return {"count": len(rows), "total": total}


def get_expense_module_summary(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    *,
    use_default_range: bool = False,
) -> Dict[str, Any]:
    start, end = resolve_date_range(dari, sampai, use_default=use_default_range)
    tagihan_stats = get_tagihan_expense_by_kategori(start, end)
    petty_stats = get_petty_cash_expense(start, end)

    modules: List[Dict[str, Any]] = []
    grand_total = 0
    grand_count = 0

    for meta in MODULE_REPORTS:
        key = meta["key"]
        source_key = meta.get("derived_from") or key
        if key == "petty_cash":
            stat = petty_stats
        else:
            stat = tagihan_stats.get(source_key, {"count": 0, "total": 0})
        href = meta["href"]
        if start or end:
            qs = []
            if start:
                qs.append(f"dari={start.isoformat()}")
            if end:
                qs.append(f"sampai={end.isoformat()}")
            href = f"{href}?{'&'.join(qs)}"
        row = {
            **meta,
            "href": href,
            "count": stat["count"],
            "total": stat["total"],
            "is_derived": bool(meta.get("derived_from")),
        }
        modules.append(row)
        if not meta.get("derived_from"):
            grand_total += stat["total"]
            grand_count += stat["count"]

    filtered = start is not None or end is not None
    dari_iso = start.isoformat() if start else ""
    sampai_iso = end.isoformat() if end else ""
    if filtered:
        dari_display = format_tanggal_display(dari_iso)
        sampai_display = format_tanggal_display(sampai_iso)
    else:
        dari_display = "Semua"
        sampai_display = "periode"

    return {
        "dari": dari_iso,
        "sampai": sampai_iso,
        "dari_display": dari_display,
        "sampai_display": sampai_display,
        "period_filtered": filtered,
        "modules": modules,
        "grand_total": grand_total,
        "grand_count": grand_count,
    }


def get_monthly_expense_all(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    *,
    use_default_range: bool = False,
) -> List[Dict[str, Any]]:
    start, end = resolve_date_range(dari, sampai, use_default=use_default_range)
    conn = get_db()
    tagihan_query = """
        SELECT strftime('%Y-%m', COALESCE(tanggal, created_at)) AS bulan,
               COALESCE(SUM(jumlah), 0) AS total
        FROM tagihan
    """
    tagihan_where = [PAID_STATUS_SQL]
    tagihan_params: List[Any] = []
    date_clauses, date_params = _date_range_clauses(start, end)
    tagihan_where.extend(date_clauses)
    tagihan_params.extend(date_params)
    if tagihan_where:
        tagihan_query += " WHERE " + " AND ".join(tagihan_where)
    tagihan_query += " GROUP BY bulan"
    tagihan_rows = conn.execute(tagihan_query, tagihan_params).fetchall()

    petty_query = """
        SELECT strftime('%Y-%m', COALESCE(tanggal, created_at)) AS bulan,
               id, jumlah, kredit
        FROM petty_cash_items
    """
    petty_params: List[Any] = []
    petty_where = []
    if start:
        petty_where.append("date(COALESCE(tanggal, created_at)) >= date(?)")
        petty_params.append(start.isoformat())
    if end:
        petty_where.append("date(COALESCE(tanggal, created_at)) <= date(?)")
        petty_params.append(end.isoformat())
    if petty_where:
        petty_query += " WHERE " + " AND ".join(petty_where)
    petty_rows = conn.execute(petty_query, petty_params).fetchall()
    conn.close()

    by_month: Dict[str, int] = {}
    for r in tagihan_rows:
        by_month[r[0]] = by_month.get(r[0], 0) + int(r[1] or 0)
    for r in petty_rows:
        amount = int(r[3] or 0) if int(r[3] or 0) > 0 else int(r[2] or 0)
        by_month[r[0]] = by_month.get(r[0], 0) + amount

    return [
        {"bulan": ym, "label": format_bulan_label(ym), "total": by_month[ym]}
        for ym in sorted(by_month.keys())
    ]


def get_bgn_transfers(
    search: str = "",
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conn = get_db()
    query = "SELECT * FROM bgn_transfers"
    params: List[Any] = []
    where = []
    if search.strip():
        s = f"%{search.strip()}%"
        where.append("(keterangan LIKE ? OR no_referensi LIKE ? OR periode LIKE ?)")
        params.extend([s, s, s])
    start, end = resolve_date_range(dari, sampai, use_default=False)
    if start:
        where.append("date(tanggal) >= date(?)")
        params.append(start.isoformat())
    if end:
        where.append("date(tanggal) <= date(?)")
        params.append(end.isoformat())
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY COALESCE(tanggal, '9999') DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_expense_total_all() -> Dict[str, int]:
    conn = get_db()
    tagihan_total = conn.execute(
        f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan WHERE {PAID_STATUS_SQL}"
    ).fetchone()[0] or 0
    tagihan_count = conn.execute(
        f"SELECT COUNT(*) FROM tagihan WHERE {PAID_STATUS_SQL}"
    ).fetchone()[0] or 0
    petty_rows = conn.execute(
        "SELECT jumlah, kredit FROM petty_cash_items"
    ).fetchall()
    conn.close()
    petty_total = sum(_petty_expense_amount(dict(r)) for r in petty_rows)
    return {
        "total": int(tagihan_total) + petty_total,
        "count": int(tagihan_count) + len(petty_rows),
    }


def get_monthly_bgn_transfers(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    *,
    use_default_range: bool = False,
) -> List[Dict[str, Any]]:
    start, end = resolve_date_range(dari, sampai, use_default=use_default_range)
    conn = get_db()
    query = """
        SELECT strftime('%Y-%m', tanggal) AS bulan,
               COALESCE(SUM(jumlah), 0) AS total,
               COUNT(*) AS cnt
        FROM bgn_transfers
    """
    params: List[Any] = []
    where = []
    if start:
        where.append("date(tanggal) >= date(?)")
        params.append(start.isoformat())
    if end:
        where.append("date(tanggal) <= date(?)")
        params.append(end.isoformat())
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " GROUP BY bulan ORDER BY bulan ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [
        {"bulan": r[0], "label": format_bulan_label(r[0]), "total": int(r[1] or 0), "count": int(r[2] or 0)}
        for r in rows
    ]


def _merge_monthly_flow(
    monthly_in: List[Dict[str, Any]],
    monthly_out: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_in = {m["bulan"]: m for m in monthly_in}
    by_out = {m["bulan"]: m for m in monthly_out}
    months = sorted(set(by_in) | set(by_out))
    result = []
    for ym in months:
        masuk = by_in.get(ym, {}).get("total", 0)
        keluar = by_out.get(ym, {}).get("total", 0)
        result.append({
            "bulan": ym,
            "label": format_bulan_label(ym),
            "masuk": masuk,
            "keluar": keluar,
            "saldo": masuk - keluar,
            "masuk_count": by_in.get(ym, {}).get("count", 0),
            "keluar_count": 0,
        })
    return result


def get_transfer_bgn_laporan_context(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Laporan khusus Transfer BGN: input (masuk) vs output (pengeluaran operasional)."""
    ctx = get_transfer_bgn_context(dari=dari, sampai=sampai, user=user)
    total_keluar = ctx["total_keluar"]
    expense_modules = []
    for mod in ctx["expense_modules"]:
        row = dict(mod)
        row["pct"] = round(row["total"] / total_keluar * 100, 1) if total_keluar else 0.0
        expense_modules.append(row)

    monthly_in = get_monthly_bgn_transfers(dari, sampai, use_default_range=False)
    monthly_out = get_monthly_expense_all(dari, sampai, use_default_range=False)
    monthly_flow = _merge_monthly_flow(monthly_in, monthly_out)

    start, end = resolve_date_range(dari, sampai, use_default=False)
    pending_all = get_pending_expense_totals(None, None)
    anggaran_global = build_bgn_anggaran_global(
        total_masuk=ctx["total_masuk"],
        total_keluar=ctx["total_keluar"],
        pending_total=ctx["pending_expense_total"],
        pending_count=ctx["pending_expense_count"],
        expense_modules=expense_modules,
        total_masuk_all=int(ctx["total_masuk_all"] or 0),
        total_keluar_all=int(ctx["total_keluar_all"] or 0),
        pending_all_total=pending_all["total"],
        pending_all_count=pending_all["count"],
        period_label=ctx["period_label"],
        period_filtered=ctx["period_filtered"],
        start=start,
        end=end,
    )

    qs = ctx["laporan_qs"]
    today = date.today()
    return {
        **ctx,
        "expense_modules": expense_modules,
        "anggaran_global": anggaran_global,
        "monthly_flow": monthly_flow,
        "monthly_in": monthly_in,
        "monthly_out": monthly_out,
        "report_title": "Laporan Transfer BGN — Input & Output",
        "report_subtitle": "Dana operasional BGN: uang masuk dan pemakaian (termasuk insentif mitra)",
        "generated_at": today.isoformat(),
        "generated_at_display": format_tanggal_display(today.isoformat()),
        "laporan_bgn_href": f"/transfer-bgn/laporan{qs}",
        "export_csv_href": f"/export/transfer-bgn/csv{qs}",
        "kelola_href": f"/transfer-bgn{qs}",
    }


def get_anggaran_status_breakdown(
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Pipeline pengajuan per status (modul persetujuan KA)."""
    from app.constants import APPROVAL_KATEGORI

    conn = get_db()
    placeholders = ",".join("?" * len(APPROVAL_KATEGORI))
    where = [f"kategori IN ({placeholders})"]
    params: List[Any] = list(sorted(APPROVAL_KATEGORI))
    date_clauses, date_params = _date_range_clauses(start, end)
    where.extend(date_clauses)
    params.extend(date_params)

    rows = conn.execute(
        f"""
        SELECT
            CASE
                WHEN {PAID_STATUS_SQL} THEN 'LUNAS'
                WHEN UPPER(COALESCE(status, '')) = 'DISETUJUI' THEN 'DISETUJUI'
                WHEN UPPER(COALESCE(status, '')) = 'DIAJUKAN' THEN 'DIAJUKAN'
                WHEN UPPER(COALESCE(status, '')) = 'DITOLAK' THEN 'DITOLAK'
                ELSE 'LAINNYA'
            END AS status_key,
            COUNT(*) AS cnt,
            COALESCE(SUM(jumlah), 0) AS total
        FROM tagihan
        WHERE {" AND ".join(where)}
        GROUP BY status_key
        """,
        params,
    ).fetchall()
    conn.close()

    meta = {
        "LUNAS": {"label": "Lunas (sudah keluar kas)", "color": "emerald", "order": 1},
        "DISETUJUI": {"label": "Disetujui (menunggu bayar)", "color": "sky", "order": 2},
        "DIAJUKAN": {"label": "Diajukan (menunggu KA)", "color": "amber", "order": 3},
        "DITOLAK": {"label": "Ditolak", "color": "red", "order": 4},
        "LAINNYA": {"label": "Lainnya", "color": "slate", "order": 5},
    }
    by_key = {r["status_key"]: {"count": int(r["cnt"] or 0), "total": int(r["total"] or 0)} for r in rows}
    result = []
    for key in sorted(meta.keys(), key=lambda k: meta[k]["order"]):
        stat = by_key.get(key, {"count": 0, "total": 0})
        if stat["count"] == 0 and key == "LAINNYA":
            continue
        result.append({
            "key": key,
            **meta[key],
            "count": stat["count"],
            "total": stat["total"],
        })
    return result


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def build_bgn_anggaran_global(
    *,
    total_masuk: int,
    total_keluar: int,
    pending_total: int,
    pending_count: int,
    expense_modules: List[Dict[str, Any]],
    total_masuk_all: int,
    total_keluar_all: int,
    pending_all_total: int,
    pending_all_count: int,
    period_label: str,
    period_filtered: bool,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Dict[str, Any]:
    """Laporan penggunaan anggaran BGN — global & periode aktif."""
    saldo_period = total_masuk - total_keluar
    saldo_global = total_masuk_all - total_keluar_all
    committed_period = total_keluar + pending_total
    committed_global = total_keluar_all + pending_all_total

    base_masuk_modules = total_masuk if period_filtered else total_masuk_all
    base_keluar_modules = total_keluar if period_filtered else total_keluar_all

    modules_report = []
    for mod in expense_modules:
        if mod.get("is_derived"):
            continue
        total_mod = int(mod.get("total") or 0)
        modules_report.append({
            **mod,
            "pct_budget": _pct(total_mod, base_masuk_modules),
            "pct_spent": _pct(total_mod, base_keluar_modules),
        })
    modules_report.sort(key=lambda m: m.get("total", 0), reverse=True)

    status_global = get_anggaran_status_breakdown(None, None)
    status_period = get_anggaran_status_breakdown(start, end) if period_filtered else status_global

    return {
        "period_label": period_label,
        "period_filtered": period_filtered,
        "global": {
            "total_masuk": total_masuk_all,
            "total_keluar": total_keluar_all,
            "saldo": saldo_global,
            "pending_total": pending_all_total,
            "pending_count": pending_all_count,
            "committed_total": committed_global,
            "sisa_anggaran": saldo_global,
            "sisa_setelah_komitmen": total_masuk_all - committed_global,
            "utilization_pct": _pct(total_keluar_all, total_masuk_all),
            "projected_utilization_pct": _pct(committed_global, total_masuk_all),
        },
        "period": {
            "total_masuk": total_masuk,
            "total_keluar": total_keluar,
            "saldo": saldo_period,
            "pending_total": pending_total,
            "pending_count": pending_count,
            "committed_total": committed_period,
            "sisa_anggaran": saldo_period,
            "sisa_setelah_komitmen": total_masuk - committed_period,
            "utilization_pct": _pct(total_keluar, total_masuk),
            "projected_utilization_pct": _pct(committed_period, total_masuk),
        },
        "modules": modules_report,
        "status_global": status_global,
        "status_period": status_period,
    }


def get_bgn_saldo_snapshot() -> Dict[str, Any]:
    """Ringkasan saldo kas BGN (semua periode) untuk dashboard KA & Maker."""
    bgn = get_bgn_transfer_totals(use_default_range=False)
    expense = get_expense_total_all()
    pending = get_pending_expense_totals(None, None)
    total_masuk = int(bgn["total_all"] or 0)
    total_keluar = int(expense["total"] or 0)
    return {
        "total_masuk": total_masuk,
        "total_keluar": total_keluar,
        "bgn_count": int(bgn["count_all"] or 0),
        "expense_count": int(expense["count"] or 0),
        "saldo": total_masuk - total_keluar,
        "pending_expense_total": int(pending["total"] or 0),
        "pending_expense_count": int(pending["count"] or 0),
        "transfer_bgn_href": "/transfer-bgn",
    }


def get_bgn_transfer_totals(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    *,
    use_default_range: bool = False,
) -> Dict[str, Any]:
    start, end = resolve_date_range(dari, sampai, use_default=use_default_range)
    conn = get_db()
    bgn_query = "SELECT COUNT(*), COALESCE(SUM(jumlah), 0) FROM bgn_transfers"
    bgn_params: List[Any] = []
    bgn_where = []
    if start:
        bgn_where.append("date(tanggal) >= date(?)")
        bgn_params.append(start.isoformat())
    if end:
        bgn_where.append("date(tanggal) <= date(?)")
        bgn_params.append(end.isoformat())
    if bgn_where:
        bgn_query += " WHERE " + " AND ".join(bgn_where)
    row = conn.execute(bgn_query, bgn_params).fetchone()
    all_row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(jumlah), 0) FROM bgn_transfers"
    ).fetchone()
    conn.close()
    return {
        "count_range": row[0] or 0,
        "total_range": row[1] or 0,
        "count_all": all_row[0] or 0,
        "total_all": all_row[1] or 0,
    }


def _build_period_href(base_href: str, start: Optional[date], end: Optional[date]) -> str:
    if not start and not end:
        return base_href
    qs = []
    if start:
        qs.append(f"dari={start.isoformat()}")
    if end:
        qs.append(f"sampai={end.isoformat()}")
    return f"{base_href}?{'&'.join(qs)}"


def get_transfer_bgn_context(
    search: str = "",
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from app.services.user_access import get_user_menu_keys

    start, end = resolve_date_range(dari, sampai, use_default=False)
    dari_arg = start.isoformat() if start else None
    sampai_arg = end.isoformat() if end else None

    expense = get_expense_module_summary(dari_arg, sampai_arg, use_default_range=False)
    expense_all = get_expense_total_all()
    bgn = get_bgn_transfer_totals(dari_arg, sampai_arg, use_default_range=False)
    transfers = get_bgn_transfers(search, dari_arg, sampai_arg)

    menu_keys = get_user_menu_keys(user) if user else None
    expense_modules = expense["modules"]
    if menu_keys is not None:
        expense_modules = [
            m for m in expense_modules
            if m.get("key") in menu_keys and not m.get("is_derived")
        ]

    total_masuk = bgn["total_range"] if (start or end) else bgn["total_all"]
    total_keluar = expense["grand_total"] if (start or end) else expense_all["total"]
    saldo = total_masuk - total_keluar
    bgn_count = bgn["count_range"] if (start or end) else bgn["count_all"]
    expense_count = expense["grand_count"] if (start or end) else expense_all["count"]
    pending = get_pending_expense_totals(start, end)
    pending_all = get_pending_expense_totals(None, None)

    anggaran_global = build_bgn_anggaran_global(
        total_masuk=total_masuk,
        total_keluar=total_keluar,
        pending_total=pending["total"],
        pending_count=pending["count"],
        expense_modules=expense_modules,
        total_masuk_all=int(bgn["total_all"] or 0),
        total_keluar_all=int(expense_all["total"] or 0),
        pending_all_total=pending_all["total"],
        pending_all_count=pending_all["count"],
        period_label=f"{expense['dari_display']} — {expense['sampai_display']}",
        period_filtered=bool(start or end),
        start=start,
        end=end,
    )

    laporan_qs = ""
    if start or end:
        parts = []
        if start:
            parts.append(f"dari={start.isoformat()}")
        if end:
            parts.append(f"sampai={end.isoformat()}")
        laporan_qs = "?" + "&".join(parts)

    return {
        "items": transfers,
        "expense_modules": expense_modules,
        "grand_expense": expense["grand_total"],
        "grand_expense_count": expense["grand_count"],
        "total_masuk": total_masuk,
        "total_masuk_all": bgn["total_all"],
        "total_keluar": total_keluar,
        "total_keluar_all": expense_all["total"],
        "saldo": saldo,
        "saldo_all": bgn["total_all"] - expense_all["total"],
        "bgn_count": bgn_count,
        "bgn_count_all": bgn["count_all"],
        "expense_count": expense_count,
        "expense_count_all": expense_all["count"],
        "pending_expense_total": pending["total"],
        "pending_expense_count": pending["count"],
        "period_filtered": expense["period_filtered"],
        "period_label": f"{expense['dari_display']} — {expense['sampai_display']}",
        "laporan_qs": laporan_qs,
        "laporan_href": f"/laporan{laporan_qs}",
        "transfer_bgn_href": f"/transfer-bgn{laporan_qs}",
        "laporan_bgn_href": f"/transfer-bgn/laporan{laporan_qs}",
        "export_bgn_csv_href": f"/export/transfer-bgn/csv{laporan_qs}",
        "filters": {
            "search": search,
            "dari": expense["dari"],
            "sampai": expense["sampai"],
        },
        "dari_display": expense["dari_display"],
        "sampai_display": expense["sampai_display"],
        "anggaran_global": anggaran_global,
    }


def get_laporan_context(dari: Optional[str] = None, sampai: Optional[str] = None) -> Dict[str, Any]:
    start, end = resolve_date_range(dari, sampai, use_default=False)
    expense = get_expense_module_summary(dari, sampai, use_default_range=False)
    monthly = get_monthly_expense_all(dari, sampai, use_default_range=False)
    bgn = get_bgn_transfer_totals(dari, sampai, use_default_range=False)
    bgn_total = bgn["total_range"] if (start or end) else bgn["total_all"]
    bgn_count = bgn["count_range"] if (start or end) else bgn["count_all"]
    pending = get_pending_expense_totals(start, end)
    laporan_qs = ""
    if start or end:
        parts = []
        if start:
            parts.append(f"dari={start.isoformat()}")
        if end:
            parts.append(f"sampai={end.isoformat()}")
        laporan_qs = "?" + "&".join(parts)
    return {
        **expense,
        "monthly": monthly,
        "bgn_masuk": bgn_total,
        "bgn_count": bgn_count,
        "saldo": bgn_total - expense["grand_total"],
        "pending_expense_total": pending["total"],
        "pending_expense_count": pending["count"],
        "laporan_qs": laporan_qs,
        "laporan_href": f"/laporan{laporan_qs}",
        "transfer_bgn_href": f"/transfer-bgn{laporan_qs}",
        "bgn_module": {
            "key": "transfer_bgn",
            "label": "Transfer BGN (Masuk)",
            "href": f"/transfer-bgn{laporan_qs}",
            "icon": "fa-building-columns",
            "accent": "tagihan",
            "count": bgn_count,
            "total": bgn_total,
            "is_income": True,
        },
    }