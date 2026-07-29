"""Laporan & export pengajuan status LUNAS."""
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.constants import APPROVAL_KATEGORI, KATEGORI_LABELS, ROLE_ADMIN, ROLE_KA_SPPG, ROLE_MAKER, STATUS_LUNAS
from app.services.approval import get_tagihan_by_status
from app.services.user_access import user_has_module
from app.utils.formatters import format_tanggal_display


def can_export_lunas(user: Optional[Dict[str, Any]]) -> bool:
    if not user:
        return False
    role = (user.get("role") or "").lower()
    if role == ROLE_ADMIN:
        return True
    if role == ROLE_KA_SPPG or user_has_module(user, "dashboard_ka"):
        return True
    if role == ROLE_MAKER or user_has_module(user, "dashboard_bayar"):
        return True
    return False


def resolve_lunas_scope(user: Optional[Dict[str, Any]], scope: str = "") -> str:
    role = (user.get("role") or "").lower() if user else ""
    scope = (scope or "").lower()
    if scope in ("ka", "maker", "all"):
        if scope == "ka" and role not in (ROLE_ADMIN, ROLE_KA_SPPG) and not user_has_module(user, "dashboard_ka"):
            return "maker" if role == ROLE_MAKER else "all"
        if scope == "maker" and role not in (ROLE_ADMIN, ROLE_MAKER) and not user_has_module(user, "dashboard_bayar"):
            return "ka" if role == ROLE_KA_SPPG else "all"
        return scope
    if role == ROLE_KA_SPPG:
        return "ka"
    if role == ROLE_MAKER:
        return "maker"
    return "all"


def get_lunas_laporan_items(
    *,
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    kategori: Optional[str] = None,
    search: str = "",
    approved_by: Optional[int] = None,
    paid_by: Optional[int] = None,
) -> List[Dict[str, Any]]:
    items = get_tagihan_by_status(
        STATUS_LUNAS,
        kategori=kategori or None,
        search=search,
    )

    def _date_key(val: Optional[str]) -> str:
        if not val:
            return ""
        return str(val)[:10]

    d_from = (dari or "").strip()[:10]
    d_to = (sampai or "").strip()[:10]

    result = []
    for item in items:
        if approved_by and int(item.get("approved_by") or 0) != int(approved_by):
            continue
        if paid_by and int(item.get("paid_by") or 0) != int(paid_by):
            continue
        paid_date = _date_key(item.get("paid_at")) or _date_key(item.get("tanggal"))
        if d_from and paid_date and paid_date < d_from:
            continue
        if d_to and paid_date and paid_date > d_to:
            continue
        result.append(item)
    return result


def build_lunas_export_href(
    *,
    scope: str = "",
    kategori: str = "",
    search: str = "",
    dari: str = "",
    sampai: str = "",
) -> str:
    params = {k: v for k, v in {
        "scope": scope,
        "kategori": kategori,
        "search": search,
        "dari": dari,
        "sampai": sampai,
    }.items() if v}
    qs = f"?{urlencode(params)}" if params else ""
    return f"/export/laporan/lunas/csv{qs}"


def get_lunas_laporan_context(
    *,
    scope: str = "",
    kategori: str = "",
    search: str = "",
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    approved_by = None
    paid_by = None
    scope = resolve_lunas_scope(user, scope)

    if scope == "ka":
        approved_by = user.get("id") if user else None
    elif scope == "maker":
        paid_by = user.get("id") if user else None

    items = get_lunas_laporan_items(
        dari=dari,
        sampai=sampai,
        kategori=kategori or None,
        search=search,
        approved_by=approved_by,
        paid_by=paid_by,
    )
    total = sum(int(i.get("jumlah") or 0) for i in items)

    scope_label = "Semua"
    if approved_by:
        scope_label = "Disetujui saya (KA SPPG)"
    elif paid_by:
        scope_label = "Diproses saya (Maker)"

    today = date.today()
    return {
        "items": items,
        "item_count": len(items),
        "item_total": total,
        "scope": scope,
        "scope_label": scope_label,
        "dari": (dari or "").strip()[:10],
        "sampai": (sampai or "").strip()[:10],
        "dari_display": format_tanggal_display(dari) if dari else "Awal",
        "sampai_display": format_tanggal_display(sampai) if sampai else "Akhir",
        "kategori": kategori,
        "kategori_label": KATEGORI_LABELS.get(kategori, "Semua modul") if kategori else "Semua modul",
        "search": search,
        "report_title": "Laporan Pengajuan LUNAS",
        "report_subtitle": "Pembayaran VA selesai — sudah mengurangi saldo kas BGN",
        "generated_at_display": format_tanggal_display(today.isoformat()),
        "export_csv_href": build_lunas_export_href(
            scope=scope,
            kategori=kategori,
            search=search,
            dari=dari or "",
            sampai=sampai or "",
        ),
        "kategori_options": [
            {"key": k, "label": KATEGORI_LABELS.get(k, k)}
            for k in sorted(APPROVAL_KATEGORI, key=lambda x: KATEGORI_LABELS.get(x, x))
        ],
    }