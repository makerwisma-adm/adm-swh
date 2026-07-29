#!/usr/bin/env python3
"""Generate PDF: Alur Proses SPPG Keuangan."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "Alur-Proses-SPPG-Keuangan.pdf"

NAVY = colors.HexColor("#071e49")
GOLD = colors.HexColor("#c9a558")
SKY = colors.HexColor("#e0f2fe")
GREEN_BG = colors.HexColor("#f0fdf4")
GREEN_BORDER = colors.HexColor("#86efac")
AMBER = colors.HexColor("#fef3c7")
RED_BG = colors.HexColor("#fef2f2")
SLATE = colors.HexColor("#64748b")
WHITE = colors.white


def box_style(bg, border, text_color=NAVY):
    return [
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 1, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 0), (-1, -1), text_color),
    ]


def arrow_cell(text="→"):
    return Paragraph(f'<font color="#94a3b8"><b>{text}</b></font>', styles["small"])


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleMain", fontSize=22, leading=26, textColor=NAVY, alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Subtitle", fontSize=11, leading=14, textColor=SLATE, alignment=TA_CENTER, spaceAfter=20))
styles.add(ParagraphStyle(name="H1", fontSize=14, leading=18, textColor=NAVY, spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="H2", fontSize=11, leading=14, textColor=NAVY, spaceBefore=10, spaceAfter=6, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Body", fontSize=9.5, leading=13, textColor=colors.HexColor("#334155"), spaceAfter=6))
styles.add(ParagraphStyle(name="Note", fontSize=8.5, leading=11, textColor=SLATE, spaceAfter=4, leftIndent=4))
styles.add(ParagraphStyle(name="BoxText", fontSize=8.5, leading=11, textColor=NAVY, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="BoxTextWhite", fontSize=8.5, leading=11, textColor=WHITE, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="small", fontSize=10, leading=12, alignment=TA_CENTER))


def cell(text, style="BoxText", bold=False):
    t = f"<b>{text}</b>" if bold else text
    return Paragraph(t.replace("\n", "<br/>"), styles[style])


def build_cover():
    return [
        Spacer(1, 2.5 * cm),
        Paragraph("Alur Proses &amp; Pola Kerja", styles["TitleMain"]),
        Paragraph("Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun", styles["Subtitle"]),
        Spacer(1, 0.4 * cm),
        Table(
            [[Paragraph("<b>Dokumen referensi alur operasional</b><br/>Maker-Checker · Saldo BGN · Modul Keuangan", styles["Body"])]],
            colWidths=[14 * cm],
            style=[("BACKGROUND", (0, 0), (-1, -1), SKY), ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#bae6fd")), ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14), ("ALIGN", (0, 0), (-1, -1), "CENTER")],
        ),
        Spacer(1, 1.2 * cm),
        Paragraph("Isi dokumen:", styles["H2"]),
        Paragraph("1. Alur keuangan besar (uang masuk ↔ pengeluaran ↔ saldo)", styles["Body"]),
        Paragraph("2. Alur persetujuan maker-checker (status transaksi)", styles["Body"]),
        Paragraph("3. Alur per peran: Akuntan, KA SPPG, Maker", styles["Body"]),
        Paragraph("4. Contoh alur satu transaksi (sequence)", styles["Body"]),
        Paragraph("5. Peta modul aplikasi", styles["Body"]),
        Paragraph("6. Ringkasan tabel status &amp; dampak saldo", styles["Body"]),
        PageBreak(),
    ]


def build_section1():
    items = [
        Paragraph("1. Alur Keuangan Besar", styles["H1"]),
        Paragraph(
            "Transfer BGN mencatat dana masuk. Modul pengeluaran mengurangi saldo hanya setelah status <b>LUNAS</b>. "
            "Laporan Keuangan merangkum semua modul.",
            styles["Body"],
        ),
        Spacer(1, 4),
        Table(
            [
                [cell("Transfer BGN\n(uang masuk)", "BoxText", True), arrow_cell(), cell("Modul Pengeluaran\n(9 modul + petty cash)", "BoxText", True), arrow_cell(), cell("Laporan Keuangan\n(ringkasan)", "BoxText", True), arrow_cell("="), cell("Saldo BGN\nMasuk − Keluar LUNAS", "BoxTextWhite", True)],
            ],
            colWidths=[3.2 * cm, 0.6 * cm, 3.8 * cm, 0.6 * cm, 3.2 * cm, 0.6 * cm, 3.6 * cm],
            style=box_style(GREEN_BG, GREEN_BORDER) + [
                ("BACKGROUND", (6, 0), (6, 0), NAVY),
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#dcfce7")),
                ("BACKGROUND", (2, 0), (2, 0), colors.white),
                ("BACKGROUND", (4, 0), (4, 0), colors.white),
            ],
        ),
        Spacer(1, 8),
        Paragraph("Modul pengeluaran (workflow persetujuan KA):", styles["H2"]),
        Table(
            [[
                cell("Tagihan"),
                cell("Gaji Relawan"),
                cell("Gaji Staff"),
                cell("Insentif PIC"),
                cell("Insentif Mitra"),
            ], [
                cell("Sewa Kendaraan"),
                cell("Pengembalian Dana"),
                cell("Pengajuan Dana Mitra"),
                cell("Pengeluaran Mitra"),
                cell("Petty Cash*"),
            ]],
            colWidths=[3.2 * cm] * 5,
            style=[
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ],
        ),
        Paragraph("* Petty Cash: tabel terpisah, tanpa workflow KA/Maker.", styles["Note"]),
        Spacer(1, 6),
        Table(
            [[Paragraph("<b>Aturan saldo:</b> DIAJUKAN &amp; DISETUJUI = komitmen (belum kurangi saldo). LUNAS = kas riil keluar (saldo berkurang).", styles["Note"])]],
            colWidths=[16 * cm],
            style=[("BACKGROUND", (0, 0), (-1, -1), AMBER), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fcd34d")), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)],
        ),
        PageBreak(),
    ]
    return items


def build_section2():
    rows = [
        [cell("DIAJUKAN", "BoxText", True), arrow_cell(), cell("DISETUJUI", "BoxTextWhite", True), arrow_cell(), cell("LUNAS", "BoxTextWhite", True)],
        [Paragraph("", styles["Body"]), Paragraph("", styles["Body"]), Paragraph('<font color="#64748b" size="8">Akuntan ajukan</font>', styles["small"]), Paragraph("", styles["Body"]), Paragraph('<font color="#64748b" size="8">KA setujui</font>', styles["small"]), Paragraph("", styles["Body"]), Paragraph('<font color="#64748b" size="8">Maker bayar VA</font>', styles["small"])],
    ]
    branch = Table(
        [
            [cell("DIAJUKAN", "BoxText", True)],
            [arrow_cell("↓")],
            [cell("DITOLAK\n(wajib alasan)", "BoxText", True)],
            [arrow_cell("↺")],
            [cell("Perbaiki &amp;\najukan ulang", "BoxText")],
        ],
        colWidths=[3.5 * cm],
        style=box_style(RED_BG, colors.HexColor("#fecaca")),
    )

    main = Table(
        rows,
        colWidths=[2.8 * cm, 0.5 * cm, 2.8 * cm, 0.5 * cm, 2.8 * cm],
        style=[
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#fef3c7")),
            ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#0ea5e9")),
            ("BACKGROUND", (4, 0), (4, 0), colors.HexColor("#059669")),
            ("TEXTCOLOR", (2, 0), (2, 0), WHITE),
            ("TEXTCOLOR", (4, 0), (4, 0), WHITE),
            ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#fcd34d")),
            ("BOX", (2, 0), (2, 0), 1, colors.HexColor("#0284c7")),
            ("BOX", (4, 0), (4, 0), 1, colors.HexColor("#047857")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("SPAN", (0, 1), (0, 1)),
        ],
    )

    audit = Table(
        [
            ["Status", "Siapa", "Audit trail", "Dampak saldo BGN"],
            ["DIAJUKAN", "Akuntan", "created_at / input user", "Belum berkurang"],
            ["DISETUJUI", "KA SPPG", "approved_by, approved_at", "Belum berkurang"],
            ["DITOLAK", "KA SPPG", "rejected_by, rejection_note", "Tidak berkurang"],
            ["LUNAS", "Maker", "paid_by, paid_at + notif KA", "Berkurang"],
        ],
        colWidths=[2.5 * cm, 2.2 * cm, 5.5 * cm, 3.5 * cm],
        style=[
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ],
    )

    layout = Table([[main, Spacer(0.8 * cm, 1), branch]], colWidths=[9.5 * cm, 0.8 * cm, 3.8 * cm])
    return [
        Paragraph("2. Alur Persetujuan (Maker-Checker)", styles["H1"]),
        Paragraph("Berlaku untuk 9 modul di APPROVAL_KATEGORI. Status terpusat di modul approval.py.", styles["Body"]),
        Spacer(1, 6),
        layout,
        Spacer(1, 10),
        Paragraph("Detail status &amp; audit:", styles["H2"]),
        audit,
        PageBreak(),
    ]


def build_section3():
    def role_block(title, color, steps):
        return Table(
            [[Paragraph(f"<b>{title}</b>", ParagraphStyle(name=title, parent=styles["BoxTextWhite"], fontSize=9, textColor=WHITE))]] +
            [[Paragraph(f"• {s}", styles["Note"])] for s in steps],
            colWidths=[5 * cm],
            style=[
                ("BACKGROUND", (0, 0), (0, 0), color),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, color),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 1), (-1, -1), 8),
            ],
        )

    blocks = Table(
        [[
            role_block("Akuntan / Member", colors.HexColor("#0c4a6e"), [
                "Input data di modul laporan",
                "Upload lampiran / nota",
                "Set status → DIAJUKAN",
                "Jika ditolak: perbaiki & ajukan ulang",
            ]),
            role_block("KA SPPG", colors.HexColor("#1e3a5f"), [
                "Dashboard KA: review DIAJUKAN",
                "Setujui → DISETUJUI",
                "Tolak → DITOLAK + alasan",
                "Terima notifikasi saat LUNAS",
            ]),
            role_block("Maker Pembayaran", colors.HexColor("#166534"), [
                "Dashboard Bayar: lihat DISETUJUI",
                "Transfer via VA ke rekening",
                "Tandai → LUNAS",
                "Hanya aksi dari dashboard bayar",
            ]),
        ]],
        colWidths=[5.2 * cm, 5.2 * cm, 5.2 * cm],
        style=[("VALIGN", (0, 0), (-1, -1), "TOP")],
    )

    guard = Table(
        [[Paragraph("<b>Pembatasan HTTP (middleware):</b> KA hanya tulis dari /dashboard-ka · Maker hanya dari /dashboard-bayar · Viewer/Mitra read-only", styles["Note"])]],
        colWidths=[16 * cm],
        style=[("BACKGROUND", (0, 0), (-1, -1), SKY), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#7dd3fc")), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)],
    )

    flow = Table(
        [
            [cell("Akuntan\nDIAJUKAN"), arrow_cell(), cell("KA SPPG\nDISETUJUI"), arrow_cell(), cell("Maker\nLUNAS"), arrow_cell(), cell("Notifikasi\nke KA")],
        ],
        colWidths=[3 * cm, 0.6 * cm, 3 * cm, 0.6 * cm, 3 * cm, 0.6 * cm, 3 * cm],
        style=box_style(colors.white, colors.HexColor("#cbd5e1")),
    )

    return [
        Paragraph("3. Alur Per Peran", styles["H1"]),
        Paragraph("Pemisahan tugas (segregation of duty): tidak ada satu orang yang input, setujui, dan bayar sekaligus.", styles["Body"]),
        Spacer(1, 6),
        flow,
        Spacer(1, 10),
        blocks,
        Spacer(1, 8),
        guard,
        PageBreak(),
    ]


def build_section4():
    steps = [
        ("1", "Akuntan", "Buat record di modul (mis. Gaji Staff)", "status = DIAJUKAN · saldo belum berubah"),
        ("2", "KA SPPG", "Buka Dashboard KA, review antrian", "Setujui atau tolak dengan alasan"),
        ("3", "KA SPPG", "Jika setuju: DISETUJUI", "Tercatat approved_by & approved_at"),
        ("4", "Maker", "Buka Dashboard Pembayaran", "Lihat daftar DISETUJUI + info VA"),
        ("5", "Maker", "Transfer VA ke rekening tujuan", "Di luar sistem (bank/VA)"),
        ("6", "Maker", "Tandai LUNAS di dashboard", "paid_by, paid_at · saldo BGN berkurang"),
        ("7", "Sistem", "Kirim notifikasi ke KA", '"Pembayaran LUNAS — [modul]"'),
    ]
    data = [["#", "Aktor", "Aksi", "Catatan"]] + [[a, b, c, d] for a, b, c, d in steps]
    tbl = Table(data, colWidths=[0.8 * cm, 2.2 * cm, 5.5 * cm, 5.2 * cm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [
        Paragraph("4. Contoh Alur Satu Transaksi", styles["H1"]),
        Paragraph("Contoh: pengajuan Gaji Staff — pola sama untuk modul lain yang butuh persetujuan KA.", styles["Body"]),
        Spacer(1, 6),
        tbl,
        PageBreak(),
    ]


def build_section5():
    top = Table(
        [
            [cell("Dashboard", "BoxText"), cell("Transfer BGN", "BoxText", True), cell("Laporan Keuangan", "BoxText")],
        ],
        colWidths=[4.8 * cm, 4.8 * cm, 4.8 * cm],
        style=box_style(SKY, colors.HexColor("#7dd3fc")),
    )
    mid = Table(
        [
            [cell("Dashboard KA SPPG", "BoxTextWhite", True), arrow_cell("⇄"), cell("Dashboard Pembayaran", "BoxTextWhite", True)],
            [Paragraph('<font size="7" color="#64748b">Review DIAJUKAN</font>', styles["small"]), Paragraph("", styles["Body"]), Paragraph('<font size="7" color="#64748b">Proses DISETUJUI → LUNAS</font>', styles["small"])],
        ],
        colWidths=[5.5 * cm, 1 * cm, 5.5 * cm],
        style=[
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#1e3a5f")),
            ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#166534")),
            ("TEXTCOLOR", (0, 0), (0, 0), WHITE),
            ("TEXTCOLOR", (2, 0), (2, 0), WHITE),
            ("BOX", (0, 0), (0, 0), 1, NAVY),
            ("BOX", (2, 0), (2, 0), 1, colors.HexColor("#166534")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ],
    )
    mods = Table(
        [[cell("Modul Pengeluaran (9 modul workflow KA)\nTagihan · Gaji · Insentif · Sewa · Mitra · Refund", "BoxText")]],
        colWidths=[14 * cm],
        style=box_style(colors.white, colors.HexColor("#cbd5e1")),
    )
    special = Table(
        [
            [cell("Petty Cash\n(tanpa workflow KA)"), cell("Portal Mitra\n(read-only mitra)"), cell("Setup\n(user & menu access)")],
        ],
        colWidths=[4.8 * cm, 4.8 * cm, 4.8 * cm],
        style=[
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ],
    )

    summary = Table(
        [
            ["Tahap", "Status", "Peran", "Dampak Saldo BGN"],
            ["Input", "DIAJUKAN", "Akuntan", "Belum berkurang"],
            ["Otorisasi", "DISETUJUI / DITOLAK", "KA SPPG", "Belum berkurang"],
            ["Bayar VA", "LUNAS", "Maker", "Berkurang"],
            ["Uang masuk", "Transfer BGN", "Admin / Akuntan", "Bertambah"],
        ],
        colWidths=[2.5 * cm, 3.5 * cm, 3 * cm, 4.5 * cm],
        style=[
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ],
    )

    return [
        Paragraph("5. Peta Modul Aplikasi", styles["H1"]),
        Paragraph("Struktur modul di aplikasi appweb-sppg — beranda, persetujuan, laporan, dan modul khusus.", styles["Body"]),
        Spacer(1, 6),
        Paragraph("Modul Beranda", styles["H2"]),
        top,
        Spacer(1, 8),
        Paragraph("Dashboard Persetujuan", styles["H2"]),
        mid,
        Spacer(1, 8),
        Paragraph("Modul Pengeluaran", styles["H2"]),
        mods,
        Spacer(1, 8),
        Paragraph("Modul Khusus", styles["H2"]),
        special,
        Spacer(1, 12),
        Paragraph("6. Ringkasan Cepat", styles["H1"]),
        summary,
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")),
        Paragraph("Dokumen ini dibuat otomatis dari pola proses aplikasi SPPG Keuangan (FastAPI + SQLite).", styles["Note"]),
    ]


def add_page_number(canv: canvas.Canvas, doc):
    canv.saveState()
    canv.setFont("Helvetica", 8)
    canv.setFillColor(SLATE)
    canv.drawString(2 * cm, 1.2 * cm, "SPPG Wisma Haji Madiun — Alur Proses Keuangan")
    canv.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Halaman {canv.getPageNumber()}")
    canv.restoreState()


def main():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Alur Proses SPPG Keuangan",
        author="SPPG Wisma Haji Madiun",
    )
    story = []
    story.extend(build_cover())
    story.extend(build_section1())
    story.extend(build_section2())
    story.extend(build_section3())
    story.extend(build_section4())
    story.extend(build_section5())
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF created: {OUT}")


if __name__ == "__main__":
    main()