"""Tagihan CRUD routes."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth.session import redirect_with_flash, require_login
from app.db import get_db

router = APIRouter()


@router.post("/tagihan")
async def create_tagihan(
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pos: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form("DIAJUKAN"),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
    kategori: str = Form("tagihan"),
):
    conn = get_db()
    conn.execute("""
        INSERT INTO tagihan (no, pos, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, kategori, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        no.strip() or None,
        pos.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or "DIAJUKAN",
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        kategori or "tagihan",
        user["id"]
    ))
    conn.commit()
    conn.close()

    if request.headers.get("hx-request"):
        return JSONResponse({"success": True})

    return RedirectResponse("/tagihan", status_code=303)


@router.post("/tagihan/{tagihan_id}/update")
async def update_tagihan(
    tagihan_id: int,
    request: Request,
    user=Depends(require_login),
    no: str = Form(""),
    pos: str = Form(""),
    pengajuan: str = Form(...),
    jumlah: int = Form(...),
    status: str = Form(""),
    rekening: str = Form(""),
    tanggal: str = Form(""),
    atas_nama: str = Form(""),
    nomor_rekening: str = Form(""),
    bank: str = Form(""),
    kategori: str = Form(""),
):
    conn = get_db()
    conn.execute("""
        UPDATE tagihan SET
            no = ?,
            pos = ?,
            pengajuan = ?,
            jumlah = ?,
            status = ?,
            rekening = ?,
            tanggal = ?,
            atas_nama = ?,
            nomor_rekening = ?,
            bank = ?,
            kategori = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        no.strip() or None,
        pos.strip() or None,
        pengajuan.strip(),
        jumlah,
        status or None,
        rekening.strip() or None,
        tanggal or None,
        atas_nama.strip() or None,
        nomor_rekening.strip() or None,
        bank.strip() or None,
        kategori or None,
        tagihan_id
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/tagihan", status_code=303)


@router.post("/tagihan/{tagihan_id}/delete")
async def delete_tagihan(tagihan_id: int, user=Depends(require_login)):
    conn = get_db()
    conn.execute("DELETE FROM tagihan WHERE id = ?", (tagihan_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/tagihan", status_code=303)
