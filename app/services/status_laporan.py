"""Laporan pengajuan per status: DIAJUKAN, DISETUJUI, LUNAS, DITOLAK."""
from datetime import date
from typing import Any, Dict, List, Optional

from app.constants import (
    APPROVAL_KATEGORI,
    KATEGORI_LABELS,
    STATUS_DIAJUKAN,
    STATUS_DISETUJUI,
    STATUS_DITOLAK,
    STATUS_LUNAS,
)
from app.db import get_db
from app.services.finance_summary import get_bgn_transfer_totals, resolve_date_range
from app.utils.formatters import format_tanggal_display

STATUS_ORDER = [STATUS_DIAJUKAN, STATUS_DISETUJUI, STATUS_LUNAS, STATUS_DITOLAK, "LAINNYA"]

STATUS_META = {
    STATUS_DIAJUKAN: {"label": "Diajukan", "color": "amber", "icon": "fa-clock", "desc": "Menunggu persetujuan KA"},
    STATUS_DISETUJUI: {"label": "Disetujui", "color": "sky", "icon": "fa-check", "desc": "Disetujui KA, belum dibayar"},
    STATUS_LUNAS: {"label": "Lunas", "color": "emerald", "icon": "fa-circle-check", "desc": "Sudah dibayar VA — mengurangi saldo kas"},
    STATUS_DITOLAK: {"label": "Ditolak", "color": "red", "icon": "fa-ban", "desc": "Ditolak KA dengan alasan"},
    "LAINNYA": {"label": "Lainnya", "color": "slate", "icon": "fa-circle-question", "desc": "Status kosong atau tidak standar"},
}

NORMALIZE_STATUS_SQL = """
    CASE
        WHEN UPPER(COALESCE(status, '')) IN ('LUNAS', 'DIBAYARKAN', 'TERBAYAR') THEN 'LUNAS'
        WHEN UPPER(COALESCE(status, '')) = 'DISETUJUI' THEN 'DISETUJUI'
        WHEN UPPER(COALESCE(status, '')) = 'DIAJUKAN' THEN 'DIAJUKAN'
        WHEN UPPER(COALESCE(status, '')) = 'DITOLAK' THEN 'DITOLAK'
        ELSE 'LAINNYA'
    END
"""

KATEGORI_IN_SQL = ",".join("?" * len(APPROVAL_KATEGORI))


def _module_href(kategori: str) -> str:
    from app.constants import MODULE_BY_KEY

    mod = MODULE_BY_KEY.get(kategori)
    return mod.get("href", "/laporan") if mod else "/laporan"


def get_status_laporan_context(
    *,
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    status_filter: str = "",
    kategori_filter: str = "",
    search: str = "",
) -> Dict[str, Any]:
    start, end = resolve_date_range(dari, sampai, use_default=False)
    conn = get_db()

    base_where = [f"kategori IN ({KATEGORI_IN_SQL})"]
    base_params: List[Any] = list(sorted(APPROVAL_KATEGORI))

    date_clauses = []
    if start:
        date_clauses.append("date(COALESCE(tanggal, created_at)) >= date(?)")
        base_params.append(start.isoformat())
    if end:
        date_clauses.append("date(COALESCE(tanggal, created_at)) <= date(?)")
        base_params.append(end.isoformat())
    base_where.extend(date_clauses)

    where_sql = " AND ".join(base_where)

    # Ringkasan per status
    status_rows = conn.execute(
        f"""
        SELECT {NORMALIZE_STATUS_SQL} AS st,
               COUNT(*) AS cnt,
               COALESCE(SUM(jumlah), 0) AS total
        FROM tagihan
        WHERE {where_sql}
        GROUP BY st
        """,
        base_params,
    ).fetchall()
    by_status: Dict[str, Dict[str, int]] = {
        s: {"count": 0, "total": 0} for s in STATUS_ORDER
    }
    for r in status_rows:
        st = r[0] or "LAINNYA"
        by_status.setdefault(st, {"count": 0, "total": 0})
        by_status[st] = {"count": int(r[1] or 0), "total": int(r[2] or 0)}

    status_summary = []
    grand_count = 0
    grand_total = 0
    for st in STATUS_ORDER:
        row = by_status.get(st, {"count": 0, "total": 0})
        if row["count"] == 0 and st == "LAINNYA":
            continue
        meta = STATUS_META.get(st, STATUS_META["LAINNYA"])
        pct = 0.0
        status_summary.append({
            "key": st,
            "label": meta["label"],
            "color": meta["color"],
            "icon": meta["icon"],
            "desc": meta["desc"],
            "count": row["count"],
            "total": row["total"],
            "pct": pct,
        })
        grand_count += row["count"]
        grand_total += row["total"]
    for row in status_summary:
        row["pct"] = round(row["total"] / grand_total * 100, 1) if grand_total else 0.0

    # Matriks modul × status
    matrix_rows = conn.execute(
        f"""
        SELECT COALESCE(NULLIF(TRIM(kategori), ''), 'tagihan') AS kat,
               {NORMALIZE_STATUS_SQL} AS st,
               COUNT(*) AS cnt,
               COALESCE(SUM(jumlah), 0) AS total
        FROM tagihan
        WHERE {where_sql}
        GROUP BY kat, st
        ORDER BY kat, st
        """,
        base_params,
    ).fetchall()

    matrix_by_kat: Dict[str, Dict[str, Dict[str, int]]] = {}
    for r in matrix_rows:
        kat, st = r[0], r[1] or "LAINNYA"
        matrix_by_kat.setdefault(kat, {})
        matrix_by_kat[kat][st] = {"count": int(r[2] or 0), "total": int(r[3] or 0)}

    module_matrix = []
    for kat in sorted(matrix_by_kat.keys(), key=lambda k: KATEGORI_LABELS.get(k, k)):
        cells = {}
        row_total = 0
        row_count = 0
        for st in STATUS_ORDER:
            cell = matrix_by_kat[kat].get(st, {"count": 0, "total": 0})
            cells[st] = cell
            row_total += cell["total"]
            row_count += cell["count"]
        module_matrix.append({
            "kategori": kat,
            "label": KATEGORI_LABELS.get(kat, kat),
            "href": _module_href(kat),
            "cells": cells,
            "row_total": row_total,
            "row_count": row_count,
        })

    # Detail transaksi (filter opsional)
    detail_where: List[str] = []
    detail_params: List[Any] = []
    if kategori_filter and kategori_filter in APPROVAL_KATEGORI:
        detail_where.append("kategori = ?")
        detail_params.append(kategori_filter)
    else:
        detail_where.append(f"kategori IN ({KATEGORI_IN_SQL})")
        detail_params.extend(sorted(APPROVAL_KATEGORI))
    if start:
        detail_where.append("date(COALESCE(tanggal, created_at)) >= date(?)")
        detail_params.append(start.isoformat())
    if end:
        detail_where.append("date(COALESCE(tanggal, created_at)) <= date(?)")
        detail_params.append(end.isoformat())
    if status_filter and status_filter in STATUS_ORDER:
        detail_where.append(f"({NORMALIZE_STATUS_SQL}) = ?")
        detail_params.append(status_filter)
    if search.strip():
        detail_where.append("(pengajuan LIKE ? OR atas_nama LIKE ? OR no LIKE ?)")
        q = f"%{search.strip()}%"
        detail_params.extend([q, q, q])

    detail_sql = f"""
        SELECT id, no, pengajuan, jumlah, status, kategori, tanggal, atas_nama,
               rejection_note, approved_at, rejected_at,
               {NORMALIZE_STATUS_SQL} AS status_norm
        FROM tagihan
        WHERE {" AND ".join(detail_where)}
        ORDER BY
            CASE status_norm
                WHEN 'DIAJUKAN' THEN 1
                WHEN 'DISETUJUI' THEN 2
                WHEN 'DITOLAK' THEN 3
                WHEN 'LUNAS' THEN 4
                ELSE 5
            END,
            tanggal DESC, id DESC
        LIMIT 500
    """
    detail_items = [dict(r) for r in conn.execute(detail_sql, detail_params).fetchall()]
    for item in detail_items:
        kat = item.get("kategori") or "tagihan"
        item["kategori_label"] = KATEGORI_LABELS.get(kat, kat)
        item["module_href"] = _module_href(kat)
        item["status_key"] = item.pop("status_norm", item.get("status"))

    conn.close()

    bgn = get_bgn_transfer_totals(
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        use_default_range=False,
    )
    bgn_total = bgn["total_range"] if (start or end) else bgn["total_all"]

    dibayarkan = by_status.get(STATUS_LUNAS, {"total": 0})
    diajukan = by_status.get(STATUS_DIAJUKAN, {"total": 0})
    disetujui = by_status.get(STATUS_DISETUJUI, {"total": 0})
    ditolak = by_status.get(STATUS_DITOLAK, {"total": 0})
    pending_total = diajukan["total"] + disetujui["total"]

    from urllib.parse import quote

    qs_parts: List[str] = []
    date_qs_parts: List[str] = []
    if start:
        qs_parts.append(f"dari={start.isoformat()}")
        date_qs_parts.append(f"dari={start.isoformat()}")
    if end:
        qs_parts.append(f"sampai={end.isoformat()}")
        date_qs_parts.append(f"sampai={end.isoformat()}")
    if status_filter:
        qs_parts.append(f"status={status_filter}")
    if kategori_filter:
        qs_parts.append(f"kategori={kategori_filter}")
    if search.strip():
        qs_parts.append(f"search={quote(search.strip())}")
    qs = ("?" + "&".join(qs_parts)) if qs_parts else ""
    date_qs = ("?" + "&".join(date_qs_parts)) if date_qs_parts else ""

    today = date.today()
    period_filtered = bool(start or end)

    return {
        "status_summary": status_summary,
        "module_matrix": module_matrix,
        "detail_items": detail_items,
        "detail_count": len(detail_items),
        "grand_count": grand_count,
        "grand_total": grand_total,
        "bgn_masuk": bgn_total,
        "bgn_count": bgn["count_range"] if (start or end) else bgn["count_all"],
        "dibayarkan_total": dibayarkan["total"],
        "dibayarkan_count": dibayarkan["count"],
        "pending_total": pending_total,
        "pending_count": diajukan["count"] + disetujui["count"],
        "diajukan_total": diajukan["total"],
        "disetujui_total": disetujui["total"],
        "ditolak_total": ditolak["total"],
        "ditolak_count": ditolak["count"],
        "saldo_kas": bgn_total - dibayarkan["total"],
        "status_order": [s for s in STATUS_ORDER if s != "LAINNYA" or by_status.get("LAINNYA", {}).get("count")],
        "status_meta": STATUS_META,
        "kategori_options": [
            {"key": k, "label": KATEGORI_LABELS.get(k, k)}
            for k in sorted(APPROVAL_KATEGORI, key=lambda x: KATEGORI_LABELS.get(x, x))
        ],
        "filters": {
            "dari": start.isoformat() if start else "",
            "sampai": end.isoformat() if end else "",
            "status": status_filter,
            "kategori": kategori_filter,
            "search": search,
        },
        "dari": start.isoformat() if start else "",
        "sampai": end.isoformat() if end else "",
        "dari_display": format_tanggal_display(start.isoformat()) if start else "Awal",
        "sampai_display": format_tanggal_display(end.isoformat()) if end else "Akhir",
        "period_filtered": period_filtered,
        "period_label": (
            f"{format_tanggal_display(start.isoformat())} — {format_tanggal_display(end.isoformat())}"
            if start and end
            else ("Semua periode" if not period_filtered else "")
        ),
        "report_title": "Laporan Status Pengajuan",
        "report_subtitle": "Ringkasan DIAJUKAN → DISETUJUI → LUNAS dan penolakan KA SPPG",
        "generated_at_display": format_tanggal_display(today.isoformat()),
        "laporan_qs": qs,
        "laporan_href": f"/laporan{date_qs}",
        "laporan_status_href": f"/laporan/status{qs}",
        "export_csv_href": f"/export/laporan/status/csv{qs}",
        "transfer_bgn_href": f"/transfer-bgn{date_qs}",
        "dashboard_ka_href": "/dashboard-ka",
        "dashboard_bayar_href": "/dashboard-bayar",
    }