"""Tagihan data access."""
import os
from datetime import date
from typing import Any, Dict, List, Optional

from app.config import UPLOAD_DIR
from app.constants import TAGIHAN_CHARGES_AMOUNT
from app.utils.formatters import _parse_id_date
from app.db import get_db

_REKENING_PEMILIK_MAP: Optional[Dict[str, str]] = None

def get_all_tagihan(filters: Dict = None) -> List[Dict]:
    conn = get_db()
    query = "SELECT * FROM tagihan"
    params = []
    where = []
    if filters and filters.get("kategori"):
        where.append("kategori = ?")
        params.append(filters["kategori"])
    else:
        where.append("(kategori IS NULL OR kategori = '' OR kategori = 'tagihan')")

    if filters:
        if filters.get("search"):
            where.append("(pengajuan LIKE ? OR atas_nama LIKE ? OR bank LIKE ? OR pos LIKE ? OR no LIKE ? OR nomor_rekening LIKE ?)")
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s, s, s])
        if filters.get("status"):
            where.append("status = ?")
            params.append(filters["status"])
        if filters.get("rekening"):
            where.append("rekening = ?")
            params.append(filters["rekening"])
        if filters.get("tanggal"):
            where.append("tanggal = ?")
            params.append(filters["tanggal"])
        if filters.get("upload_id"):
            where.append("upload_id = ?")
            params.append(filters["upload_id"])
        if filters.get("dari"):
            where.append("date(COALESCE(tanggal, created_at)) >= date(?)")
            params.append(filters["dari"])
        if filters.get("sampai"):
            where.append("date(COALESCE(tanggal, created_at)) <= date(?)")
            params.append(filters["sampai"])

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY COALESCE(tanggal, '9999-12-31') DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_summary() -> Dict[str, Any]:
    conn = get_db()
    c = conn.cursor()
    exclude_pc = "WHERE (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')"

    # Total keseluruhan (tanpa petty cash)
    c.execute(f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan {exclude_pc}")
    total = c.fetchone()[0] or 0

    from app.constants import PAID_STATUS_SQL
    c.execute(f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan {exclude_pc} AND {PAID_STATUS_SQL}")
    terbayar = c.fetchone()[0] or 0

    c.execute(f"SELECT COALESCE(SUM(jumlah), 0) FROM tagihan {exclude_pc} AND status = 'DIAJUKAN'")
    diajukan = c.fetchone()[0] or 0

    c.execute(f"SELECT COUNT(*) FROM tagihan {exclude_pc}")
    jumlah_item = c.fetchone()[0] or 0

    # By rekening
    c.execute(f"""
        SELECT COALESCE(rekening, 'Belum Ditentukan') as r, COALESCE(SUM(jumlah),0) 
        FROM tagihan {exclude_pc} GROUP BY r ORDER BY 2 DESC
    """)
    by_rekening = [{"rekening": r[0], "total": r[1]} for r in c.fetchall()]

    # By status counts
    c.execute(f"SELECT status, COUNT(*), COALESCE(SUM(jumlah),0) FROM tagihan {exclude_pc} GROUP BY status")
    by_status = [{"status": r[0] or "Belum Ada Status", "count": r[1], "total": r[2]} for r in c.fetchall()]

    conn.close()

    return {
        "total": total,
        "terbayar": terbayar,
        "diajukan": diajukan,
        "jumlah_item": jumlah_item,
        "by_rekening": by_rekening,
        "by_status": by_status,
    }


def calc_tagihan_charges(item: Dict) -> int:
    """Biaya transfer Rp6.500 per baris, kecuali bank Mandiri."""
    bank = (item.get("bank") or "").strip().lower()
    if "mandiri" in bank:
        return 0
    return TAGIHAN_CHARGES_AMOUNT


def _build_rekening_pemilik_map() -> Dict[str, str]:
    """Peta nomor rekening → nama pemilik rekening dari PDF tagihan yang diupload."""
    from app.parsers.upload import parse_faktur_belum_lunas

    mapping: Dict[str, str] = {}
    if not os.path.isdir(UPLOAD_DIR):
        return mapping

    for fname in sorted(os.listdir(UPLOAD_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        if "tagihan" not in fname.lower() and "faktur" not in fname.lower():
            continue
        pdf_path = os.path.join(UPLOAD_DIR, fname)
        try:
            for item in parse_faktur_belum_lunas(pdf_path):
                nomor = str(item.get("nomor_rekening") or "").strip()
                atas = str(item.get("atas_nama") or "").strip()
                if nomor and atas:
                    mapping[nomor] = atas
        except Exception:
            continue
    return mapping


def _get_rekening_pemilik_map() -> Dict[str, str]:
    global _REKENING_PEMILIK_MAP
    if _REKENING_PEMILIK_MAP is None:
        _REKENING_PEMILIK_MAP = _build_rekening_pemilik_map()
    return _REKENING_PEMILIK_MAP


def resolve_tagihan_atas_nama(item: Dict) -> str:
    """Atas nama = nama pemilik rekening (bukan nama pemasok)."""
    nomor = str(item.get("nomor_rekening") or "").strip()
    atas = str(item.get("atas_nama") or "").strip()
    pos = str(item.get("pos") or "").strip()
    if nomor:
        pemilik = _get_rekening_pemilik_map().get(nomor)
        if pemilik:
            return pemilik
    if atas and pos and atas.upper() == pos.upper():
        return ""
    return atas


def sync_tagihan_rekening_pemilik() -> int:
    """Perbaiki atas_nama & pos tagihan dari PDF faktur yang sudah diupload."""
    from app.parsers.upload import parse_faktur_belum_lunas

    if not os.path.isdir(UPLOAD_DIR):
        return 0

    conn = get_db()
    updated = 0
    for fname in sorted(os.listdir(UPLOAD_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        if "tagihan" not in fname.lower() and "faktur" not in fname.lower():
            continue
        pdf_path = os.path.join(UPLOAD_DIR, fname)
        try:
            items = parse_faktur_belum_lunas(pdf_path)
        except Exception:
            continue
        for item in items:
            no = str(item.get("no") or "").strip()
            if not no:
                continue
            atas = str(item.get("atas_nama") or "").strip() or None
            pos = str(item.get("pos") or "").strip() or None
            bank = str(item.get("bank") or "").strip() or None
            nomor = str(item.get("nomor_rekening") or "").strip() or None
            cur = conn.execute(
                "SELECT id, atas_nama, pos FROM tagihan WHERE no = ? AND (kategori IS NULL OR kategori = '' OR kategori = 'tagihan')",
                (no,),
            ).fetchone()
            if not cur:
                continue
            if (cur["atas_nama"] or "") == (atas or "") and (cur["pos"] or "") == (pos or ""):
                continue
            conn.execute(
                "UPDATE tagihan SET atas_nama = ?, pos = ?, bank = COALESCE(?, bank), nomor_rekening = COALESCE(?, nomor_rekening) WHERE id = ?",
                (atas, pos, bank, nomor, cur["id"]),
            )
            updated += 1
    if updated:
        conn.commit()
        global _REKENING_PEMILIK_MAP
        _REKENING_PEMILIK_MAP = None
    conn.close()
    return updated


def format_tagihan_rekening_export(item: Dict) -> str:
    """REKENING untuk export: gabung nomor rekening + atas nama (bukan label kategori)."""
    nomor = str(item.get("nomor_rekening") or "").strip()
    atas = str(item.get("atas_nama") or "").strip()
    bank = str(item.get("bank") or "").strip()
    if nomor and atas:
        prefix = f"{bank} " if bank else ""
        return f"{prefix}{nomor} a.n. {atas}".strip()
    if nomor:
        return f"{bank} {nomor}".strip() if bank else nomor
    if atas:
        return atas
    return str(item.get("rekening") or "").strip()


def enrich_tagihan_item(item: Dict) -> Dict:
    row = dict(item)
    atas_pemilik = resolve_tagihan_atas_nama(row)
    if atas_pemilik:
        row["atas_nama"] = atas_pemilik
    jumlah = row.get("jumlah") or 0
    charges = calc_tagihan_charges(row)
    row["charges"] = charges
    row["total"] = jumlah + charges
    row["rekening_export"] = format_tagihan_rekening_export(row)
    return row
