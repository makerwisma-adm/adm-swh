"""Filter data tagihan untuk akun role mitra."""
import re
from typing import Any, Dict, List, Optional

from app.constants import ROLE_MITRA


def normalize_mitra_key(value: Optional[str]) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip().lower())
    return text


def get_mitra_nama(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return ""
    return (user.get("mitra_nama") or user.get("full_name") or "").strip()


def item_matches_mitra(item: Dict[str, Any], mitra_nama: str) -> bool:
    key = normalize_mitra_key(mitra_nama)
    if not key:
        return False
    for field in ("atas_nama", "pengajuan", "rekening", "nomor_rekening"):
        val = normalize_mitra_key(item.get(field))
        if not val:
            continue
        if key in val or val in key:
            return True
    return False


def filter_items_for_mitra(items: List[Dict[str, Any]], mitra_nama: str) -> List[Dict[str, Any]]:
    if not mitra_nama:
        return []
    return [item for item in items if item_matches_mitra(item, mitra_nama)]


def is_mitra_role(user: Optional[Dict[str, Any]]) -> bool:
    return (user.get("role") or "").lower() == ROLE_MITRA if user else False