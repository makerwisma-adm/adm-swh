"""CRUD transfer masuk dari BGN."""
from typing import Any, Dict, List, Optional

from app.services.finance_summary import get_bgn_transfers
from app.db import get_db


def create_bgn_transfer(
    tanggal: str,
    keterangan: str,
    jumlah: int,
    no_referensi: str = "",
    periode: str = "",
    created_by: Optional[int] = None,
) -> int:
    conn = get_db()
    conn.execute(
        """
        INSERT INTO bgn_transfers (tanggal, keterangan, jumlah, no_referensi, periode, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tanggal.strip(),
            keterangan.strip(),
            jumlah,
            no_referensi.strip() or None,
            periode.strip() or None,
            created_by,
        ),
    )
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return row_id


def update_bgn_transfer(
    item_id: int,
    tanggal: str,
    keterangan: str,
    jumlah: int,
    no_referensi: str = "",
    periode: str = "",
) -> None:
    conn = get_db()
    conn.execute(
        """
        UPDATE bgn_transfers SET
            tanggal = ?, keterangan = ?, jumlah = ?,
            no_referensi = ?, periode = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            tanggal.strip(),
            keterangan.strip(),
            jumlah,
            no_referensi.strip() or None,
            periode.strip() or None,
            item_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_bgn_transfer(item_id: int) -> None:
    conn = get_db()
    conn.execute("DELETE FROM bgn_transfers WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def bulk_delete_bgn_transfers(ids: List[int]) -> int:
    if not ids:
        return 0
    conn = get_db()
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM bgn_transfers WHERE id IN ({placeholders})", ids)
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return deleted