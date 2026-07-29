"""Gaji relawan PDF export."""
from datetime import date
from typing import Any, Dict, List

from app.constants import FEE_PAYROL_PER_ORANG
from app.services.transfer_reports import (
    _nama_from_gaji_item,
    build_pic_transfer_export_rows,
    calc_fee_payrol,
    resolve_gaji_relawan_export,
)
from app.utils.formatters import format_rupiah, format_tanggal_pengajuan

def _pdf_sanitize_text(text) -> str:
    if text is None:
        return ""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _pdf_fit_cell(pdf, text, width_mm: float) -> str:
    text = _pdf_sanitize_text(text)
    if not text:
        return ""
    usable = max(width_mm - 2, 4)
    if pdf.get_string_width(text) <= usable:
        return text
    ell = "..."
    trimmed = text
    while trimmed and pdf.get_string_width(trimmed + ell) > usable:
        trimmed = trimmed[:-1]
    return (trimmed + ell) if trimmed else ell


def _gaji_relawan_pdf_status(_status: str = "") -> str:
    """Label status di PDF rincian transaksi — selalu Sukses."""
    return "Sukses"


def _enrich_gaji_relawan_export_items(laporan: Dict, items: List[Dict]) -> List[Dict]:
    periode_label = laporan.get("periode") or laporan.get("filename") or "—"
    enriched = []
    for item in items:
        row = dict(item)
        row["periode_label"] = periode_label
        row["fee_payrol"] = FEE_PAYROL_PER_ORANG
        row["total_bayar"] = int(row.get("jumlah") or 0) + FEE_PAYROL_PER_ORANG
        enriched.append(row)
    return enriched


def _build_gaji_relawan_pdf(laporan: Dict, items: List[Dict]) -> bytes:
    """PDF rincian transaksi gaji relawan — ringkasan + tabel sama dengan halaman web."""
    from fpdf import FPDF

    items = _enrich_gaji_relawan_export_items(laporan, items)
    periode_label = laporan.get("periode") or laporan.get("filename") or "—"
    total_gaji = sum(int(i.get("jumlah") or 0) for i in items)
    total_fee = calc_fee_payrol(len(items))
    total_grand = total_gaji + total_fee

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    page_bottom = pdf.h - pdf.b_margin
    table_width = 277
    col_widths = [10, 58, 28, 36, 22, 32, 28, 32, 31]
    headers = ["NO", "NAMA RELAWAN", "PERIODE", "REK. TUJUAN", "BANK", "JUMLAH GAJI", "FEE PAYROL", "TOTAL", "STATUS"]
    row_h = 7
    header_h = 8

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(7, 30, 73)
    pdf.cell(0, 9, "LAPORAN GAJI RELAWAN - SPPG WISMA HAJI MADIUN", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    subtitle = f"Periode: {periode_label}  |  Dicetak: {date.today().strftime('%d %B %Y')}"
    if laporan.get("tanggal_pembayaran"):
        subtitle += f"  |  Tanggal bayar: {laporan['tanggal_pembayaran']}"
    pdf.cell(0, 6, _pdf_sanitize_text(subtitle), ln=True, align="C")
    pdf.ln(3)

    kpi_w = table_width / 4
    kpi_h = 18
    kpi_data = [
        ("JUMLAH PENERIMA", str(len(items)), "relawan / transaksi"),
        ("JUMLAH GAJI", format_rupiah(total_gaji), "total gaji relawan"),
        ("JUMLAH FEE PAYROL", format_rupiah(total_fee), f"{len(items)} x {format_rupiah(FEE_PAYROL_PER_ORANG)}"),
        ("GRAND TOTAL", format_rupiah(total_grand), "gaji + fee payrol"),
    ]
    kpi_y = pdf.get_y()
    for col_idx, (label, value, note) in enumerate(kpi_data):
        x0 = pdf.l_margin + col_idx * kpi_w
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(x0, kpi_y, kpi_w, kpi_h, style="DF")
        pdf.set_xy(x0 + 3, kpi_y + 2)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(7, 30, 73)
        pdf.cell(kpi_w - 6, 4, label, ln=0)
        pdf.set_xy(x0 + 3, kpi_y + 6)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(kpi_w - 6, 6, _pdf_fit_cell(pdf, value, kpi_w - 6), ln=0)
        pdf.set_xy(x0 + 3, kpi_y + 12)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(kpi_w - 6, 4, _pdf_fit_cell(pdf, note, kpi_w - 6), ln=0)
    pdf.set_xy(pdf.l_margin, kpi_y + kpi_h + 4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(7, 30, 73)
    pdf.cell(0, 7, "Rincian Transaksi", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"{len(items)} baris pembayaran", ln=True)
    pdf.ln(2)

    def _draw_table_header():
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(7, 30, 73)
        pdf.set_text_color(255, 255, 255)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], header_h, header, border=1, align="C", ln=0, fill=True)
        pdf.ln(header_h)

    def _ensure_row_space(height: float):
        if pdf.get_y() + height > page_bottom:
            pdf.add_page()
            _draw_table_header()
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(30, 30, 30)

    def _draw_data_row(cells: List[str], aligns: List[str], fill: bool):
        _ensure_row_space(row_h)
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        for i, (text, align) in enumerate(zip(cells, aligns)):
            pdf.cell(
                col_widths[i],
                row_h,
                _pdf_fit_cell(pdf, text, col_widths[i]),
                border=1,
                align=align,
                ln=0,
                fill=True,
            )
        pdf.ln(row_h)

    _draw_table_header()
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for idx, item in enumerate(items, start=1):
        cells = [
            str(item.get("no") or idx),
            _nama_from_gaji_item(item),
            item.get("periode_label") or periode_label,
            str(item.get("nomor_rekening") or ""),
            str(item.get("bank") or ""),
            format_rupiah(int(item.get("jumlah") or 0)),
            format_rupiah(int(item.get("fee_payrol") or FEE_PAYROL_PER_ORANG)),
            format_rupiah(int(item.get("total_bayar") or 0)),
            _gaji_relawan_pdf_status(item.get("status")),
        ]
        aligns = ["C", "L", "L", "L", "C", "R", "R", "R", "C"]
        _draw_data_row(cells, aligns, fill)
        fill = not fill

    _ensure_row_space(row_h + 2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(236, 253, 245)
    pdf.set_text_color(7, 30, 73)
    pdf.cell(sum(col_widths[:5]), row_h, "TOTAL", border=1, align="R", ln=0, fill=True)
    pdf.cell(col_widths[5], row_h, _pdf_fit_cell(pdf, format_rupiah(total_gaji), col_widths[5]), border=1, align="R", ln=0, fill=True)
    pdf.cell(col_widths[6], row_h, _pdf_fit_cell(pdf, format_rupiah(total_fee), col_widths[6]), border=1, align="R", ln=0, fill=True)
    pdf.cell(col_widths[7], row_h, _pdf_fit_cell(pdf, format_rupiah(total_grand), col_widths[7]), border=1, align="R", ln=0, fill=True)
    pdf.cell(col_widths[8], row_h, "", border=1, ln=0, fill=True)
    pdf.ln(row_h)

    return bytes(pdf.output())
