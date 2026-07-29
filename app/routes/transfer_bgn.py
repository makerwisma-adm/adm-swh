"""Transfer masuk dari BGN — integrasi dengan pengeluaran."""
import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.auth.session import is_viewer, render_template, require_login
from app.services.bgn_transfer import (
    bulk_delete_bgn_transfers,
    create_bgn_transfer,
    delete_bgn_transfer,
    update_bgn_transfer,
)
from app.services.finance_summary import get_transfer_bgn_context, get_transfer_bgn_laporan_context
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/transfer-bgn", response_class=HTMLResponse)
async def transfer_bgn_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    dari: str = "",
    sampai: str = "",
):
    return render_template(request, "transfer_bgn.html", {
        "user": user,
        **get_transfer_bgn_context(
            search=search,
            dari=dari or None,
            sampai=sampai or None,
            user=user,
        ),
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "transfer_bgn",
    })


@router.get("/transfer-bgn/laporan", response_class=HTMLResponse)
async def transfer_bgn_laporan_page(
    request: Request,
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
):
    return render_template(request, "laporan_transfer_bgn.html", {
        "user": user,
        **get_transfer_bgn_laporan_context(
            dari=dari or None,
            sampai=sampai or None,
            user=user,
        ),
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "transfer_bgn",
    })


@router.get("/export/transfer-bgn/csv")
async def export_transfer_bgn_csv(
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
):
    ctx = get_transfer_bgn_laporan_context(dari=dari or None, sampai=sampai or None, user=user)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([ctx["report_title"]])
    writer.writerow([ctx["report_subtitle"]])
    writer.writerow(["Periode", f"{ctx['dari_display']} — {ctx['sampai_display']}"])
    writer.writerow(["Dicetak", ctx["generated_at_display"]])
    writer.writerow([])

    ag = ctx.get("anggaran_global") or {}
    g = ag.get("global") or {}
    p = ag.get("period") or {}

    writer.writerow(["RINGKASAN DANA OPERASIONAL BGN"])
    writer.writerow(["Posisi", "Jumlah Transaksi", "Total (Rp)"])
    writer.writerow(["INPUT — Transfer Masuk BGN", ctx["bgn_count"], ctx["total_masuk"]])
    writer.writerow(["OUTPUT — Pengeluaran LUNAS", ctx["expense_count"], ctx["total_keluar"]])
    writer.writerow(["SALDO (Input − Output)", "", ctx["saldo"]])
    writer.writerow([])

    writer.writerow(["LAPORAN PENGGUNAAN ANGGARAN — GLOBAL (KUMULATIF)"])
    writer.writerow(["Posisi", "Nilai (Rp)", "Keterangan"])
    writer.writerow(["Total Dana Masuk BGN", g.get("total_masuk", 0), "Semua transfer masuk"])
    writer.writerow(["Sudah Terpakai (LUNAS)", g.get("total_keluar", 0), "Mengurangi saldo kas"])
    writer.writerow(["Sisa Anggaran", g.get("saldo", 0), "Masuk − LUNAS"])
    writer.writerow(["Menunggu (DIAJUKAN/DISETUJUI)", g.get("pending_total", 0), f"{g.get('pending_count', 0)} transaksi"])
    writer.writerow(["Komitmen (LUNAS + Menunggu)", g.get("committed_total", 0), ""])
    writer.writerow(["Sisa Setelah Komitmen", g.get("sisa_setelah_komitmen", 0), ""])
    writer.writerow(["Tingkat Pemakaian", f"{g.get('utilization_pct', 0)}%", "LUNAS / Masuk"])
    writer.writerow(["Proyeksi Pemakaian", f"{g.get('projected_utilization_pct', 0)}%", "Jika semua menunggu dibayar"])
    writer.writerow([])

    if ag.get("period_filtered"):
        writer.writerow(["RINGKASAN PERIODE AKTIF"])
        writer.writerow(["Masuk periode", p.get("total_masuk", 0)])
        writer.writerow(["Keluar LUNAS periode", p.get("total_keluar", 0)])
        writer.writerow(["Saldo periode", p.get("saldo", 0)])
        writer.writerow(["Pemakaian periode", f"{p.get('utilization_pct', 0)}%"])
        writer.writerow([])

    writer.writerow(["PEMAKAIAN ANGGARAN PER MODUL"])
    writer.writerow(["Modul", "Transaksi", "Total LUNAS (Rp)", "% dari Anggaran", "% dari Keluar"])
    for mod in ag.get("modules") or []:
        writer.writerow([
            mod.get("label", ""),
            mod.get("count", 0),
            mod.get("total", 0),
            mod.get("pct_budget", 0),
            mod.get("pct_spent", 0),
        ])
    writer.writerow([])

    writer.writerow(["PIPELINE STATUS PENGAJUAN (GLOBAL)"])
    writer.writerow(["Status", "Transaksi", "Total (Rp)"])
    for st in ag.get("status_global") or []:
        writer.writerow([st.get("label", st.get("key", "")), st.get("count", 0), st.get("total", 0)])
    writer.writerow([])

    writer.writerow(["INPUT — Daftar Transfer BGN"])
    writer.writerow(["Tanggal", "Keterangan", "No. Referensi", "Periode", "Jumlah (Rp)"])
    for item in ctx["items"]:
        writer.writerow([
            item.get("tanggal") or "",
            item.get("keterangan") or "",
            item.get("no_referensi") or "",
            item.get("periode") or "",
            item.get("jumlah") or 0,
        ])
    writer.writerow([])

    writer.writerow(["OUTPUT — Pengeluaran per Modul Operasional"])
    writer.writerow(["Modul", "Transaksi", "Total (Rp)", "Persen (%)"])
    for mod in ctx["expense_modules"]:
        writer.writerow([mod["label"], mod["count"], mod["total"], mod.get("pct", 0)])
    writer.writerow(["Total Dibayarkan", ctx["expense_count"], ctx["total_keluar"], 100 if ctx["total_keluar"] else 0])
    writer.writerow([])

    writer.writerow(["ALUR PER BULAN"])
    writer.writerow(["Bulan", "Masuk BGN (Rp)", "Keluar Operasional (Rp)", "Saldo Bulan (Rp)"])
    for m in ctx["monthly_flow"]:
        writer.writerow([m["label"], m["masuk"], m["keluar"], m["saldo"]])

    filename = f"laporan_transfer_bgn_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/transfer-bgn")
async def create_transfer_bgn(
    user=Depends(require_login),
    tanggal: str = Form(...),
    keterangan: str = Form(...),
    jumlah: int = Form(...),
    no_referensi: str = Form(""),
    periode: str = Form(""),
):
    if is_viewer(user):
        return RedirectResponse("/transfer-bgn", status_code=303)
    create_bgn_transfer(
        tanggal=tanggal,
        keterangan=keterangan,
        jumlah=jumlah,
        no_referensi=no_referensi,
        periode=periode,
        created_by=user["id"],
    )
    return RedirectResponse("/transfer-bgn", status_code=303)


@router.post("/transfer-bgn/{item_id}/update")
async def update_transfer_bgn_item(
    item_id: int,
    user=Depends(require_login),
    tanggal: str = Form(...),
    keterangan: str = Form(...),
    jumlah: int = Form(...),
    no_referensi: str = Form(""),
    periode: str = Form(""),
):
    if is_viewer(user):
        return RedirectResponse("/transfer-bgn", status_code=303)
    update_bgn_transfer(item_id, tanggal, keterangan, jumlah, no_referensi, periode)
    return RedirectResponse("/transfer-bgn", status_code=303)


@router.post("/transfer-bgn/{item_id}/delete")
async def delete_transfer_bgn_item(item_id: int, user=Depends(require_login)):
    if is_viewer(user):
        return RedirectResponse("/transfer-bgn", status_code=303)
    delete_bgn_transfer(item_id)
    return RedirectResponse("/transfer-bgn", status_code=303)


@router.post("/api/transfer-bgn/bulk-delete")
async def api_transfer_bgn_bulk_delete(request: Request, user=Depends(require_login)):
    if is_viewer(user):
        return JSONResponse({"error": "Akses ditolak"}, status_code=403)
    try:
        data = await request.json()
        ids = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "no valid ids"}, status_code=400)
        deleted = bulk_delete_bgn_transfers(ids)
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)