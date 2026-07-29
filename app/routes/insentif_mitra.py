"""Insentif mitra routes."""
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.auth.session import (
    can_member_upload,
    is_admin,
    is_mitra,
    is_viewer,
    redirect_with_flash,
    render_template,
    require_admin,
    require_login,
)
from app.services.mitra_access import get_mitra_nama
from app.services.mitra_page_filter import apply_mitra_page_filter
from app.services.mitra_portal import build_mitra_portal_context
from app.config import UPLOAD_DIR
from app.db import get_db
from app.services.insentif_mitra_page import build_insentif_mitra_page_context
from app.services.transfer_reports import (
    _export_filename_from_laporan,
    build_pic_transfer_export_rows,
    build_pic_transfer_xlsx_bytes,
    parse_insentif_mitra_xlsx,
    recalc_insentif_mitra_laporan,
    resolve_insentif_mitra_export,
)
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/insentif-mitra", response_class=HTMLResponse)
async def insentif_mitra_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
    message: str = "",
    success: bool = False,
):
    ctx = build_insentif_mitra_page_context(
        upload_id=upload_id,
        search=search,
        status=status,
        rekening=rekening,
        tanggal=tanggal,
        dari=dari,
        sampai=sampai,
    )
    portal_ctx = {}
    if is_mitra(user):
        ctx = apply_mitra_page_filter(ctx, get_mitra_nama(user))
        portal_ctx = build_mitra_portal_context(user)

    return render_template(request, "insentif_mitra.html", {
        **portal_ctx,
        **ctx,
        "user": user,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "message": message,
        "success": success,
        "active_menu": "insentif_mitra",
    })


@router.post("/insentif-mitra/upload")
async def insentif_mitra_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    """Upload Excel insentif mitra — format transfer massal Mandiri; download CSV mengekstrak ke format bank."""
    if is_viewer(user):
        return redirect_with_flash(
            request,
            "/insentif-mitra",
            "Akses ditolak. Akun Anda hanya dapat melihat data.",
        )
    if not is_admin(user) and not can_member_upload(user):
        return redirect_with_flash(
            request,
            "/insentif-mitra",
            "Akses ditolak. Anda tidak dapat mengunggah file.",
        )
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""

    conn = get_db()
    conn.execute(
        "INSERT INTO uploads (filename, created_by) VALUES (?, ?)",
        (file.filename, user["id"]),
    )
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        if ext in ("xlsx", "xls"):
            parsed = parse_insentif_mitra_xlsx(file_path, file.filename)
        else:
            conn.close()
            return redirect_with_flash(
                request,
                "/insentif-mitra",
                "Format tidak didukung. Upload file Excel (.xlsx / .xls).",
            )
    except Exception as e:
        conn.close()
        return redirect_with_flash(request, "/insentif-mitra", f"Error parsing file: {str(e)}")

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []
    ip_meta = parsed.get("meta", {}) if isinstance(parsed, dict) else {}

    if not item_list:
        conn.close()
        return redirect_with_flash(request, "/insentif-mitra", "Tidak ada data yang bisa dibaca dari file")

    inserted = 0
    for item in item_list:
        pengajuan = item.get("pengajuan") or item.get("atas_nama") or ""
        if not pengajuan:
            continue
        jumlah = int(item.get("jumlah") or 0)
        if jumlah <= 0:
            continue

        dup = conn.execute("""
            SELECT 1 FROM tagihan
            WHERE upload_id = ? AND pengajuan = ? AND jumlah = ?
            LIMIT 1
        """, (upload_id, pengajuan, jumlah)).fetchone()
        if dup:
            continue

        conn.execute("""
            INSERT INTO tagihan
            (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, upload_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_mitra', ?, ?)
        """, (
            item.get("no"),
            pengajuan,
            jumlah,
            item.get("status") or "DIAJUKAN",
            item.get("rekening") or "TRANSFER MASSAL",
            item.get("tanggal") or ip_meta.get("tanggal_pembayaran"),
            item.get("atas_nama"),
            item.get("nomor_rekening"),
            item.get("bank"),
            upload_id,
            user["id"],
        ))
        inserted += 1

    conn.execute("""
        INSERT OR REPLACE INTO insentif_mitra_laporan
        (upload_id, tanggal_pembayaran, rekening_sumber, jumlah_penerima, total_gaji,
         periode, bank, kota, filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        upload_id,
        ip_meta.get("tanggal_pembayaran"),
        ip_meta.get("rekening_sumber"),
        ip_meta.get("jumlah_penerima") or inserted,
        ip_meta.get("total_gaji") or sum(i.get("jumlah", 0) for i in item_list),
        ip_meta.get("periode"),
        ip_meta.get("bank") or "MANDIRI",
        ip_meta.get("kota"),
        file.filename,
    ))
    conn.execute("UPDATE uploads SET record_count = ?, periode = ? WHERE id = ?",
                 (inserted, ip_meta.get("periode"), upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} data insentif mitra"
    if ip_meta.get("periode"):
        msg += f" ({ip_meta['periode']})"
    return redirect_with_flash(request, f"/insentif-mitra?upload_id={upload_id}", msg, success=True)


@router.post("/insentif-mitra")
async def create_insentif_mitra(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    periode: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, pos, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_mitra', ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        periode.strip() or None,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-mitra", status_code=303)


@router.post("/insentif-mitra/{item_id}/update")
async def update_insentif_mitra(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    periode: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?, pos = ?,
            kategori = 'insentif_mitra', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'insentif_mitra'
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        periode.strip() or None,
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-mitra", status_code=303)


@router.post("/insentif-mitra/{item_id}/delete")
async def delete_insentif_mitra(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'insentif_mitra'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'insentif_mitra'", (item_id,))
    if row and row[0]:
        recalc_insentif_mitra_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-mitra", status_code=303)


@router.post("/api/insentif-mitra/bulk-delete")
async def api_insentif_mitra_bulk_delete(request: Request, user=Depends(require_admin)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        upload_rows = conn.execute(
            f"""SELECT DISTINCT upload_id FROM tagihan
                WHERE id IN ({placeholders}) AND kategori = 'insentif_mitra' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'insentif_mitra'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_insentif_mitra_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/insentif-mitra/bulk-update")
async def api_insentif_mitra_bulk_update(request: Request, user=Depends(require_admin)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        from app.services.approval import bulk_set_tagihan_status

        updated = bulk_set_tagihan_status(conn, ids, status, user, kategori="insentif_mitra")
        conn.commit()
        conn.close()
        if updated == 0:
            return JSONResponse(
                {"error": "Tidak ada status yang diubah. DIAJUKAN harus disetujui KA SPPG sebelum DIBAYARKAN."},
                status_code=400,
            )
        return JSONResponse({"success": True, "updated": updated})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/export/insentif-mitra/csv")
async def export_insentif_mitra_csv(user=Depends(require_login), upload_id: int = 0):
    import csv
    from io import StringIO

    laporan, items, _ = resolve_insentif_mitra_export(upload_id)
    if not laporan or not items:
        return Response("Tidak ada data insentif mitra untuk diunduh.", status_code=404)

    output = StringIO()
    writer = csv.writer(output)
    for row in build_pic_transfer_export_rows(laporan, items):
        writer.writerow(row)
    output.seek(0)
    filename = _export_filename_from_laporan(laporan, "csv")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/insentif-mitra/xlsx")
async def export_insentif_mitra_xlsx(user=Depends(require_login), upload_id: int = 0):
    laporan, items, _ = resolve_insentif_mitra_export(upload_id)
    if not laporan or not items:
        return Response("Tidak ada data insentif mitra untuk diunduh.", status_code=404)

    filename = _export_filename_from_laporan(laporan, "xlsx")
    return Response(
        content=build_pic_transfer_xlsx_bytes(laporan, items),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
