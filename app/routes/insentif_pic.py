"""Insentif PIC routes."""
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.auth.session import (
    can_member_upload,
    is_admin,
    is_viewer,
    redirect_with_flash,
    render_template,
    require_admin,
    require_login,
)
from app.config import UPLOAD_DIR
from app.constants import FEE_PAYROL_PER_ORANG
from app.db import get_db
from app.services.transfer_reports import (
    _export_filename_from_laporan,
    build_pic_transfer_export_rows,
    build_pic_transfer_xlsx_bytes,
    calc_fee_payrol,
    get_insentif_pic,
    get_insentif_pic_laporans,
    parse_insentif_pic_xlsx,
    recalc_insentif_pic_laporan,
    resolve_insentif_pic_export,
)
from app.services.personnel import list_personnel
from app.services.report_sync import build_keuangan_link_context, filter_items_by_date_range
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/insentif-pic", response_class=HTMLResponse)
async def insentif_pic_page(
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
    periode_options = get_insentif_pic_laporans(active_only=True)
    laporans = periode_options
    laporan = None
    active_upload_ids = {lap["upload_id"] for lap in periode_options}

    filters = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if rekening:
        filters["rekening"] = rekening
    if tanggal:
        filters["tanggal"] = tanggal

    if upload_id and upload_id not in active_upload_ids:
        upload_id = 0

    view_all = upload_id == 0

    if upload_id and upload_id in active_upload_ids:
        laporan = next((lap for lap in periode_options if lap["upload_id"] == upload_id), None)
        filters["upload_id"] = upload_id

    data = get_insentif_pic(filters)
    data = filter_items_by_date_range(data, dari, sampai)

    periode_map = {lap["upload_id"]: lap.get("periode") or lap.get("filename") for lap in laporans}
    for item in data:
        uid = item.get("upload_id")
        item["periode_label"] = periode_map.get(uid, "Input Manual") if uid else "Input Manual"

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR") for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    ip_filter = "kategori = 'insentif_pic'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    rekenings = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT rekening FROM tagihan WHERE rekening IS NOT NULL AND {ip_filter}"
        ).fetchall()
    ]
    conn.close()

    for item in data:
        item["fee_payrol"] = FEE_PAYROL_PER_ORANG
        item["total_bayar"] = (item.get("jumlah") or 0) + FEE_PAYROL_PER_ORANG

    total_filtered = sum(d["jumlah"] for d in data)
    total_fee_payrol = calc_fee_payrol(len(data))
    total_grand = total_filtered + total_fee_payrol
    avg_gaji = int(total_filtered / len(data)) if data else 0
    max_item = max(data, key=lambda x: x["jumlah"]) if data else None
    min_item = min(data, key=lambda x: x["jumlah"]) if data else None
    total_all_batches = sum(lap.get("total_gaji") or 0 for lap in laporans)
    total_all_pic = sum(lap.get("jumlah_penerima") or lap.get("record_count") or 0 for lap in laporans)

    return render_template(request, "insentif_pic.html", {
        "user": user,
        "items": data,
        "laporans": laporans,
        "laporan": laporan,
        "view_all": view_all,
        "selected_upload_id": upload_id if upload_id else 0,
        "total_filtered": total_filtered,
        "total_fee_payrol": total_fee_payrol,
        "total_grand": total_grand,
        "fee_payrol_amount": FEE_PAYROL_PER_ORANG,
        "total_all_batches": total_all_batches,
        "total_all_pic": total_all_pic,
        "avg_gaji": avg_gaji,
        "max_item": max_item,
        "min_item": min_item,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {
            "search": search,
            "status": status,
            "rekening": rekening,
            "tanggal": tanggal,
            "periode": upload_id,
            "dari": (dari or "").strip(),
            "sampai": (sampai or "").strip(),
        },
        **build_keuangan_link_context(dari, sampai, module_key="insentif_pic"),
        "personnel_options": list_personnel("pic", aktif_only=True),
        "periode_options": periode_options,
        "status_options": sorted([s for s in statuses if s]),
        "rekening_options": sorted([r for r in rekenings if r]),
        "message": message,
        "success": success,
    })


@router.post("/insentif-pic/upload")
async def insentif_pic_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
):
    """Upload Excel insentif PIC — format transfer massal Mandiri; download CSV mengekstrak ke format bank."""
    if is_viewer(user):
        return redirect_with_flash(
            request,
            "/insentif-pic",
            "Akses ditolak. Akun Anda hanya dapat melihat data.",
        )
    if not is_admin(user) and not can_member_upload(user):
        return redirect_with_flash(
            request,
            "/insentif-pic",
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
            parsed = parse_insentif_pic_xlsx(file_path, file.filename)
        else:
            conn.close()
            return redirect_with_flash(
                request,
                "/insentif-pic",
                "Format tidak didukung. Upload file Excel (.xlsx / .xls).",
            )
    except Exception as e:
        conn.close()
        return redirect_with_flash(request, "/insentif-pic", f"Error parsing file: {str(e)}")

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []
    ip_meta = parsed.get("meta", {}) if isinstance(parsed, dict) else {}

    if not item_list:
        conn.close()
        return redirect_with_flash(request, "/insentif-pic", "Tidak ada data yang bisa dibaca dari file")

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_pic', ?, ?)
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
        INSERT OR REPLACE INTO insentif_pic_laporan
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

    msg = f"Berhasil mengunggah {inserted} data insentif PIC"
    if ip_meta.get("periode"):
        msg += f" ({ip_meta['periode']})"
    return redirect_with_flash(request, f"/insentif-pic?upload_id={upload_id}", msg, success=True)


@router.post("/insentif-pic")
async def create_insentif_pic(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'insentif_pic', ?)
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
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-pic", status_code=303)


@router.post("/insentif-pic/{item_id}/update")
async def update_insentif_pic(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = 'insentif_pic', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = 'insentif_pic'
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
        item_id,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-pic", status_code=303)


@router.post("/insentif-pic/{item_id}/delete")
async def delete_insentif_pic(item_id: int, user=Depends(require_login)):
    conn = get_db()
    row = conn.execute(
        "SELECT upload_id FROM tagihan WHERE id = ? AND kategori = 'insentif_pic'", (item_id,)
    ).fetchone()
    conn.execute("DELETE FROM tagihan WHERE id = ? AND kategori = 'insentif_pic'", (item_id,))
    if row and row[0]:
        recalc_insentif_pic_laporan(conn, row[0])
    conn.commit()
    conn.close()
    return RedirectResponse("/insentif-pic", status_code=303)


@router.post("/api/insentif-pic/bulk-delete")
async def api_insentif_pic_bulk_delete(request: Request, user=Depends(require_admin)):
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
                WHERE id IN ({placeholders}) AND kategori = 'insentif_pic' AND upload_id IS NOT NULL""",
            ids,
        ).fetchall()
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = 'insentif_pic'",
            ids,
        )
        deleted = conn.total_changes
        for row in upload_rows:
            recalc_insentif_pic_laporan(conn, row[0])
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/insentif-pic/bulk-update")
async def api_insentif_pic_bulk_update(request: Request, user=Depends(require_admin)):
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

        updated = bulk_set_tagihan_status(conn, ids, status, user, kategori="insentif_pic")
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


@router.get("/export/insentif-pic/csv")
async def export_insentif_pic_csv(user=Depends(require_login), upload_id: int = 0):
    import csv
    from io import StringIO

    laporan, items, _ = resolve_insentif_pic_export(upload_id)
    if not laporan or not items:
        return Response("Tidak ada data insentif PIC untuk diunduh.", status_code=404)

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


@router.get("/export/insentif-pic/xlsx")
async def export_insentif_pic_xlsx(user=Depends(require_login), upload_id: int = 0):
    laporan, items, _ = resolve_insentif_pic_export(upload_id)
    if not laporan or not items:
        return Response("Tidak ada data insentif PIC untuk diunduh.", status_code=404)

    filename = _export_filename_from_laporan(laporan, "xlsx")
    return Response(
        content=build_pic_transfer_xlsx_bytes(laporan, items),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
