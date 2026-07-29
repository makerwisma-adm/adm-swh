"""Workflow persetujuan KA SPPG: DIAJUKAN → DISETUJUI → LUNAS (atau DITOLAK)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.constants import (
    APPROVAL_KATEGORI,
    KATEGORI_LABELS,
    ROLE_ADMIN,
    ROLE_KA_SPPG,
    ROLE_MAKER,
    ROLE_MEMBER,
    STATUS_DIAJUKAN,
    STATUS_DIBAYARKAN,
    STATUS_DISETUJUI,
    STATUS_DITOLAK,
    STATUS_LUNAS,
)
from app.db import get_db


def normalize_status(status: Optional[str]) -> str:
    s = (status or "").strip().upper()
    if s in ("TERBAYAR", "DIBAYARKAN"):
        return STATUS_LUNAS
    return s


def is_dibayarkan(status: Optional[str]) -> bool:
    return normalize_status(status) == STATUS_LUNAS


def is_lunas(status: Optional[str]) -> bool:
    return is_dibayarkan(status)


def requires_ka_approval(kategori: Optional[str]) -> bool:
    return (kategori or "tagihan") in APPROVAL_KATEGORI


def _user_role(user: Optional[Dict]) -> str:
    if not user:
        return ""
    return (user.get("role") or ROLE_MEMBER).lower()


def is_ka_sppg(user: Optional[Dict]) -> bool:
    return _user_role(user) == ROLE_KA_SPPG


def is_maker(user: Optional[Dict]) -> bool:
    return _user_role(user) == ROLE_MAKER


def can_approve(user: Optional[Dict]) -> bool:
    role = _user_role(user)
    return role in (ROLE_KA_SPPG, ROLE_ADMIN)


def can_mark_paid(user: Optional[Dict]) -> bool:
    role = _user_role(user)
    return role in (ROLE_ADMIN, ROLE_MAKER)


def can_submit_status(user: Optional[Dict]) -> bool:
    role = _user_role(user)
    return role in (ROLE_ADMIN, ROLE_MEMBER)


def can_user_set_status(
    user: Optional[Dict],
    current_status: Optional[str],
    new_status: Optional[str],
    *,
    kategori: Optional[str] = None,
) -> bool:
    current = normalize_status(current_status)
    new = normalize_status(new_status)
    if not new:
        return _user_role(user) == ROLE_ADMIN

    role = _user_role(user)
    needs_approval = requires_ka_approval(kategori)

    if role == ROLE_ADMIN:
        return True

    if role == ROLE_KA_SPPG:
        if not needs_approval:
            return False
        if new == STATUS_DISETUJUI and current == STATUS_DIAJUKAN:
            return True
        if new == STATUS_DITOLAK and current == STATUS_DIAJUKAN:
            return True
        return False

    if role == ROLE_MAKER:
        if new == STATUS_LUNAS:
            if not needs_approval:
                return False
            return current == STATUS_DISETUJUI
        return False

    if role == ROLE_MEMBER:
        if new == STATUS_DIAJUKAN:
            return current in ("", STATUS_DITOLAK)
        if new in (STATUS_LUNAS, STATUS_DIBAYARKAN):
            return not needs_approval
        return False

    return False


def validate_status_change(
    user: Optional[Dict],
    current_status: Optional[str],
    new_status: Optional[str],
    *,
    kategori: Optional[str] = None,
) -> None:
    if not can_user_set_status(user, current_status, new_status, kategori=kategori):
        current = normalize_status(current_status) or "—"
        new = normalize_status(new_status)
        if new == STATUS_DISETUJUI:
            raise ValueError("Hanya KA SPPG yang dapat menyetujui pengajuan DIAJUKAN.")
        if new == STATUS_DITOLAK:
            raise ValueError("Hanya KA SPPG yang dapat menolak pengajuan DIAJUKAN.")
        if new == STATUS_LUNAS and requires_ka_approval(kategori):
            raise ValueError(
                f"Pembayaran VA hanya dapat diproses Maker setelah disetujui KA SPPG (saat ini: {current})."
            )
        if new == STATUS_DIAJUKAN and current == STATUS_DITOLAK:
            raise ValueError("Pengajuan ditolak — perbaiki data lalu ajukan ulang sebagai DIAJUKAN.")
        raise ValueError(f"Perubahan status {current} → {new} tidak diizinkan untuk akun Anda.")


def _clear_approval_fields() -> str:
    return "approved_by = NULL, approved_at = NULL"


def _clear_rejection_fields() -> str:
    return "rejected_by = NULL, rejected_at = NULL, rejection_note = NULL"


def _approval_set_clause(new_status: str, user: Optional[Dict], *, rejection_note: str = "") -> tuple:
    new_status = normalize_status(new_status)
    ts = datetime.now().isoformat(timespec="seconds")

    if new_status == STATUS_DISETUJUI and user:
        return (
            f"status = ?, approved_by = ?, approved_at = ?, {_clear_rejection_fields()}, updated_at = CURRENT_TIMESTAMP",
            [new_status, user.get("id"), ts],
        )
    if new_status == STATUS_DITOLAK and user:
        note = (rejection_note or "").strip()
        if not note:
            raise ValueError("Alasan penolakan wajib diisi.")
        return (
            f"status = ?, rejected_by = ?, rejected_at = ?, rejection_note = ?, {_clear_approval_fields()}, updated_at = CURRENT_TIMESTAMP",
            [new_status, user.get("id"), ts, note],
        )
    if new_status == STATUS_DIAJUKAN:
        return (
            f"status = ?, {_clear_approval_fields()}, {_clear_rejection_fields()}, paid_by = NULL, paid_at = NULL, updated_at = CURRENT_TIMESTAMP",
            [new_status],
        )
    if new_status == STATUS_LUNAS and user:
        return (
            "status = ?, paid_by = ?, paid_at = ?, updated_at = CURRENT_TIMESTAMP",
            [STATUS_LUNAS, user.get("id"), ts],
        )
    return (
        "status = ?, updated_at = CURRENT_TIMESTAMP",
        [new_status],
    )


def bulk_set_tagihan_status(
    conn,
    ids: List[int],
    new_status: str,
    user: Optional[Dict],
    *,
    kategori: Optional[str] = None,
    rejection_note: str = "",
) -> int:
    if not ids:
        return 0

    placeholders = ",".join("?" * len(ids))
    params: List[Any] = list(ids)
    where = f"id IN ({placeholders})"
    if kategori:
        where += " AND kategori = ?"
        params.append(kategori)

    rows = conn.execute(
        f"SELECT id, status, kategori FROM tagihan WHERE {where}",
        params,
    ).fetchall()
    if not rows:
        return 0

    from app.services.ka_notifications import notify_ka_lunas_bulk

    updated = 0
    paid_ids: List[int] = []
    target_status = normalize_status(new_status)
    for row in rows:
        kat = row["kategori"] or "tagihan"
        try:
            validate_status_change(user, row["status"], new_status, kategori=kat)
            set_sql, set_params = _approval_set_clause(
                new_status, user, rejection_note=rejection_note if normalize_status(new_status) == STATUS_DITOLAK else ""
            )
        except ValueError:
            continue
        conn.execute(
            f"UPDATE tagihan SET {set_sql} WHERE id = ?",
            set_params + [row["id"]],
        )
        updated += 1
        if target_status == STATUS_LUNAS:
            paid_ids.append(int(row["id"]))
    if paid_ids:
        notify_ka_lunas_bulk(conn, paid_ids, user)
    return updated


def bulk_reject_tagihan(
    conn,
    ids: List[int],
    user: Optional[Dict],
    note: str,
    *,
    kategori: Optional[str] = None,
) -> int:
    return bulk_set_tagihan_status(
        conn, ids, STATUS_DITOLAK, user, kategori=kategori, rejection_note=note
    )


def get_tagihan_by_status(
    status: str,
    *,
    kategori: Optional[str] = None,
    search: str = "",
) -> List[Dict[str, Any]]:
    status = normalize_status(status)
    conn = get_db()
    if status == STATUS_LUNAS:
        status_clause = "UPPER(COALESCE(status, '')) IN ('LUNAS', 'DIBAYARKAN', 'TERBAYAR')"
        clauses = [status_clause, "kategori IN ({})".format(",".join("?" * len(APPROVAL_KATEGORI)))]
        params: List[Any] = list(sorted(APPROVAL_KATEGORI))
        if kategori and kategori in APPROVAL_KATEGORI:
            clauses = [status_clause, "kategori = ?"]
            params = [kategori]
    else:
        clauses = ["status = ?", "kategori IN ({})".format(",".join("?" * len(APPROVAL_KATEGORI)))]
        params = [status, *sorted(APPROVAL_KATEGORI)]
        if kategori and kategori in APPROVAL_KATEGORI:
            clauses = ["status = ?", "kategori = ?"]
            params = [status, kategori]

    if search.strip():
        clauses.append("(pengajuan LIKE ? OR atas_nama LIKE ? OR no LIKE ?)")
        q = f"%{search.strip()}%"
        params.extend([q, q, q])

    sql = f"""
        SELECT t.id, t.no, t.pengajuan, t.jumlah, t.status, t.kategori, t.tanggal, t.atas_nama,
               t.nomor_rekening, t.bank, t.rekening, t.created_at,
               t.approved_by, t.approved_at, t.rejected_by, t.rejected_at, t.rejection_note,
               t.paid_by, t.paid_at,
               ua.username AS approved_by_name, ur.username AS rejected_by_name,
               up.username AS paid_by_name
        FROM tagihan t
        LEFT JOIN users ua ON ua.id = t.approved_by
        LEFT JOIN users ur ON ur.id = t.rejected_by
        LEFT JOIN users up ON up.id = t.paid_by
        WHERE {" AND ".join(clauses)}
        ORDER BY t.tanggal DESC, t.id DESC
    """
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        item = dict(r)
        kat = item.get("kategori") or "tagihan"
        item["kategori_label"] = KATEGORI_LABELS.get(kat, kat)
        item["module_href"] = _kategori_href(kat)
        item["va_label"] = _va_label(item)
        result.append(item)
    return result


def get_pending_approvals(
    *,
    kategori: Optional[str] = None,
    search: str = "",
) -> List[Dict[str, Any]]:
    return get_tagihan_by_status(STATUS_DIAJUKAN, kategori=kategori, search=search)


def _group_tagihan_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_kategori: Dict[str, List[Dict]] = {}
    for item in items:
        kat = item.get("kategori") or "tagihan"
        by_kategori.setdefault(kat, []).append(item)

    groups = []
    for kat in sorted(by_kategori.keys(), key=lambda k: KATEGORI_LABELS.get(k, k)):
        group_items = by_kategori[kat]
        groups.append({
            "kategori": kat,
            "label": KATEGORI_LABELS.get(kat, kat),
            "href": _kategori_href(kat),
            "count": len(group_items),
            "total": sum(int(i.get("jumlah") or 0) for i in group_items),
            "entries": group_items,
        })
    return groups


def _tab_counts() -> Dict[str, int]:
    conn = get_db()
    placeholders = ",".join("?" * len(APPROVAL_KATEGORI))
    rows = conn.execute(
        f"""
        SELECT
            CASE
                WHEN UPPER(COALESCE(status, '')) IN ('LUNAS', 'DIBAYARKAN', 'TERBAYAR') THEN ?
                ELSE UPPER(COALESCE(status, ''))
            END AS status_norm,
            COUNT(*) AS cnt
        FROM tagihan
        WHERE kategori IN ({placeholders})
          AND UPPER(COALESCE(status, '')) IN (?, ?, ?, ?, 'DIBAYARKAN', 'TERBAYAR')
        GROUP BY status_norm
        """,
        [
            STATUS_LUNAS,
            *sorted(APPROVAL_KATEGORI),
            STATUS_DIAJUKAN,
            STATUS_DISETUJUI,
            STATUS_DITOLAK,
            STATUS_LUNAS,
        ],
    ).fetchall()
    conn.close()
    counts = {STATUS_DIAJUKAN: 0, STATUS_DISETUJUI: 0, STATUS_DITOLAK: 0, STATUS_LUNAS: 0}
    for row in rows:
        key = normalize_status(row["status_norm"])
        if key in counts:
            counts[key] = int(row["cnt"] or 0)
    return {
        "diajukan": counts[STATUS_DIAJUKAN],
        "disetujui": counts[STATUS_DISETUJUI],
        "ditolak": counts[STATUS_DITOLAK],
        "lunas": counts[STATUS_LUNAS],
    }


KA_TABS = {
    "diajukan": {"status": STATUS_DIAJUKAN, "label": "Perlu Disetujui", "empty_title": "Tidak ada pengajuan menunggu persetujuan", "empty_desc": "Semua pengajuan sudah diproses atau belum diajukan oleh akuntan."},
    "disetujui": {"status": STATUS_DISETUJUI, "label": "Sudah Disetujui", "empty_title": "Belum ada pengajuan disetujui", "empty_desc": "Pengajuan yang disetujui KA akan tampil di sini menunggu pembayaran akuntan."},
    "ditolak": {"status": STATUS_DITOLAK, "label": "Ditolak", "empty_title": "Tidak ada pengajuan ditolak", "empty_desc": "Pengajuan yang ditolak KA beserta alasannya akan tampil di sini."},
    "lunas": {"status": STATUS_LUNAS, "label": "Sudah Lunas", "empty_title": "Belum ada pembayaran lunas", "empty_desc": "Pengajuan yang sudah dibayarkan Maker via VA akan tampil di sini."},
}


def _va_label(item: Dict[str, Any]) -> str:
    bank = (item.get("bank") or "").strip()
    nomor = (item.get("nomor_rekening") or "").strip()
    atas = (item.get("atas_nama") or "").strip()
    rekening = (item.get("rekening") or "").strip()
    parts = [p for p in (bank, nomor, atas) if p]
    if parts:
        return " · ".join(parts)
    return rekening or "—"


def _kategori_href(kategori: str) -> str:
    from app.constants import MODULE_BY_KEY

    mod = MODULE_BY_KEY.get(kategori)
    if mod:
        return mod.get("href", "/dashboard-ka")
    return "/dashboard-ka"


def get_ka_dashboard_context(
    search: str = "",
    kategori: str = "",
    tab: str = "diajukan",
    *,
    ka_user_id: Optional[int] = None,
    dari: str = "",
    sampai: str = "",
) -> Dict[str, Any]:
    tab = tab if tab in KA_TABS else "diajukan"
    tab_meta = KA_TABS[tab]
    if tab == "lunas" and ka_user_id:
        from app.services.lunas_laporan import get_lunas_laporan_items

        items = get_lunas_laporan_items(
            dari=dari or None,
            sampai=sampai or None,
            kategori=kategori or None,
            search=search,
            approved_by=ka_user_id,
        )
    else:
        items = get_tagihan_by_status(
            tab_meta["status"],
            kategori=kategori or None,
            search=search,
        )
    groups = _group_tagihan_items(items)
    tab_counts = _tab_counts()

    notifications: List[Dict[str, Any]] = []
    unread_notification_count = 0
    if ka_user_id:
        from app.services.ka_notifications import count_unread_ka_notifications, get_ka_notifications

        unread_notification_count = count_unread_ka_notifications(ka_user_id)
        notifications = get_ka_notifications(ka_user_id, limit=15)

    return {
        "tab": tab,
        "tab_meta": tab_meta,
        "tab_counts": tab_counts,
        "ka_notifications": notifications,
        "ka_unread_notification_count": unread_notification_count,
        "items": items,
        "groups": groups,
        "item_count": len(items),
        "item_total": sum(int(i.get("jumlah") or 0) for i in items),
        "pending_items": items,
        "pending_groups": groups,
        "pending_count": tab_counts["diajukan"],
        "pending_total": sum(int(i.get("jumlah") or 0) for i in items) if tab == "diajukan" else 0,
        "kategori_options": [
            {"key": k, "label": KATEGORI_LABELS.get(k, k)}
            for k in sorted(APPROVAL_KATEGORI, key=lambda x: KATEGORI_LABELS.get(x, x))
        ],
        "filters": {"search": search, "kategori": kategori, "tab": tab, "dari": dari, "sampai": sampai},
    }


def get_bayar_dashboard_context(search: str = "", kategori: str = "") -> Dict[str, Any]:
    items = get_tagihan_by_status(STATUS_DISETUJUI, kategori=kategori or None, search=search)
    groups = _group_tagihan_items(items)
    tab_counts = _tab_counts()

    return {
        "items": items,
        "groups": groups,
        "item_count": len(items),
        "item_total": sum(int(i.get("jumlah") or 0) for i in items),
        "disetujui_count": tab_counts["disetujui"],
        "kategori_options": [
            {"key": k, "label": KATEGORI_LABELS.get(k, k)}
            for k in sorted(APPROVAL_KATEGORI, key=lambda x: KATEGORI_LABELS.get(x, x))
        ],
        "filters": {"search": search, "kategori": kategori},
    }


def resolve_status_for_save(
    user: Optional[Dict],
    current_status: Optional[str],
    requested_status: Optional[str],
    *,
    kategori: Optional[str] = None,
    is_new: bool = False,
) -> str:
    if is_new:
        new = normalize_status(requested_status) or STATUS_DIAJUKAN
        validate_status_change(user, "", new, kategori=kategori)
        return new
    new = normalize_status(requested_status) or normalize_status(current_status)
    validate_status_change(user, current_status, new, kategori=kategori)
    return new


def status_options_for_user(user: Optional[Dict], current: Optional[str] = None) -> List[str]:
    """Opsi status yang boleh dipilih di form edit."""
    current = normalize_status(current)
    role = _user_role(user)
    if role == ROLE_ADMIN:
        return [STATUS_DIAJUKAN, STATUS_DISETUJUI, STATUS_LUNAS, STATUS_DITOLAK]
    if role == ROLE_MAKER:
        if current == STATUS_DISETUJUI:
            return [STATUS_DISETUJUI, STATUS_LUNAS]
        return []
    if role == ROLE_MEMBER:
        opts = [STATUS_DIAJUKAN]
        if current == STATUS_LUNAS:
            opts.append(STATUS_LUNAS)
        elif current == STATUS_DITOLAK:
            opts = [STATUS_DIAJUKAN]
        return opts
    return []