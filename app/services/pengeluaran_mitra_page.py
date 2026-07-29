"""Page context untuk Pengeluaran Mitra."""
from typing import Any, Dict

from app.services.report_sync import build_keuangan_link_context, date_range_filters
from app.services.transfer_reports import get_pengeluaran_mitra
from app.utils.formatters import format_tanggal_display
from app.db import get_db


def build_pengeluaran_mitra_page_context(
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal
    filters.update(date_range_filters(dari, sampai))

    data = get_pengeluaran_mitra(filters)
    for item in data:
        item["tanggal_display"] = format_tanggal_display(item.get("tanggal") or "")

    conn = get_db()
    pm_filter = "kategori = 'pengeluaran_mitra'"
    statuses = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {pm_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {pm_filter}"
        ).fetchall()
    ]
    tanggals = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT tanggal FROM tagihan WHERE tanggal IS NOT NULL AND tanggal != '' AND {pm_filter}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    terbayar_count = sum(1 for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_count = sum(1 for d in data if (d.get("status") or "").upper() == "DIAJUKAN")
    terbayar_total = sum(d["jumlah"] for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_total = sum(d["jumlah"] for d in data if (d.get("status") or "").upper() == "DIAJUKAN")

    return {
        "items": data,
        "total_filtered": total_filtered,
        "terbayar_count": terbayar_count,
        "diajukan_count": diajukan_count,
        "terbayar_total": terbayar_total,
        "diajukan_total": diajukan_total,
        "filters": {
            "search": search,
            "status": status,
            "rekening": rekening,
            "tanggal": tanggal,
            "dari": (dari or "").strip(),
            "sampai": (sampai or "").strip(),
        },
        **build_keuangan_link_context(dari, sampai, module_key="pengeluaran_mitra"),
        "status_options": sorted(s for s in statuses if s),
        "rekening_options": sorted(r for r in rekenings if r),
        "tanggal_options": sorted(tanggals, reverse=True),
    }