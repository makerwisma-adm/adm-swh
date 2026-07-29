"""Page context for Laporan Insentif Mitra."""
from typing import Any, Dict, List, Optional

from app.constants import (
    FEE_PAYROL_PER_ORANG,
    INSENTIF_MITRA_HARI,
    INSENTIF_MITRA_JUMLAH,
    INSENTIF_MITRA_PER_HARI,
)
from app.services.report_sync import build_keuangan_link_context, date_range_filters
from app.services.transfer_reports import get_insentif_mitra, get_insentif_mitra_laporans
from app.utils.formatters import format_tanggal_display
from app.db import get_db


def build_insentif_mitra_page_context(
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
) -> Dict[str, Any]:
    periode_options = get_insentif_mitra_laporans(active_only=True)
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

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

    laporan: Optional[Dict[str, Any]] = None
    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_insentif_mitra(filters)
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

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR") for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    ip_filter = "kategori = 'insentif_mitra'"
    statuses = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0]
        for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    terbayar_count = sum(1 for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_count = sum(1 for d in data if (d.get("status") or "").upper() == "DIAJUKAN")
    terbayar_total = sum(d["jumlah"] for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_total = sum(d["jumlah"] for d in data if (d.get("status") or "").upper() == "DIAJUKAN")

    laporan_meta = None
    if laporan:
        laporan_meta = {
            "periode": laporan.get("periode") or laporan.get("filename") or "—",
            "tanggal": format_tanggal_display(laporan.get("tanggal_pembayaran") or ""),
            "rekening_sumber": laporan.get("rekening_sumber") or "—",
            "bank": laporan.get("bank") or "MANDIRI",
            "kota": laporan.get("kota") or "—",
            "penerima": laporan.get("jumlah_penerima") or laporan.get("record_count") or 0,
            "total_laporan": laporan.get("total_gaji") or 0,
        }

    return {
        "items": data,
        "laporans": periode_options,
        "laporan": laporan,
        "laporan_meta": laporan_meta,
        "view_all": upload_id == 0,
        "selected_upload_id": upload_id or 0,
        "total_filtered": total_filtered,
        "terbayar_count": terbayar_count,
        "diajukan_count": diajukan_count,
        "terbayar_total": terbayar_total,
        "diajukan_total": diajukan_total,
        "insentif_mitra_jumlah": INSENTIF_MITRA_JUMLAH,
        "insentif_mitra_per_hari": INSENTIF_MITRA_PER_HARI,
        "insentif_mitra_hari": INSENTIF_MITRA_HARI,
        "fee_payrol_amount": FEE_PAYROL_PER_ORANG,
        "main_status": main_status,
        "filters": {
            "search": search,
            "status": status,
            "rekening": rekening,
            "tanggal": tanggal,
            "periode": upload_id,
            "dari": (dari or "").strip(),
            "sampai": (sampai or "").strip(),
        },
        **build_keuangan_link_context(dari, sampai, module_key="insentif_mitra"),
        "periode_options": periode_options,
        "status_options": sorted(s for s in statuses if s),
        "rekening_options": sorted(r for r in rekenings if r),
    }