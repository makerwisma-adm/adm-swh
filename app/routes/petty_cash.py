"""Petty cash routes."""
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.session import (
    can_member_upload,
    is_admin,
    is_viewer,
    redirect_with_flash,
    render_template,
    require_login,
)
from app.config import UPLOAD_DIR
from app.db import get_db
from app.parsers.upload import parse_petty_cash_pdf
from app.services.petty_cash import (
    filter_petty_cash_items,
    get_petty_cash_items,
    get_petty_cash_laporans,
    sum_petty_pengeluaran,
)
from app.services.report_sync import build_keuangan_link_context, filter_items_by_date_range
from app.services.finance_summary import (
    get_transfer_bgn_context,
    get_bgn_saldo_snapshot,
)
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/petty-cash", response_class=HTMLResponse)
async def petty_cash_page(
    request: Request,
    user=Depends(require_login),
    upload_id: int = 0,
    search: str = "",
    tanggal: str = "",
    jenis: str = "",
    dari: str = "",
    sampai: str = "",
    message: str = "",
    success: bool = False,
):
    # Load laporan & items
    if upload_id:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM petty_cash_laporan WHERE upload_id = ?", (upload_id,)
        ).fetchone()
        conn.close()
        laporan = dict(row) if row else None
        all_items = get_petty_cash_items(upload_id)
    else:
        laporan = None
        all_items = []
        # Jika ada laporan, gunakan yang terbaru
        laporans = get_petty_cash_laporans()
        if laporans:
            laporan = dict(laporans[0])
            all_items = get_petty_cash_items(laporan["upload_id"])
        elif user and (is_admin(user) or can_member_upload(user)):
            # Tampilkan semua item petty cash jika belum ada laporan
            conn = get_db()
            rows = conn.execute("""
                SELECT * FROM petty_cash_items
                ORDER BY id ASC
            """).fetchall()
            conn.close()
            all_items = [dict(r) for r in rows]

    tanggal_options = sorted(
        {i.get("tanggal") for i in all_items if i.get("tanggal")},
        reverse=True,
    )
    tanggal_min = tanggal_options[-1] if tanggal_options else ""
    tanggal_max = tanggal_options[0] if tanggal_options else ""
    has_filters = bool(search.strip() or tanggal or jenis.strip())
    pc_items = filter_petty_cash_items(all_items, search, tanggal, jenis)
    pc_items = filter_items_by_date_range(pc_items, dari, sampai)

    total_pengeluaran = sum_petty_pengeluaran(pc_items)
    total_penerimaan = sum(int(i.get("debit") or 0) for i in pc_items)

    total_pengeluaran_all = sum_petty_pengeluaran(all_items)
    total_penerimaan_all = sum(int(i.get("debit") or 0) for i in all_items)
    is_reimbursement = laporan and (laporan.get("report_type") or "") == "reimbursement"
    if laporan and not has_filters and not is_reimbursement:
        if laporan.get("total_kredit"):
            total_pengeluaran = laporan.get("total_kredit")
        if laporan.get("total_debit"):
            total_penerimaan = laporan.get("total_debit")

    nota_count = sum(1 for i in all_items if i.get("nota_path"))

    # Ambil context dari Transfer BGN untuk saldo & anggaran
    dari_arg = dari.strip() or None
    sampai_arg = sampai.strip() or None
    bgn_ctx = get_transfer_bgn_context(dari=dari_arg, sampai=sampai_arg, user=user)

    return render_template(request, "petty_cash.html", {
        "user": user,
        "laporan": laporan,
        "items": pc_items,
        "all_items_count": len(all_items),
        "total_pengeluaran": total_pengeluaran,
        "total_penerimaan": total_penerimaan,
        "total_pengeluaran_all": total_pengeluaran_all or (laporan.get("total_kredit") if laporan else 0),
        "total_penerimaan_all": total_penerimaan_all or (laporan.get("total_debit") if laporan else 0),
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "selected_upload_id": upload_id or (laporan["upload_id"] if laporan else 0),
        "can_upload": is_admin(user) or can_member_upload(user),
        "can_edit": is_admin(user) or can_member_upload(user),
        "filters": {
            "search": search,
            "tanggal": tanggal,
            "jenis": jenis,
            "dari": dari_arg or "",
            "sampai": sampai_arg or "",
        },
        **build_keuangan_link_context(dari, sampai, module_key="petty_cash"),
        "tanggal_options": tanggal_options,
        "tanggal_min": tanggal_min,
        "tanggal_max": tanggal_max,
        "has_filters": has_filters,
        "is_reimbursement": is_reimbursement,
        "nota_count": nota_count,
        "message": message,
        "success": success,
        # Saldo & anggaran dari Transfer BGN
        "anggaran_global": bgn_ctx["anggaran_global"],
        "total_masuk": bgn_ctx["total_masuk"],
        "total_masuk_all": bgn_ctx["total_masuk_all"],
        "total_keluar": bgn_ctx["total_keluar"],
        "total_keluar_all": bgn_ctx["total_keluar_all"],
        "saldo": bgn_ctx["saldo"],
        "saldo_all": bgn_ctx["saldo_all"],
        "bgn_count": bgn_ctx["bgn_count"],
        "bgn_count_all": bgn_ctx["bgn_count_all"],
        "expense_count": bgn_ctx["expense_count"],
        "expense_count_all": bgn_ctx["expense_count_all"],
        "pending_expense_total": bgn_ctx["pending_expense_total"],
        "pending_expense_count": bgn_ctx["pending_expense_count"],
        "expense_modules": bgn_ctx["expense_modules"],
        "period_filtered": bgn_ctx["period_filtered"],
        "period_label": bgn_ctx["period_label"],
        "bgn_saldo": get_bgn_saldo_snapshot(),
    })


@router.post("/petty-cash/upload")
async def petty_cash_upload(
    request: Request,
    user=Depends(require_login),
    file: UploadFile = File(...),
    periode: str = Form(""),
):
    if is_viewer(user):
        return redirect_with_flash(
            request,
            "/petty-cash",
            "Akses ditolak. Akun Anda hanya dapat melihat data.",
        )
    if not is_admin(user) and not can_member_upload(user):
        return redirect_with_flash(
            request,
            "/petty-cash",
            "Akses ditolak. Anda tidak dapat mengunggah file.",
        )
    safe_name = f"{date.today().isoformat()}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    conn = get_db()
    conn.execute("""
        INSERT INTO uploads (filename, periode, created_by)
        VALUES (?, ?, ?)
    """, (file.filename, periode or None, user["id"]))
    upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        parsed = parse_petty_cash_pdf(file_path, upload_id, file.filename)
    except Exception as e:
        conn.close()
        return redirect_with_flash(request, "/petty-cash", f"Error parsing file: {str(e)}")

    item_list = parsed.get("items", []) if isinstance(parsed, dict) else []

    if not item_list:
        conn.close()
        return redirect_with_flash(request, "/petty-cash", "Tidak ada data yang bisa dibaca dari file")

    inserted = 0
    for item in item_list:
        pengajuan = item.get("pengajuan") or item.get("deskripsi") or ""
        if not pengajuan:
            continue
        try:
            debit_val = int(item.get("debit") or 0)
            kredit_val = int(item.get("kredit") or 0)
            jumlah = int(item.get("jumlah") or 0)
        except Exception:
            debit_val = kredit_val = jumlah = 0
        if not jumlah:
            jumlah = kredit_val if kredit_val > 0 else debit_val
        if jumlah <= 0 and debit_val <= 0 and kredit_val <= 0:
            continue

        no = str(item.get("no") or "").strip() or None
        tanggal = str(item.get("tanggal") or "").strip() or None
        nota_path = item.get("nota_path")
        saldo_akhir = item.get("saldo_akhir")
        tipe_transaksi = item.get("tipe_transaksi") or item.get("tipe")

        dup = conn.execute("""
            SELECT 1 FROM petty_cash_items
            WHERE upload_id = ? AND COALESCE(no,'') = COALESCE(?, '') AND pengajuan = ?
            LIMIT 1
        """, (upload_id, no, pengajuan)).fetchone()
        if dup:
            continue

        conn.execute("""
            INSERT INTO petty_cash_items
            (upload_id, no, pengajuan, jumlah, debit, kredit, saldo_akhir, tipe_transaksi, tanggal, nota_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            upload_id, no, pengajuan, jumlah, debit_val, kredit_val,
            saldo_akhir, tipe_transaksi, tanggal, nota_path, "DIAJUKAN",
        ))
        inserted += 1

    conn.execute("UPDATE uploads SET record_count = ? WHERE id = ?", (inserted, upload_id))
    conn.commit()
    conn.close()

    msg = f"Berhasil mengunggah {inserted} transaksi"
    return redirect_with_flash(request, f"/petty-cash?upload_id={upload_id}", msg, success=True)


@router.post("/petty-cash/laporan/save")
async def petty_cash_save_laporan(
    request: Request,
    user=Depends(require_login),
    upload_id: int = Form(...),
    nama_karyawan: str = Form(""),
    divisi: str = Form(""),
    saldo_awal: int = Form(0),
    total_digantikan: int = Form(0),
    payment_info: str = Form(""),
    bank: str = Form(""),
    nomor_rekening: str = Form(""),
    atas_nama: str = Form(""),
    yang_menyetujui: str = Form(""),
    periode: str = Form(""),
):
    """Simpan/update header meta laporan petty cash."""
    if is_viewer(user):
        return redirect_with_flash(request, f"/petty-cash?upload_id={upload_id}", "Akses ditolak.")

    conn = get_db()
    sisa_dana = saldo_awal - total_digantikan

    conn.execute("""
        INSERT OR REPLACE INTO petty_cash_laporan
        (upload_id, nama_karyawan, divisi, saldo_awal, sisa_dana, total_digantikan,
         payment_info, bank, nomor_rekening, atas_nama, yang_menyetujui, periode,
         total_kredit, total_debit, saldo_akhir, report_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        upload_id, nama_karyawan, divisi, saldo_awal, sisa_dana, total_digantikan,
        payment_info, bank, nomor_rekening, atas_nama, yang_menyetujui, periode,
        total_digantikan, 0, sisa_dana, "reimbursement",
    ))
    conn.commit()
    conn.close()
    return redirect_with_flash(request, f"/petty-cash?upload_id={upload_id}", "Header berhasil disimpan", success=True)


@router.post("/petty-cash/{upload_id}/hapus-semua")
async def petty_cash_hapus_semua(upload_id: int, request: Request, user=Depends(require_login)):
    """Hapus semua transaksi dalam upload ini, termasuk laporan."""
    if is_viewer(user):
        return redirect_with_flash(request, "/petty-cash", "Akses ditolak.")

    conn = get_db()
    rows = conn.execute("SELECT nota_path FROM petty_cash_items WHERE upload_id = ?", (upload_id,)).fetchall()
    for row in rows:
        if row[0]:
            _delete_nota_file_local(row[0])

    conn.execute("DELETE FROM petty_cash_items WHERE upload_id = ?", (upload_id,))
    conn.execute("DELETE FROM petty_cash_laporan WHERE upload_id = ?", (upload_id,))
    conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    conn.commit()
    conn.close()
    return redirect_with_flash(request, "/petty-cash", "Semua data berhasil dihapus", success=True)


def _delete_nota_file_local(nota_path: str):
    """Hapus file nota dari disk."""
    nota_full = os.path.join(UPLOAD_DIR, nota_path)
    if os.path.exists(nota_full):
        try:
            os.remove(nota_full)
        except OSError:
            pass
