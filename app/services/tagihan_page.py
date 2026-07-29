"""Page context for Laporan Tagihan."""
from typing import Any, Dict, List

from app.constants import TAGIHAN_CHARGES_AMOUNT
from app.services.report_sync import build_keuangan_link_context, filter_items_by_date_range
from app.services.tagihan import enrich_tagihan_item, get_all_tagihan
from app.utils.formatters import format_tanggal_display
from app.db import get_db


def build_tagihan_page_context(
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    kategori: str = "",
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
    if kategori:
        filters["kategori"] = kategori

    data: List[Dict[str, Any]] = []
    for raw in get_all_tagihan(filters):
        row = enrich_tagihan_item(raw)
        row["tanggal_display"] = format_tanggal_display(row.get("tanggal") or "")
        data.append(row)

    data = filter_items_by_date_range(data, dari, sampai)

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR") for item in data)
        main_status = "Sukses" if all_terbayar else "Tertagih"

    conn = get_db()
    pc_exclude = "AND (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')"
    statuses = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL {pc_exclude}"
        ).fetchall()
    ]
    rekenings = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL {pc_exclude}"
        ).fetchall()
    ]
    pos_list = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT pos FROM tagihan WHERE pos IS NOT NULL AND pos != '' {pc_exclude}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    total_charges = sum(d["charges"] for d in data)
    total_grand = total_filtered + total_charges
    terbayar_count = sum(1 for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_count = sum(1 for d in data if (d.get("status") or "").upper() == "DIAJUKAN")
    terbayar_total = sum(d["total"] for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_total = sum(d["total"] for d in data if (d.get("status") or "").upper() == "DIAJUKAN")

    return {
        "tagihan": data,
        "total_filtered": total_filtered,
        "total_charges": total_charges,
        "total_grand": total_grand,
        "terbayar_count": terbayar_count,
        "diajukan_count": diajukan_count,
        "terbayar_total": terbayar_total,
        "diajukan_total": diajukan_total,
        "tagihan_charges_amount": TAGIHAN_CHARGES_AMOUNT,
        "main_status": main_status,
        "filters": {
            "search": search,
            "status": status,
            "rekening": rekening,
            "tanggal": tanggal,
            "kategori": kategori,
            "dari": (dari or "").strip(),
            "sampai": (sampai or "").strip(),
        },
        **build_keuangan_link_context(dari, sampai, module_key="tagihan"),
        "status_options": sorted(s for s in statuses if s),
        "rekening_options": sorted(
            r for r in rekenings if r and r.strip().upper() != "PETTY CASH"
        ),
        "pos_options": sorted(p for p in pos_list if p),
    }