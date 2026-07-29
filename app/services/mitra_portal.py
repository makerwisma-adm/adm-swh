"""Portal ringkasan untuk akun mitra."""
from typing import Any, Dict, List

from app.services.mitra_access import filter_items_for_mitra, get_mitra_nama
from app.services.transfer_reports import get_insentif_mitra, get_pengeluaran_mitra


def build_mitra_portal_context(user: Dict[str, Any]) -> Dict[str, Any]:
    mitra_nama = get_mitra_nama(user)
    insentif = filter_items_for_mitra(get_insentif_mitra(), mitra_nama)
    pengeluaran = filter_items_for_mitra(get_pengeluaran_mitra(), mitra_nama)

    total_insentif = sum(int(i.get("jumlah") or 0) for i in insentif)
    total_pengeluaran = sum(int(i.get("jumlah") or 0) for i in pengeluaran)
    saldo_bersih = total_insentif - total_pengeluaran
    terbayar_insentif = sum(
        int(i.get("jumlah") or 0) for i in insentif if (i.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR")
    )
    terbayar_pengeluaran = sum(
        int(i.get("jumlah") or 0) for i in pengeluaran if (i.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR")
    )

    recent_insentif = sorted(
        insentif,
        key=lambda x: (x.get("tanggal") or "", x.get("id") or 0),
        reverse=True,
    )[:5]
    recent_pengeluaran = sorted(
        pengeluaran,
        key=lambda x: (x.get("tanggal") or "", x.get("id") or 0),
        reverse=True,
    )[:5]

    return {
        "mitra_nama": mitra_nama,
        "insentif_items": insentif,
        "pengeluaran_items": pengeluaran,
        "total_insentif": total_insentif,
        "total_pengeluaran": total_pengeluaran,
        "saldo_bersih": saldo_bersih,
        "terbayar_insentif": terbayar_insentif,
        "terbayar_pengeluaran": terbayar_pengeluaran,
        "count_insentif": len(insentif),
        "count_pengeluaran": len(pengeluaran),
        "recent_insentif": recent_insentif,
        "recent_pengeluaran": recent_pengeluaran,
    }