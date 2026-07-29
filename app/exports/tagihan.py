"""Tagihan PDF export."""
from datetime import date
from typing import Dict, List

from app.services.tagihan import enrich_tagihan_item
from app.utils.formatters import format_rupiah

def _build_tagihan_pdf(rows: List[Dict]) -> bytes:
    from fpdf import FPDF

    data = [enrich_tagihan_item(r) for r in rows]
    total_jumlah = sum(r["jumlah"] for r in data)
    total_charges = sum(r["charges"] for r in data)
    total_grand = total_jumlah + total_charges

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(7, 30, 73)
    pdf.cell(0, 8, "LAPORAN TAGIHAN - SPPG WISMA HAJI MADIUN", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Dicetak: {date.today().strftime('%d %B %Y')}  |  {len(data)} entri", ln=True, align="C")
    pdf.ln(4)

    col_widths = [22, 58, 24, 18, 24, 16, 14, 24, 24, 18]
    headers = ["NO", "KETERANGAN", "JUMLAH", "CHARGES", "TOTAL", "STATUS", "BANK", "NO. REK", "ATAS NAMA", "TANGGAL"]
    row_h = 7

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(7, 30, 73)
    pdf.set_text_color(255, 255, 255)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], row_h, header, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for item in data:
        if pdf.get_y() > 185:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_fill_color(7, 30, 73)
            pdf.set_text_color(255, 255, 255)
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], row_h, header, border=1, align="C", fill=True)
            pdf.ln()
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(30, 30, 30)

        keterangan = (item.get("pengajuan") or "")[:45]
        cells = [
            str(item.get("no") or "")[:18],
            keterangan,
            format_rupiah(item.get("jumlah") or 0).replace("Rp", "Rp "),
            format_rupiah(item.get("charges") or 0).replace("Rp", "Rp ") if item.get("charges") else "-",
            format_rupiah(item.get("total") or 0).replace("Rp", "Rp "),
            str(item.get("status") or "")[:10],
            str(item.get("bank") or "")[:12],
            str(item.get("nomor_rekening") or "")[:18],
            str(item.get("atas_nama") or "")[:24],
            str(item.get("tanggal") or "")[:10],
        ]
        aligns = ["L", "L", "R", "R", "R", "C", "L", "L", "L", "C"]
        if fill:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)
        for i, (text, align) in enumerate(zip(cells, aligns)):
            pdf.cell(col_widths[i], row_h, text, border=1, align=align, fill=True)
        pdf.ln()
        fill = not fill

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(236, 253, 245)
    pdf.set_text_color(7, 30, 73)
    pdf.cell(sum(col_widths[:2]), row_h, "TOTAL", border=1, align="R", fill=True)
    pdf.cell(col_widths[2], row_h, format_rupiah(total_jumlah).replace("Rp", "Rp "), border=1, align="R", fill=True)
    pdf.cell(col_widths[3], row_h, format_rupiah(total_charges).replace("Rp", "Rp "), border=1, align="R", fill=True)
    pdf.cell(col_widths[4], row_h, format_rupiah(total_grand).replace("Rp", "Rp "), border=1, align="R", fill=True)
    pdf.cell(sum(col_widths[5:]), row_h, "", border=1, fill=True)
    pdf.ln()

    return bytes(pdf.output())
