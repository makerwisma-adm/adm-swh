"""Sewa kendaraan — pengeluaran operasional dari dana Transfer BGN."""
from typing import Any, Dict, List

from app.services.tagihan import get_all_tagihan

KATEGORI = "sewa_kendaraan"


def _sort_key(row: Dict[str, Any]) -> tuple:
    tanggal = row.get("tanggal") or ""
    no = row.get("no") or ""
    return (tanggal, no, row.get("id") or 0)


def get_sewa_kendaraan(filters: Dict = None) -> List[Dict]:
    f = dict(filters or {})
    f["kategori"] = KATEGORI
    rows = get_all_tagihan(f)
    return sorted(rows, key=_sort_key, reverse=True)