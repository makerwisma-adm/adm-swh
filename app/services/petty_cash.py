"""Petty cash data access."""
from typing import Any, Dict, List

from app.utils.files import _delete_nota_file, _delete_upload_file
from app.db import get_db

def get_petty_cash_laporans() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, u.record_count, u.created_at as upload_at
        FROM petty_cash_laporan p
        LEFT JOIN uploads u ON u.id = p.upload_id
        ORDER BY p.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_petty_cash_items(upload_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM petty_cash_items
        WHERE upload_id = ?
        ORDER BY id ASC
    """, (upload_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def filter_petty_cash_items(
    items: List[Dict[str, Any]],
    search: str = "",
    tanggal: str = "",
    jenis: str = "",
) -> List[Dict[str, Any]]:
    """Filter petty cash rows by search, date, and transaction type."""
    result = items
    jenis = (jenis or "").strip().lower()
    if jenis == "pemasukan":
        result = [i for i in result if (i.get("debit") or 0) > 0]
    elif jenis == "pengeluaran":
        result = [
            i for i in result
            if (i.get("kredit") or 0) > 0
            or ((i.get("debit") or 0) == 0 and (i.get("jumlah") or 0) > 0)
        ]
    if tanggal:
        result = [i for i in result if (i.get("tanggal") or "") == tanggal]
    if search:
        s = search.strip().lower()
        result = [
            i for i in result
            if s in (i.get("pengajuan") or "").lower()
            or s in (i.get("tipe_transaksi") or "").lower()
        ]
    return result


def sum_petty_pengeluaran(items: List[Dict[str, Any]]) -> int:
    """Total pengeluaran = jumlah semua baris kredit / biaya yang ditambahkan."""
    total = sum(int(i.get("kredit") or 0) for i in items)
    if total > 0:
        return total
    return sum(
        int(i.get("jumlah") or 0)
        for i in items
        if int(i.get("debit") or 0) == 0
    )


# Bulk actions
def recalc_petty_cash_laporan(conn, upload_id: int):
    """Hitung ulang total laporan setelah hapus transaksi."""
    rows = conn.execute(
        "SELECT debit, kredit, saldo_akhir FROM petty_cash_items WHERE upload_id = ? ORDER BY id",
        (upload_id,),
    ).fetchall()
    total_debit = sum(r[0] or 0 for r in rows)
    total_kredit = sum(r[1] or 0 for r in rows)
    saldo_akhir = rows[-1][2] if rows else 0
    conn.execute("""
        UPDATE petty_cash_laporan SET
            total_debit = ?, total_kredit = ?, total_digantikan = ?,
            sisa_dana = ?, saldo_akhir = ?
        WHERE upload_id = ?
    """, (total_debit, total_kredit, total_kredit, saldo_akhir, saldo_akhir, upload_id))
    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (len(rows), upload_id))
