"""File upload routes."""
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.auth.session import is_admin, is_viewer, redirect_with_flash, render_template, require_login
from app.config import UPLOAD_DIR
from app.db import get_db
from app.parsers.upload import parse_upload_file

router = APIRouter()


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, user=Depends(require_login), message: str = "", success: bool = False, pos: str = "", upload_id: int = 0):
    return render_template(request, "upload.html", {
        "user": user,
        "message": message,
        "success": success,
        "pos": pos,
        "upload_id": upload_id
    })

@router.post("/upload", response_class=HTMLResponse)
async def upload_laporan(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
    pos: str = Form(""),
    pos_other: str = Form(""),
    periode: str = Form(""),
    kategori: str = Form("tagihan")
):
    if is_viewer(user):
        return redirect_with_flash(
            request,
            "/dashboard",
            "Akses ditolak. Akun Anda hanya dapat melihat data.",
        )

    if not is_admin(user) and (kategori or "tagihan") not in ("tagihan", "", "tagihan_bulanan"):
        return redirect_with_flash(
            request,
            "/tagihan",
            "Akses ditolak. Member hanya dapat upload PDF Tagihan.",
        )

    if kategori == "petty_cash":
        return redirect_with_flash(
            request,
            "/petty-cash",
            "Upload Petty Cash hanya melalui halaman Petty Cash",
        )

    final_pos = (pos_other.strip() if pos_other.strip() else pos.strip()) or None

    # Save file
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    conn = get_db()

    # Create upload record first (needed for petty cash nota folder)
    conn.execute("""
        INSERT INTO uploads (filename, pos, periode, created_by)
        VALUES (?, ?, ?, ?)
    """, (file.filename, final_pos, periode or None, user["id"]))
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Parse
    try:
        parsed = parse_upload_file(file_path, file.filename, kategori or "tagihan", upload_id)
    except Exception as e:
        conn.close()
        if kategori == "gaji_relawan":
            return redirect_with_flash(request, "/gaji-relawan", f"Error parsing file: {str(e)}")
        return redirect_with_flash(request, f"/tagihan?kategori={kategori or 'tagihan'}", f"Error parsing file: {str(e)}")

    item_list = parsed if parsed else []

    if not item_list:
        conn.close()
        if kategori == "gaji_relawan":
            return redirect_with_flash(request, "/gaji-relawan", "Tidak ada data yang bisa dibaca dari file")
        return redirect_with_flash(request, f"/tagihan?kategori={kategori or 'tagihan'}", "Tidak ada data yang bisa dibaca dari file")

    inserted = 0
    for item in item_list:
        pengajuan = item.get('pengajuan') or item.get('deskripsi') or item.get('penajuan') or item.get('keterangan') or ''
        if not pengajuan:
            continue

        try:
            debit_val = int(item.get('debit') or 0)
            kredit_val = int(item.get('kredit') or 0)
            jumlah = int(float(item.get('jumlah') or item.get('total') or 0))
        except Exception:
            debit_val = kredit_val = jumlah = 0
        if not jumlah:
            jumlah = kredit_val if kredit_val > 0 else debit_val
        if jumlah <= 0 and debit_val <= 0 and kredit_val <= 0:
            continue

        no = str(item.get('no') or '').strip() or None
        status = str(item.get('status') or 'DIAJUKAN').strip() or 'DIAJUKAN'
        kategori_val = kategori or "tagihan"
        if kategori_val in ("tagihan", "tagihan_bulanan", ""):
            rekening = str(item.get('rekening') or '').strip() or None
        else:
            rekening = str(item.get('rekening') or 'PETTY CASH').strip() or 'PETTY CASH'
        pos_val = str(item.get('pos') or item.get('pemasok') or final_pos or '').strip() or None
        tanggal = str(item.get('tanggal') or '').strip() or None
        atas_nama = str(item.get('atas nama rek') or item.get('atas_nama') or item.get('atas nama') or '').strip() or None
        nomor_rek = str(item.get('nomor rekening') or item.get('nomor_rekening') or item.get('no rekening') or '').strip() or None
        bank = str(item.get('bank') or '').strip() or None
        nota_path = item.get('nota_path')
        saldo_akhir = item.get('saldo_akhir')
        tipe_transaksi = item.get('tipe_transaksi') or item.get('tipe')

        dup_check = conn.execute("""
            SELECT 1 FROM tagihan 
            WHERE COALESCE(no,'') = COALESCE(?, '') 
              AND pengajuan = ? 
              AND jumlah = ? 
              AND COALESCE(tanggal,'') = COALESCE(?, '') 
              AND kategori = ?
            LIMIT 1
        """, (no, pengajuan, jumlah, tanggal, kategori or "tagihan")).fetchone()

        if dup_check:
            continue

        conn.execute("""
            INSERT INTO tagihan 
            (no, pengajuan, jumlah, status, rekening, tanggal, atas_nama, nomor_rekening, bank, pos, kategori, upload_id, nota_path, debit, kredit, saldo_akhir, tipe_transaksi, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            no, pengajuan, jumlah, status, rekening, tanggal,
            atas_nama, nomor_rek, bank, pos_val,
            kategori or "tagihan", upload_id, nota_path,
            debit_val, kredit_val, saldo_akhir, tipe_transaksi,
            user["id"]
        ))
        inserted += 1

    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (inserted, upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} baris data"
    if final_pos:
        msg += f" untuk Pos: {final_pos}"

    if kategori == "gaji_relawan":
        return redirect_with_flash(request, "/gaji-relawan", msg, success=True)
    if kategori == "insentif_mitra":
        return redirect_with_flash(request, "/insentif-mitra", msg, success=True)

    return redirect_with_flash(request, f"/tagihan?kategori={kategori or 'tagihan'}", msg, success=True)
