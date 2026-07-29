"""Filter tanggal & sinkronisasi angka antar modul dan Laporan Keuangan."""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.constants import MODULE_BY_KEY
from app.services.finance_summary import (
    format_bulan_label,
    parse_range_date,
    resolve_date_range,
)
from app.utils.formatters import format_tanggal_display


def resolve_page_date_range(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    *,
    use_default: bool = False,
) -> Tuple[Optional[date], Optional[date], bool]:
    """Return (start, end, is_filtered). Tanpa parameter = semua periode."""
    if not (dari or "").strip() and not (sampai or "").strip():
        if use_default:
            start, end = resolve_date_range(None, None)
            return start, end, True
        return None, None, False
    start, end = resolve_date_range(dari, sampai)
    return start, end, True


def date_range_filters(dari: Optional[str], sampai: Optional[str]) -> Dict[str, str]:
    start, end, _ = resolve_page_date_range(dari, sampai)
    out: Dict[str, str] = {}
    if start:
        out["dari"] = start.isoformat()
    if end:
        out["sampai"] = end.isoformat()
    return out


def period_display(dari: Optional[str], sampai: Optional[str]) -> str:
    start, end, filtered = resolve_page_date_range(dari, sampai)
    if not filtered:
        return "Semua periode"
    return f"{format_tanggal_display(start.isoformat())} — {format_tanggal_display(end.isoformat())}"


def laporan_query_suffix(dari: Optional[str], sampai: Optional[str]) -> str:
    parts = []
    if (dari or "").strip():
        parts.append(f"dari={(dari or '').strip()}")
    if (sampai or "").strip():
        parts.append(f"sampai={(sampai or '').strip()}")
    return ("?" + "&".join(parts)) if parts else ""


def build_keuangan_link_context(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    *,
    module_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Link & metadata alur Transfer BGN ↔ modul pengeluaran ↔ Laporan Keuangan."""
    qs = laporan_query_suffix(dari, sampai)
    meta = MODULE_BY_KEY.get(module_key or "", {})
    module_href = meta.get("href", "")
    if module_href and qs:
        module_href = f"{module_href}{qs}"
    return {
        "period_label": period_display(dari, sampai),
        "laporan_qs": qs,
        "laporan_href": f"/laporan{qs}",
        "transfer_bgn_href": f"/transfer-bgn{qs}",
        "flow_module_key": module_key,
        "flow_module_label": meta.get("label", ""),
        "flow_module_href": module_href,
        "flow_module_icon": meta.get("icon", "fa-circle"),
    }


def filter_items_by_date_range(
    items: List[Dict[str, Any]],
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
) -> List[Dict[str, Any]]:
    start, end, filtered = resolve_page_date_range(dari, sampai)
    if not filtered:
        return items

    result = []
    for item in items:
        raw = (item.get("tanggal") or item.get("created_at") or "")[:10]
        item_date = parse_range_date(raw)
        if not item_date:
            continue
        if start and item_date < start:
            continue
        if end and item_date > end:
            continue
        result.append(item)
    return result


def summarize_items(items: List[Dict[str, Any]]) -> Dict[str, int]:
    total = sum(int(i.get("jumlah") or 0) for i in items)
    terbayar = sum(
        int(i.get("jumlah") or 0) for i in items if (i.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR")
    )
    diajukan = sum(
        int(i.get("jumlah") or 0) for i in items if (i.get("status") or "").upper() == "DIAJUKAN"
    )
    return {
        "count": len(items),
        "total": total,
        "terbayar_total": terbayar,
        "diajukan_total": diajukan,
        "terbayar_count": sum(1 for i in items if (i.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR")),
        "diajukan_count": sum(1 for i in items if (i.get("status") or "").upper() == "DIAJUKAN"),
    }