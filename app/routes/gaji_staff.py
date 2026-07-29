"""Gaji staff — terhubung data personel Setup & dana Transfer BGN."""
import csv
from datetime import date
from io import StringIO
from typing import Dict

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.auth.session import is_viewer, render_template, require_login
from app.constants import FEE_PAYROL_PER_ORANG
from app.db import get_db
from app.services.personnel import list_personnel
from app.services.report_sync import build_keuangan_link_context, filter_items_by_date_range
from app.services.transfer_reports import calc_fee_payrol, get_gaji_staff
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()
KATEGORI = "gaji_staff"


@router.get("/gaji-staff", response_class=HTMLResponse)
async def gaji_staff_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    status: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
    message: str = "",
    success: bool = False,
):
    filters: Dict = {}
    if search:
        filters["search"] = search
    if status:
        filters["status"] = status
    if tanggal:
        filters["tanggal"] = tanggal

    data = get_gaji_staff(filters)
    data = filter_items_by_date_range(data, dari, sampai)

    for item in data:
        item["fee_payrol"] = FEE_PAYROL_PER_ORANG
        item["total_bayar"] = (item.get("jumlah") or 0) + FEE_PAYROL_PER_ORANG

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR") for item in data)
        main_status = "Sukses" if all_terbayar else "Belum Lunas"

    conn = get_db()
    gs_filter = f"kategori = '{KATEGORI}'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {gs_filter}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    total_fee_payrol = calc_fee_payrol(len(data))
    total_grand = total_filtered + total_fee_payrol

    return render_template(request, "gaji_staff.html", {
        "user": user,
        "items": data,
        "total_filtered": total_filtered,
        "total_fee_payrol": total_fee_payrol,
        "total_grand": total_grand,
        "fee_payrol_amount": FEE_PAYROL_PER_ORANG,
        "main_status": main_status,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "filters": {
            "search": search,
            "status": status,
            "tanggal": tanggal,
            "dari": (dari or "").strip(),
            "sampai": (sampai or "").strip(),
        },
        **build_keuangan_link_context(dari, sampai, module_key="gaji_staff"),
        "personnel_options": list_personnel("staff", aktif_only=True),
        "status_options": sorted(s for s in statuses if s),
        "message": message,
        "success": success,
        "can_edit": not is_viewer(user),
    })


@router.post("/gaji-staff")
async def create_gaji_staff(
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
    if is_viewer(user):
        return RedirectResponse("/gaji-staff", status_code=303)
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        KATEGORI,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/gaji-staff", status_code=303)


@router.post("/gaji-staff/{item_id}/update")
async def update_gaji_staff(
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
    if is_viewer(user):
        return RedirectResponse("/gaji-staff", status_code=303)
    conn = get_db()
    conn.execute(f"""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = ?
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
        KATEGORI,
        item_id,
        KATEGORI,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/gaji-staff", status_code=303)


@router.post("/gaji-staff/{item_id}/delete")
async def delete_gaji_staff(item_id: int, user=Depends(require_login)):
    if is_viewer(user):
        return RedirectResponse("/gaji-staff", status_code=303)
    conn = get_db()
    conn.execute(
        f"DELETE FROM tagihan WHERE id = ? AND kategori = ?",
        (item_id, KATEGORI),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/gaji-staff", status_code=303)


@router.post("/api/gaji-staff/bulk-delete")
async def api_gaji_staff_bulk_delete(request: Request, user=Depends(require_login)):
    if is_viewer(user):
        return JSONResponse({"error": "Akses ditolak"}, status_code=403)
    try:
        data = await request.json()
        ids = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"DELETE FROM tagihan WHERE id IN ({placeholders}) AND kategori = ?",
            ids + [KATEGORI],
        )
        deleted = conn.total_changes
        conn.commit()
        conn.close()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/gaji-staff/bulk-update")
async def api_gaji_staff_bulk_update(request: Request, user=Depends(require_login)):
    if is_viewer(user):
        return JSONResponse({"error": "Akses ditolak"}, status_code=403)
    try:
        data = await request.json()
        ids = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
        status = data.get("status")
        if not ids or status is None:
            return JSONResponse({"error": "no valid ids or status"}, status_code=400)
        conn = get_db()
        placeholders = ",".join("?" * len(ids))
        from app.services.approval import bulk_set_tagihan_status

        updated = bulk_set_tagihan_status(conn, ids, status, user, kategori=KATEGORI)
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


@router.get("/export/gaji-staff/csv")
async def export_gaji_staff_csv(user=Depends(require_login)):
    data = get_gaji_staff()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NO", "TANGGAL", "NAMA STAFF", "NAMA REKENING", "NOMOR REKENING", "BANK", "JUMLAH", "STATUS"])
    for d in data:
        writer.writerow([
            d.get("no") or "",
            d.get("tanggal") or "",
            d.get("pengajuan") or "",
            d.get("atas_nama") or "",
            d.get("nomor_rekening") or "",
            d.get("bank") or "",
            d.get("jumlah") or 0,
            d.get("status") or "",
        ])
    filename = f"gaji_staff_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )