"""Pengeluaran mitra routes."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth.session import (
    is_mitra,
    is_viewer,
    redirect_with_flash,
    render_template,
    require_login,
)
from app.db import get_db
from app.services.mitra_access import get_mitra_nama
from app.services.mitra_page_filter import apply_mitra_page_filter
from app.services.mitra_portal import build_mitra_portal_context
from app.services.pengeluaran_mitra_page import build_pengeluaran_mitra_page_context
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()
KATEGORI = "pengeluaran_mitra"


def _deny_mutation(request: Request, user):
    if is_viewer(user) or is_mitra(user):
        return redirect_with_flash(
            request,
            "/pengeluaran-mitra",
            "Akses ditolak. Akun Anda hanya dapat melihat data.",
        )
    return None


@router.get("/pengeluaran-mitra", response_class=HTMLResponse)
async def pengeluaran_mitra_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
    message: str = "",
    success: bool = False,
):
    ctx = build_pengeluaran_mitra_page_context(
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

    return render_template(request, "pengeluaran_mitra.html", {
        **portal_ctx,
        **ctx,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "pengeluaran_mitra",
        "message": message,
        "success": success,
    })


@router.post("/pengeluaran-mitra")
async def create_pengeluaran_mitra(
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
    denied = _deny_mutation(request, user)
    if denied:
        return denied

    conn = get_db()
    conn.execute(
        """
        INSERT INTO tagihan
        (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            no.strip() or None,
            pengajuan.strip(),
            jumlah,
            status or "DIAJUKAN",
            rekening.strip() or "PENGELUARAN MITRA",
            tanggal or None,
            atas_nama.strip() or None,
            nomor_rekening.strip() or None,
            bank.strip() or None,
            KATEGORI,
            user["id"],
        ),
    )
    conn.commit()
    conn.close()
    return redirect_with_flash(
        request,
        "/pengeluaran-mitra",
        "Pengeluaran mitra berhasil ditambahkan.",
        success=True,
    )


@router.post("/pengeluaran-mitra/{item_id}/update")
async def update_pengeluaran_mitra(
    item_id: int,
    request: Request,
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
    denied = _deny_mutation(request, user)
    if denied:
        return denied

    conn = get_db()
    conn.execute(
        """
        UPDATE tagihan SET
            no = ?, pengajuan = ?, jumlah = ?, status = ?, rekening = ?,
            tanggal = ?, atas_nama = ?, nomor_rekening = ?, bank = ?,
            kategori = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND kategori = ?
        """,
        (
            no.strip() or None,
            pengajuan.strip(),
            jumlah,
            status or None,
            rekening.strip() or "PENGELUARAN MITRA",
            tanggal or None,
            atas_nama.strip() or None,
            nomor_rekening.strip() or None,
            bank.strip() or None,
            KATEGORI,
            item_id,
            KATEGORI,
        ),
    )
    conn.commit()
    conn.close()
    return redirect_with_flash(
        request,
        "/pengeluaran-mitra",
        "Pengeluaran mitra berhasil diperbarui.",
        success=True,
    )


@router.post("/pengeluaran-mitra/{item_id}/delete")
async def delete_pengeluaran_mitra(item_id: int, request: Request, user=Depends(require_login)):
    denied = _deny_mutation(request, user)
    if denied:
        return denied

    conn = get_db()
    conn.execute(
        "DELETE FROM tagihan WHERE id = ? AND kategori = ?",
        (item_id, KATEGORI),
    )
    conn.commit()
    conn.close()
    return redirect_with_flash(
        request,
        "/pengeluaran-mitra",
        "Pengeluaran mitra berhasil dihapus.",
        success=True,
    )


@router.post("/api/pengeluaran-mitra/bulk-delete")
async def api_pengeluaran_mitra_bulk_delete(request: Request, user=Depends(require_login)):
    denied = _deny_mutation(request, user)
    if denied:
        return denied

    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
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