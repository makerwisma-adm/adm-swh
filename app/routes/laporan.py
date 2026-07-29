"""Laporan gabungan semua modul dengan filter rentang tanggal."""
import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app.auth.session import render_template, require_login
from app.services.lunas_laporan import can_export_lunas, get_lunas_laporan_context
from app.services.finance_summary import get_laporan_context, MODULE_REPORTS
from app.services.status_laporan import get_status_laporan_context
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/laporan", response_class=HTMLResponse)
async def laporan_page(
    request: Request,
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
):
    return render_template(request, "laporan.html", {
        "user": user,
        **get_laporan_context(dari=dari or None, sampai=sampai or None),
        "module_reports": MODULE_REPORTS,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "laporan",
    })


@router.get("/laporan/status", response_class=HTMLResponse)
async def laporan_status_page(
    request: Request,
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
    status: str = "",
    kategori: str = "",
    search: str = "",
):
    return render_template(request, "laporan_status.html", {
        "user": user,
        **get_status_laporan_context(
            dari=dari or None,
            sampai=sampai or None,
            status_filter=status,
            kategori_filter=kategori,
            search=search,
        ),
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "laporan",
    })


@router.get("/export/laporan/status/csv")
async def export_laporan_status_csv(
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
    status: str = "",
    kategori: str = "",
    search: str = "",
):
    ctx = get_status_laporan_context(
        dari=dari or None,
        sampai=sampai or None,
        status_filter=status,
        kategori_filter=kategori,
        search=search,
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([ctx["report_title"]])
    writer.writerow([ctx["report_subtitle"]])
    writer.writerow(["Periode", f"{ctx['dari_display']} — {ctx['sampai_display']}"])
    writer.writerow(["Dicetak", ctx["generated_at_display"]])
    writer.writerow([])

    writer.writerow(["RINGKASAN STATUS"])
    writer.writerow(["Status", "Transaksi", "Total (Rp)", "Persen (%)"])
    for row in ctx["status_summary"]:
        writer.writerow([row["key"], row["count"], row["total"], row["pct"]])
    writer.writerow(["TOTAL", ctx["grand_count"], ctx["grand_total"], 100 if ctx["grand_total"] else 0])
    writer.writerow([])

    writer.writerow(["DAMPAK SALDO KAS"])
    writer.writerow(["Transfer BGN Masuk", ctx["bgn_count"], ctx["bgn_masuk"]])
    writer.writerow(["Pengeluaran Dibayarkan", ctx["dibayarkan_count"], ctx["dibayarkan_total"]])
    writer.writerow(["Menunggu (DIAJUKAN+DISETUJUI)", ctx["pending_count"], ctx["pending_total"]])
    writer.writerow(["Ditolak", ctx["ditolak_count"], ctx["ditolak_total"]])
    writer.writerow(["Saldo Kas (BGN − Dibayarkan)", "", ctx["saldo_kas"]])
    writer.writerow([])

    writer.writerow(["MATRIKS MODUL × STATUS"])
    header = ["Modul"] + [s for s in ctx["status_order"]] + ["Total"]
    writer.writerow(header)
    for mod in ctx["module_matrix"]:
        row = [mod["label"]]
        for st in ctx["status_order"]:
            row.append(mod["cells"].get(st, {}).get("total", 0))
        row.append(mod["row_total"])
        writer.writerow(row)
    writer.writerow([])

    writer.writerow(["RINCIAN TRANSAKSI"])
    writer.writerow([
        "Status", "Modul", "No", "Tanggal", "Keterangan", "Penerima",
        "Jumlah (Rp)", "Alasan Penolakan",
    ])
    for item in ctx["detail_items"]:
        writer.writerow([
            item.get("status_key") or item.get("status") or "",
            item.get("kategori_label") or "",
            item.get("no") or "",
            item.get("tanggal") or "",
            item.get("pengajuan") or "",
            item.get("atas_nama") or "",
            item.get("jumlah") or 0,
            item.get("rejection_note") or "",
        ])

    filename = f"laporan_status_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/laporan/csv")
async def export_laporan_csv(
    user=Depends(require_login),
    dari: str = "",
    sampai: str = "",
):
    ctx = get_laporan_context(dari=dari or None, sampai=sampai or None)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Laporan Keuangan SPPG — Ringkasan Modul"])
    writer.writerow(["Periode", f"{ctx['dari_display']} — {ctx['sampai_display']}"])
    writer.writerow([])
    writer.writerow(["Modul", "Jumlah Transaksi", "Total (Rp)"])
    for mod in ctx["modules"]:
        writer.writerow([mod["label"], mod["count"], mod["total"]])
    writer.writerow([])
    writer.writerow(["Total Pengeluaran", ctx["grand_count"], ctx["grand_total"]])
    writer.writerow(["Transfer BGN (masuk)", ctx["bgn_count"], ctx["bgn_masuk"]])
    writer.writerow(["Saldo (BGN - Pengeluaran)", "", ctx["saldo"]])
    writer.writerow([])
    writer.writerow(["Per Bulan", "Total (Rp)"])
    for m in ctx["monthly"]:
        writer.writerow([m["label"], m["total"]])

    filename = f"laporan_sppg_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/laporan/lunas/csv")
async def export_laporan_lunas_csv(
    user=Depends(require_login),
    scope: str = "",
    dari: str = "",
    sampai: str = "",
    kategori: str = "",
    search: str = "",
):
    if not can_export_lunas(user):
        raise HTTPException(status_code=403, detail="Akses export laporan LUNAS tidak diizinkan.")

    ctx = get_lunas_laporan_context(
        scope=scope,
        kategori=kategori,
        search=search,
        dari=dari or None,
        sampai=sampai or None,
        user=user,
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([ctx["report_title"]])
    writer.writerow([ctx["report_subtitle"]])
    writer.writerow(["Cakupan", ctx["scope_label"]])
    writer.writerow(["Periode dibayar", f"{ctx['dari_display']} — {ctx['sampai_display']}"])
    writer.writerow(["Modul", ctx["kategori_label"]])
    writer.writerow(["Dicetak", ctx["generated_at_display"]])
    writer.writerow([])
    writer.writerow(["RINGKASAN"])
    writer.writerow(["Total transaksi LUNAS", ctx["item_count"]])
    writer.writerow(["Total nilai (Rp)", ctx["item_total"]])
    writer.writerow([])

    writer.writerow([
        "No", "Modul", "Tanggal", "Keterangan", "Penerima",
        "Bank", "No. Rekening / VA", "Jumlah (Rp)",
        "Disetujui Oleh", "Tanggal Disetujui",
        "Dibayar Oleh", "Tanggal Dibayar", "Status",
    ])
    for item in ctx["items"]:
        writer.writerow([
            item.get("no") or "",
            item.get("kategori_label") or "",
            item.get("tanggal") or "",
            item.get("pengajuan") or "",
            item.get("atas_nama") or "",
            item.get("bank") or "",
            item.get("nomor_rekening") or "",
            int(item.get("jumlah") or 0),
            item.get("approved_by_name") or "",
            (item.get("approved_at") or "")[:10] if item.get("approved_at") else "",
            item.get("paid_by_name") or "",
            (item.get("paid_at") or "")[:10] if item.get("paid_at") else "",
            item.get("status") or "LUNAS",
        ])

    scope_suffix = ctx["scope"]
    filename = f"laporan_lunas_{scope_suffix}_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )