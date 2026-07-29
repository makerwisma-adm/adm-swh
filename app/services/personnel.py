"""Master data personel: Relawan, PIC, Staff — dikelola di Setup."""
from typing import Any, Dict, List, Optional

from app.db import get_db

PERSONNEL_TYPES = {
    "relawan": {
        "label": "Relawan",
        "label_plural": "Relawan",
        "module_key": "gaji_relawan",
        "module_href": "/gaji-relawan",
        "icon": "fa-users",
    },
    "pic": {
        "label": "PIC",
        "label_plural": "PIC",
        "module_key": "insentif_pic",
        "module_href": "/insentif-pic",
        "icon": "fa-user-tie",
    },
    "staff": {
        "label": "Staff",
        "label_plural": "Staff",
        "module_key": "gaji_staff",
        "module_href": "/gaji-staff",
        "icon": "fa-id-badge",
    },
}

VALID_TIPE = frozenset(PERSONNEL_TYPES.keys())


def _row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    d["aktif"] = bool(d.get("aktif", 1))
    meta = PERSONNEL_TYPES.get(d.get("tipe") or "", {})
    d["tipe_label"] = meta.get("label", d.get("tipe"))
    d["module_href"] = meta.get("module_href", "")
    return d


def list_personnel(
    tipe: Optional[str] = None,
    *,
    aktif_only: bool = False,
) -> List[Dict[str, Any]]:
    conn = get_db()
    query = "SELECT * FROM personnel"
    params: List[Any] = []
    where = []
    if tipe and tipe in VALID_TIPE:
        where.append("tipe = ?")
        params.append(tipe)
    if aktif_only:
        where.append("aktif = 1")
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY tipe ASC, nama COLLATE NOCASE ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def list_personnel_grouped(*, aktif_only: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {k: [] for k in VALID_TIPE}
    for row in list_personnel(aktif_only=aktif_only):
        t = row.get("tipe")
        if t in grouped:
            grouped[t].append(row)
    return grouped


def get_personnel(personnel_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("SELECT * FROM personnel WHERE id = ?", (personnel_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def create_personnel(
    *,
    tipe: str,
    nama: str,
    no: str = "",
    atas_nama: str = "",
    nomor_rekening: str = "",
    bank: str = "",
    pos: str = "",
    aktif: bool = True,
) -> Dict[str, Any]:
    tipe = (tipe or "").strip().lower()
    nama = (nama or "").strip()
    if tipe not in VALID_TIPE:
        raise ValueError("Tipe personel tidak valid")
    if not nama:
        raise ValueError("Nama wajib diisi")
    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO personnel (tipe, nama, no, atas_nama, nomor_rekening, bank, pos, aktif)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tipe,
            nama,
            (no or "").strip() or None,
            (atas_nama or "").strip() or None,
            (nomor_rekening or "").strip() or None,
            (bank or "").strip() or None,
            (pos or "").strip() or None,
            1 if aktif else 0,
        ),
    )
    pid = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM personnel WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def update_personnel(
    personnel_id: int,
    *,
    tipe: Optional[str] = None,
    nama: Optional[str] = None,
    no: Optional[str] = None,
    atas_nama: Optional[str] = None,
    nomor_rekening: Optional[str] = None,
    bank: Optional[str] = None,
    pos: Optional[str] = None,
    aktif: Optional[bool] = None,
) -> Dict[str, Any]:
    existing = get_personnel(personnel_id)
    if not existing:
        raise ValueError("Data personel tidak ditemukan")
    new_tipe = (tipe or existing["tipe"]).strip().lower()
    new_nama = (nama if nama is not None else existing["nama"]).strip()
    if new_tipe not in VALID_TIPE:
        raise ValueError("Tipe personel tidak valid")
    if not new_nama:
        raise ValueError("Nama wajib diisi")
    conn = get_db()
    conn.execute(
        """
        UPDATE personnel SET
            tipe = ?, nama = ?, no = ?, atas_nama = ?, nomor_rekening = ?,
            bank = ?, pos = ?, aktif = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            new_tipe,
            new_nama,
            (no if no is not None else existing.get("no") or "").strip() or None,
            (atas_nama if atas_nama is not None else existing.get("atas_nama") or "").strip() or None,
            (nomor_rekening if nomor_rekening is not None else existing.get("nomor_rekening") or "").strip() or None,
            (bank if bank is not None else existing.get("bank") or "").strip() or None,
            (pos if pos is not None else existing.get("pos") or "").strip() or None,
            1 if (aktif if aktif is not None else existing.get("aktif")) else 0,
            personnel_id,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM personnel WHERE id = ?", (personnel_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def delete_personnel(personnel_id: int) -> None:
    conn = get_db()
    row = conn.execute("SELECT id FROM personnel WHERE id = ?", (personnel_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("Data personel tidak ditemukan")
    conn.execute("DELETE FROM personnel WHERE id = ?", (personnel_id,))
    conn.commit()
    conn.close()