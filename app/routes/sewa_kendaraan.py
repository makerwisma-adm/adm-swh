"""Sewa kendaraan — anggaran dari dana operasional Transfer BGN."""
import csv
from datetime import date
from io import StringIO
from typing import Dict

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.auth.session import is_viewer, render_template, require_login
from app.db import get_db
from app.services.report_sync import build_keuangan_link_context, filter_items_by_date_range
from app.services.sewa_kendaraan import KATEGORI, get_sewa_kendaraan
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/sewa-kendaraan", response_class=HTMLResponse)
async def sewa_kendaraan_page(
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

    data = get_sewa_kendaraan(filters)
    data = filter_items_by_date_range(data, dari, sampai)

    if not data:
        main_status = "—"
    else:
        all_terbayar = all((item.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR") for item in data)
        main_status = "Lunas" if all_terbayar else "Belum Lunas"

    conn = get_db()
    sk_filter = f"kategori = '{KATEGORI}'"
    statuses = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT status FROM tagihan WHERE status IS NOT NULL AND {sk_filter}"
        ).fetchall()
    ]
    conn.close()

    total_filtered = sum(d["jumlah"] for d in data)
    terbayar_total = sum(d["jumlah"] for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_total = sum(d["jumlah"] for d in data if (d.get("status") or "").upper() == "DIAJUKAN")
    terbayar_count = sum(1 for d in data if (d.get("status") or "").upper() in ("DIBAYARKAN", "TERBAYAR"))
    diajukan_count = sum(1 for d in data if (d.get("status") or "").upper() == "DIAJUKAN")

    return render_template(request, "sewa_kendaraan.html", {
        "user": user,
        "items": data,
        "total_filtered": total_filtered,
        "terbayar_total": terbayar_total,
        "diajukan_total": diajukan_total,
        "terbayar_count": terbayar_count,
        "diajukan_count": diajukan_count,
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
        **build_keuangan_link_context(dari, sampai, module_key="sewa_kendaraan"),
        "status_options": sorted(s for s in statuses if s),
        "message": message,
        "success": success,
        "can_edit": not is_viewer(user),
    })


@router.post("/sewa-kendaraan")
async def create_sewa_kendaraan(
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    pos: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    if is_viewer(user):
        return RedirectResponse("/sewa-kendaraan", status_code=303)
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (
            no, pengajuan, jumlah, status, rekening, tanggal, pos,
            atas_nama, nomor_rekening, bank, kategori, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        pos.strip() or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        KATEGORI,
        user["id"],
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/sewa-kendaraan", status_code=303)


@router.post("/sewa-kendaraan/{item_id}/update")
async def update_sewa_kendaraan(
    item_id: int,
    user=Depends(require_login),
    no: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    pos: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
):
    if is_viewer(user):
        return RedirectResponse("/sewa-kendaraan", status_code=303)
    conn = get_db()
    conn.execute(f"""
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, pos = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = ?
    """, (
        no.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        pos.strip() or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        KATEGORI,
        item_id,
        KATEGORI,
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/sewa-kendaraan", status_code=303)


@router.post("/sewa-kendaraan/{item_id}/delete")
async def delete_sewa_kendaraan(item_id: int, user=Depends(require_login)):
    if is_viewer(user):
        return RedirectResponse("/sewa-kendaraan", status_code=303)
    conn = get_db()
    conn.execute(
        f"DELETE FROM tagihan WHERE id = ? AND kategori = ?",
        (item_id, KATEGORI),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/sewa-kendaraan", status_code=303)


@router.post("/api/sewa-kendaraan/bulk-delete")
async def api_sewa_kendaraan_bulk_delete(request: Request, user=Depends(require_login)):
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


@router.post("/api/sewa-kendaraan/bulk-update")
async def api_sewa_kendaraan_bulk_update(request: Request, user=Depends(require_login)):
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


@router.get("/export/sewa-kendaraan/csv")
async def export_sewa_kendaraan_csv(user=Depends(require_login)):
    data = get_sewa_kendaraan()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Laporan Sewa Kendaraan — Dana Operasional Transfer BGN"])
    writer.writerow([])
    writer.writerow([
        "No. Plat", "Tanggal", "Kendaraan / Vendor", "Periode Sewa", "Penyedia",
        "Atas Nama", "No. Rekening", "Bank", "Jumlah (Rp)", "Status",
    ])
    for d in data:
        writer.writerow([
            d.get("no") or "",
            d.get("tanggal") or "",
            d.get("pengajuan") or "",
            d.get("pos") or "",
            d.get("rekening") or "",
            d.get("atas_nama") or "",
            d.get("nomor_rekening") or "",
            d.get("bank") or "",
            d.get("jumlah") or 0,
            d.get("status") or "",
        ])
    writer.writerow([])
    writer.writerow(["Total", "", "", "", "", "", "", "", sum(d.get("jumlah") or 0 for d in data), ""])
    filename = f"sewa_kendaraan_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )