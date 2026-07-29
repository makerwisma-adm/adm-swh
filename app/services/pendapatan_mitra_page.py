"""Page context untuk Laporan Pendapatan Mitra (sumber: insentif mitra)."""
from collections import defaultdict
from typing import Any, Dict, List

from app.services.report_sync import build_keuangan_link_context, date_range_filters
from app.services.transfer_reports import get_insentif_mitra, get_insentif_mitra_laporans
from app.utils.formatters import format_tanggal_display
from app.db import get_db


def _enrich_insentif_items(data: List[Dict[str, Any]]) -> None:
    periode_options = get_insentif_mitra_laporans(active_only=True)
    periode_map = {
        lap["upload_id"]: lap.get("periode") or lap.get("filename")
        for lap in periode_options
    }
    for item in data:
        uid = item.get("upload_id")
        if uid:
            item["periode_label"] = periode_map.get(uid, "Input Manual")
        else:
            item["periode_label"] = (item.get("pos") or "").strip() or "Input Manual"
        item["tanggal_display"] = format_tanggal_display(item.get("tanggal") or "")


def _group_by_periode(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "total": 0, "terbayar": 0})
    for item in items:
        label = item.get("periode_label") or "Input Manual"
        groups[label]["label"] = label
        groups[label]["count"] += 1
        jumlah = int(item.get("jumlah") or 0)
        groups[label]["total"] += jumlah
        if (item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"):
            groups[label]["terbayar"] += jumlah
    return sorted(groups.values(), key=lambda g: g["label"], reverse=True)


def build_pendapatan_mitra_page_context(
    search: str = "",
    status: str = "",
    periode: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if tanggal:
        filters["tanggal"] = tanggal
    filters.update(date_range_filters(dari, sampai))

    data = get_insentif_mitra(filters)
    _enrich_insentif_items(data)

    if periode:
        needle = periode.strip().lower()
        data = [d for d in data if needle in (d.get("periode_label") or "").lower()]

    conn = get_db()
    im_filter = "kategori = 'insentif_mitra'"
    statuses = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {im_filter}"
        ).fetchall()
    ]
    periode_labels = sorted({
        (r[0] or "").strip()
        for r in conn.execute(
            f"""SELECT DISTINCT COALESCE(NULLIF(pos, ''), 'Input Manual') AS p
                FROM tagihan WHERE {im_filter} AND upload_id IS NULL"""
        ).fetchall()
        if (r[0] or "").strip()
    })
    for lap in get_insentif_mitra_laporans(active_only=True):
        label = (lap.get("periode") or lap.get("filename") or "").strip()
        if label and label not in periode_labels:
            periode_labels.append(label)
    conn.close()

    total_filtered = sum(int(d.get("jumlah") or 0) for d in data)
    terbayar_count = sum(1 for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_count = sum(1 for d in data if (d.get("status") or "").upper() == "DIAJUKAN")
    terbayar_total = sum(
        int(d.get("jumlah") or 0) for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR")
    )
    diajukan_total = sum(
        int(d.get("jumlah") or 0) for d in data if (d.get("status") or "").upper() == "DIAJUKAN"
    )

    return {
        "items": data,
        "by_periode": _group_by_periode(data),
        "total_filtered": total_filtered,
        "terbayar_count": terbayar_count,
        "diajukan_count": diajukan_count,
        "terbayar_total": terbayar_total,
        "diajukan_total": diajukan_total,
        "filters": {
            "search": search,
            "status": status,
            "periode": periode,
            "tanggal": tanggal,
            "dari": (dari or "").strip(),
            "sampai": (sampai or "").strip(),
        },
        **build_keuangan_link_context(dari, sampai, module_key="pendapatan_mitra"),
        "status_options": sorted(s for s in statuses if s),
        "periode_options": sorted(periode_labels),
    }