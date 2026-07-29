"""Terapkan filter mitra dan hitung ulang ringkasan halaman."""
from typing import Any, Dict, List

from app.services.mitra_access import filter_items_for_mitra


def _recalc_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_filtered = sum(int(d.get("jumlah") or 0) for d in items)
    terbayar_count = sum(1 for d in items if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_count = sum(1 for d in items if (d.get("status") or "").upper() == "DIAJUKAN")
    terbayar_total = sum(
        int(d.get("jumlah") or 0) for d in items if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR")
    )
    diajukan_total = sum(
        int(d.get("jumlah") or 0) for d in items if (d.get("status") or "").upper() == "DIAJUKAN"
    )
    if not items:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR") for item in items)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"
    return {
        "items": items,
        "total_filtered": total_filtered,
        "terbayar_count": terbayar_count,
        "diajukan_count": diajukan_count,
        "terbayar_total": terbayar_total,
        "diajukan_total": diajukan_total,
        "main_status": main_status,
    }


def apply_mitra_page_filter(ctx: Dict[str, Any], mitra_nama: str) -> Dict[str, Any]:
    filtered = filter_items_for_mitra(ctx.get("items") or [], mitra_nama)
    ctx.update(_recalc_summary(filtered))
    ctx["mitra_view"] = True
    return ctx