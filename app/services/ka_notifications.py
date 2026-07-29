"""Notifikasi pembayaran lunas untuk KA SPPG."""
from typing import Any, Dict, List, Optional

from app.constants import KATEGORI_LABELS, ROLE_KA_SPPG
from app.db import get_db
from app.utils.formatters import format_rupiah


def _ka_user_ids(conn, approved_by: Optional[int]) -> List[int]:
    if approved_by:
        row = conn.execute("SELECT id, role FROM users WHERE id = ?", (approved_by,)).fetchone()
        if row and (row["role"] or "").lower() == ROLE_KA_SPPG:
            return [int(row["id"])]
    rows = conn.execute(
        "SELECT id FROM users WHERE role = ?",
        (ROLE_KA_SPPG,),
    ).fetchall()
    return [int(r["id"]) for r in rows]


def notify_ka_lunas(conn, tagihan_id: int, maker_user: Optional[Dict[str, Any]]) -> int:
    row = conn.execute(
        """
        SELECT id, pengajuan, jumlah, kategori, atas_nama, approved_by, approved_at
        FROM tagihan WHERE id = ?
        """,
        (tagihan_id,),
    ).fetchone()
    if not row:
        return 0

    item = dict(row)
    targets = _ka_user_ids(conn, item.get("approved_by"))
    if not targets:
        return 0

    kat = item.get("kategori") or "tagihan"
    mod_label = KATEGORI_LABELS.get(kat, kat)
    maker_name = (maker_user or {}).get("full_name") or (maker_user or {}).get("username") or "Maker"
    penerima = (item.get("atas_nama") or item.get("pengajuan") or "—").strip()
    jumlah = format_rupiah(int(item.get("jumlah") or 0))
    title = f"Pembayaran LUNAS — {mod_label}"
    message = (
        f"Pengajuan \"{item.get('pengajuan') or '—'}\" ({penerima}) sebesar {jumlah} "
        f"telah dibayarkan via VA oleh {maker_name}."
    )

    created = 0
    for uid in targets:
        conn.execute(
            """
            INSERT INTO ka_notifications (user_id, tagihan_id, title, message)
            VALUES (?, ?, ?, ?)
            """,
            (uid, tagihan_id, title, message),
        )
        created += 1
    return created


def notify_ka_lunas_bulk(conn, tagihan_ids: List[int], maker_user: Optional[Dict[str, Any]]) -> int:
    total = 0
    for tid in tagihan_ids:
        total += notify_ka_lunas(conn, tid, maker_user)
    return total


def count_unread_ka_notifications(user_id: int) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM ka_notifications WHERE user_id = ? AND read_at IS NULL",
        (user_id,),
    ).fetchone()
    conn.close()
    return int(row["cnt"] or 0) if row else 0


def get_ka_notifications(user_id: int, *, limit: int = 30, unread_only: bool = False) -> List[Dict[str, Any]]:
    conn = get_db()
    clauses = ["n.user_id = ?"]
    params: List[Any] = [user_id]
    if unread_only:
        clauses.append("n.read_at IS NULL")

    rows = conn.execute(
        f"""
        SELECT n.id, n.tagihan_id, n.title, n.message, n.read_at, n.created_at,
               t.pengajuan, t.jumlah, t.kategori, t.status, t.paid_at,
               um.username AS paid_by_name
        FROM ka_notifications n
        JOIN tagihan t ON t.id = n.tagihan_id
        LEFT JOIN users um ON um.id = t.paid_by
        WHERE {" AND ".join(clauses)}
        ORDER BY n.created_at DESC, n.id DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        item = dict(r)
        kat = item.get("kategori") or "tagihan"
        item["kategori_label"] = KATEGORI_LABELS.get(kat, kat)
        item["is_unread"] = not item.get("read_at")
        result.append(item)
    return result


def mark_ka_notifications_read(user_id: int, notification_ids: Optional[List[int]] = None) -> int:
    conn = get_db()
    if notification_ids:
        placeholders = ",".join("?" * len(notification_ids))
        cur = conn.execute(
            f"""
            UPDATE ka_notifications
            SET read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND id IN ({placeholders}) AND read_at IS NULL
            """,
            [user_id, *notification_ids],
        )
    else:
        cur = conn.execute(
            """
            UPDATE ka_notifications
            SET read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND read_at IS NULL
            """,
            (user_id,),
        )
    updated = cur.rowcount
    conn.commit()
    conn.close()
    return updated