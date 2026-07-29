"""JSON API routes."""
import os

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.auth.session import require_admin, require_login
from app.config import UPLOAD_DIR
from app.constants import (
    ALLOWED_NOTA_EXT,
    TAGIHAN_ATTACHMENT_COLS,
    TAGIHAN_ATTACHMENT_FIELDS,
    TAGIHAN_ATTACHMENT_KATEGORI,
)
from app.db import get_db
from app.services.dashboard import get_monthly_expenses
from app.services.petty_cash import (
    _delete_nota_file,
    _delete_upload_file,
    recalc_petty_cash_laporan,
)
from app.services.tagihan import get_all_tagihan, get_summary
from app.utils.formatters import format_rupiah

router = APIRouter()


@router.post("/api/petty-cash/{item_id}/nota")
async def api_petty_cash_upload_nota(
    item_id: int,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_NOTA_EXT:
        return JSONResponse({"error": "Format file tidak didukung"}, status_code=400)

    conn = get_db()
    row = conn.execute(
        "SELECT id, upload_id, nota_path FROM petty_cash_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)

    nota_dir = os.path.join(UPLOAD_DIR, "nota", str(row["upload_id"]))
    os.makedirs(nota_dir, exist_ok=True)
    safe_ext = ".jpg" if ext in (".jpg", ".jpeg") else ext
    fname = f"nota_item_{item_id}{safe_ext}"
    rel_path = f"nota/{row['upload_id']}/{fname}"
    full_path = os.path.join(UPLOAD_DIR, rel_path)

    if row["nota_path"] and row["nota_path"] != rel_path:
        _delete_nota_file(row["nota_path"])

    content = await file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    conn.execute(
        "UPDATE petty_cash_items SET nota_path = ? WHERE id = ?", (rel_path, item_id)
    )
    conn.commit()
    conn.close()
    return JSONResponse({"success": True, "nota_path": rel_path})


@router.patch("/api/petty-cash/{item_id}/ket")
async def api_petty_cash_update_ket(
    item_id: int,
    request: Request,
    user=Depends(require_login),
):
    try:
        data = await request.json()
        ket = (data.get("ket") or "").strip() or None
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM petty_cash_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)
        conn.execute(
            "UPDATE petty_cash_items SET ket = ? WHERE id = ?", (ket, item_id)
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "ket": ket or ""})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.patch("/api/petty-cash/{item_id}/status")
async def api_petty_cash_update_status(
    item_id: int,
    request: Request,
    user=Depends(require_login),
):
    try:
        data = await request.json()
        status = (data.get("status") or "").strip().upper()
        valid = {"DIAJUKAN", "DISETUJUI", "DIBAYAR", "DIBATALKAN"}
        if status not in valid:
            return JSONResponse(
                {"error": f"Status harus salah satu dari: {', '.join(valid)}"},
                status_code=400,
            )
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM petty_cash_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)
        conn.execute(
            "UPDATE petty_cash_items SET status = ? WHERE id = ?", (status, item_id)
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "status": status})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/petty-cash/bulk-update")
async def api_petty_cash_bulk_update(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        new_status = (data.get("status") or "").strip().upper()
        valid = {"DIAJUKAN", "DISETUJUI", "DIBAYAR", "DIBATALKAN"}
        if new_status not in valid:
            return JSONResponse(
                {"error": f"Status harus salah satu dari: {', '.join(valid)}"},
                status_code=400,
            )
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE petty_cash_items SET status = ? WHERE id IN ({placeholders})",
            [new_status] + ids,
        )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": len(ids), "status": new_status})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/petty-cash/{item_id}/nota")
async def api_petty_cash_delete_nota(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT nota_path FROM petty_cash_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)

    if row["nota_path"]:
        _delete_nota_file(row["nota_path"])

    conn.execute("UPDATE petty_cash_items SET nota_path = NULL WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"success": True})


@router.post("/api/tagihan/{item_id}/{field}")
async def api_tagihan_upload_attachment(
    item_id: int,
    field: str,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    field = (field or "").lower()
    if field not in TAGIHAN_ATTACHMENT_FIELDS:
        return JSONResponse({"error": "Field lampiran tidak valid"}, status_code=400)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_NOTA_EXT:
        return JSONResponse({"error": "Format file tidak didukung"}, status_code=400)

    col = TAGIHAN_ATTACHMENT_COLS[field]
    conn = get_db()
    row = conn.execute(
        f"SELECT id, upload_id, kategori, {col} AS file_path FROM tagihan WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)
    if (row["kategori"] or "") not in TAGIHAN_ATTACHMENT_KATEGORI:
        conn.close()
        return JSONResponse({"error": "Lampiran tidak didukung untuk kategori ini"}, status_code=400)

    upload_key = row["upload_id"] or item_id
    attach_dir = os.path.join(UPLOAD_DIR, "lampiran", str(upload_key))
    os.makedirs(attach_dir, exist_ok=True)
    safe_ext = ".jpg" if ext in (".jpg", ".jpeg") else ext
    fname = f"{field}_item_{item_id}{safe_ext}"
    rel_path = f"lampiran/{upload_key}/{fname}"
    full_path = os.path.join(UPLOAD_DIR, rel_path)

    if row["file_path"] and row["file_path"] != rel_path:
        _delete_upload_file(row["file_path"])

    content = await file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    conn.execute(f"UPDATE tagihan SET {col} = ? WHERE id = ?", (rel_path, item_id))
    conn.commit()
    conn.close()
    return JSONResponse({"success": True, "path": rel_path, "field": field})


@router.delete("/api/tagihan/{item_id}/{field}")
async def api_tagihan_delete_attachment(item_id: int, field: str, user=Depends(require_login)):
    field = (field or "").lower()
    if field not in TAGIHAN_ATTACHMENT_FIELDS:
        return JSONResponse({"error": "Field lampiran tidak valid"}, status_code=400)

    col = TAGIHAN_ATTACHMENT_COLS[field]
    conn = get_db()
    row = conn.execute(
        f"SELECT id, kategori, {col} AS file_path FROM tagihan WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "Transaksi tidak ditemukan"}, status_code=404)
    if (row["kategori"] or "") not in TAGIHAN_ATTACHMENT_KATEGORI:
        conn.close()
        return JSONResponse({"error": "Lampiran tidak didukung untuk kategori ini"}, status_code=400)

    if row["file_path"]:
        _delete_upload_file(row["file_path"])

    conn.execute(f"UPDATE tagihan SET {col} = NULL WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"success": True, "field": field})


@router.post("/api/petty-cash/bulk-delete")
async def api_petty_cash_bulk_delete(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()

        # Ambil upload_id dari item pertama
        first = conn.execute(
            "SELECT upload_id FROM petty_cash_items WHERE id = ?", (ids[0],)
        ).fetchone()
        upload_id = first[0] if first else None

        # Hapus nota file dari setiap item
        for item_id in ids:
            row = conn.execute(
                "SELECT nota_path FROM petty_cash_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row and row[0]:
                _delete_nota_file(row[0])

        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM petty_cash_items WHERE id IN ({placeholders})", ids)

        if upload_id:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM petty_cash_items WHERE upload_id = ?", (upload_id,)
            ).fetchone()[0]
            if remaining == 0:
                conn.execute("DELETE FROM petty_cash_laporan WHERE upload_id = ?", (upload_id,))
                conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
            else:
                recalc_petty_cash_laporan(conn, upload_id)

        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": len(ids)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/api/tagihan/bulk-delete")
async def api_bulk_delete(request: Request, user=Depends(require_admin)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM tagihan WHERE id IN ({placeholders})", ids)
        deleted = conn.total_changes
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/api/tagihan/bulk-update")
async def api_bulk_update(request: Request, user=Depends(require_admin)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        pos = data.get("pos")
        status = data.get("status")
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        if pos is not None:
            conn.execute(f"UPDATE tagihan SET pos = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", [pos] + ids)
        updated = len(ids)
        if status is not None:
            from app.services.approval import bulk_set_tagihan_status

            updated = bulk_set_tagihan_status(conn, ids, status, user)
            if updated == 0:
                conn.close()
                return JSONResponse(
                    {"error": "Tidak ada status yang diubah. DIAJUKAN harus disetujui KA SPPG sebelum DIBAYARKAN."},
                    status_code=400,
                )
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "updated": updated})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/tagihan")
async def api_tagihan(user=Depends(require_login)):
    data = get_all_tagihan()
    return [{"id": d["id"], **d, "jumlah_fmt": format_rupiah(d["jumlah"])} for d in data]

@router.get("/api/summary")
async def api_summary(user=Depends(require_login)):
    return get_summary()


@router.get("/api/dashboard/monthly-chart")
async def api_dashboard_monthly_chart(
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
):
    data = get_monthly_expenses(dari or None, sampai or None)
    monthly = data["monthly"]
    return JSONResponse({
        "labels": [m["label"] for m in monthly],
        "values": [m["total"] for m in monthly],
        "dari": data["chart_dari"],
        "sampai": data["chart_sampai"],
        "dari_display": data["chart_dari_display"],
        "sampai_display": data["chart_sampai_display"],
        "total": data["chart_total"],
        "months": data["chart_months"],
    })
