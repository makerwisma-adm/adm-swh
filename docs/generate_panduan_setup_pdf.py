#!/usr/bin/env python3
"""Generate PDF: Panduan Setup & Pengembangan SPPG Keuangan."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "Panduan-Setup-SPPG-Keuangan.pdf"

NAVY = colors.HexColor("#071e49")
GOLD = colors.HexColor("#c9a558")
SKY = colors.HexColor("#e0f2fe")
GREEN_BG = colors.HexColor("#f0fdf4")
AMBER = colors.HexColor("#fef3c7")
SLATE = colors.HexColor("#64748b")
CODE_BG = colors.HexColor("#f1f5f9")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleMain", fontSize=20, leading=24, textColor=NAVY, alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Subtitle", fontSize=10, leading=13, textColor=SLATE, alignment=TA_CENTER, spaceAfter=16))
styles.add(ParagraphStyle(name="H1", fontSize=13, leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=8, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="H2", fontSize=10.5, leading=14, textColor=NAVY, spaceBefore=8, spaceAfter=5, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Body", fontSize=9, leading=12.5, textColor=colors.HexColor("#334155"), spaceAfter=5))
styles.add(ParagraphStyle(name="Note", fontSize=8.5, leading=11, textColor=SLATE, spaceAfter=4))
styles.add(ParagraphStyle(name="CodeBlock", fontSize=8, leading=11, textColor=colors.HexColor("#1e293b"), fontName="Courier", backColor=CODE_BG, leftIndent=6, rightIndent=6))


def code_block(text: str):
    return Preformatted(text.strip(), styles["CodeBlock"])


def table_data(headers, rows, col_widths):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def callout(text, bg=AMBER, border=colors.HexColor("#fcd34d")):
    return Table(
        [[Paragraph(text, styles["Note"])]],
        colWidths=[16 * cm],
        style=[("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 0.5, border), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8)],
    )


def add_page_number(canv: canvas.Canvas, doc):
    canv.saveState()
    canv.setFont("Helvetica", 8)
    canv.setFillColor(SLATE)
    canv.drawString(2 * cm, 1.2 * cm, "Panduan Setup SPPG Keuangan — Internal")
    canv.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Halaman {canv.getPageNumber()}")
    canv.restoreState()


def build_story():
    s = []

    # Cover
    s += [
        Spacer(1, 2 * cm),
        Paragraph("Panduan Setup &amp; Pengembangan", styles["TitleMain"]),
        Paragraph("Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun", styles["Subtitle"]),
        Table(
            [[Paragraph("<b>Dokumen untuk tim developer</b><br/>Extract zip · Install · Jalankan · Struktur proyek · Troubleshooting", styles["Body"])]],
            colWidths=[14 * cm],
            style=[("BACKGROUND", (0, 0), (-1, -1), SKY), ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#7dd3fc")), ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14), ("ALIGN", (0, 0), (-1, -1), "CENTER")],
        ),
        Spacer(1, 1 * cm),
        Paragraph("<b>Stack teknologi:</b> Python 3 · FastAPI · SQLite · Jinja2 · Port <b>8001</b>", styles["Body"]),
        Paragraph("<b>File zip:</b> appweb-sppg-develop-YYYYMMDD.zip", styles["Body"]),
        PageBreak(),
    ]

    # 1. Prasyarat
    s += [
        Paragraph("1. Prasyarat Sistem", styles["H1"]),
        Paragraph("Pastikan komputer tim sudah memenuhi persyaratan berikut sebelum menjalankan aplikasi.", styles["Body"]),
        table_data(
            ["Komponen", "Versi / Keterangan"],
            [
                ["Python", "3.9 atau lebih baru (disarankan 3.10+)"],
                ["pip", "Sudah terpasang bersama Python"],
                ["Browser", "Chrome, Firefox, Safari, atau Edge terbaru"],
                ["OS", "macOS, Windows 10+, atau Linux"],
                ["Port", "8001 harus bebas (tidak dipakai aplikasi lain)"],
                ["Ruang disk", "Minimal ~50 MB (tanpa upload besar)"],
            ],
            [4 * cm, 12 * cm],
        ),
        Spacer(1, 6),
        Paragraph("Cek versi Python:", styles["H2"]),
        code_block("python3 --version\n# atau di Windows:\npython --version"),
        Spacer(1, 4),
        callout("<b>Catatan Windows:</b> Jika perintah <font name='Courier'>python3</font> tidak dikenali, gunakan <font name='Courier'>python</font> sebagai gantinya di semua langkah berikut."),
        PageBreak(),
    ]

    # 2. Extract zip
    s += [
        Paragraph("2. Extract File Zip Proyek", styles["H1"]),
        Paragraph("Salin file <b>appweb-sppg-develop-*.zip</b> ke komputer tim, lalu extract ke folder kerja.", styles["Body"]),
        Paragraph("macOS / Linux:", styles["H2"]),
        code_block("cd ~/Projects\nunzip ~/Downloads/appweb-sppg-develop-20260712.zip\nls appweb-sppg"),
        Paragraph("Windows (PowerShell):", styles["H2"]),
        code_block("cd $env:USERPROFILE\\Projects\nExpand-Archive -Path $env:USERPROFILE\\Downloads\\appweb-sppg-develop-20260712.zip -DestinationPath .\ncd appweb-sppg"),
        Spacer(1, 6),
        Paragraph("Isi folder setelah extract:", styles["H2"]),
        table_data(
            ["Folder / File", "Fungsi"],
            [
                ["app/", "Kode backend (routes, services, auth)"],
                ["templates/", "Halaman HTML (UI)"],
                ["static/", "CSS, JavaScript, gambar logo"],
                ["uploads/", "File upload & lampiran nota"],
                ["docs/", "Dokumentasi PDF & skrip generator"],
                ["sppg_keuangan.db", "Database SQLite (data existing)"],
                ["main.py", "Entry point aplikasi"],
                ["requirements.txt", "Daftar dependency Python"],
                ["start-local.sh", "Skrip cepat jalankan server (Mac/Linux)"],
                ["README.md", "Dokumentasi singkat"],
                [".git/", "Riwayat versi git"],
            ],
            [4.5 * cm, 11.5 * cm],
        ),
        Spacer(1, 6),
        callout(
            "<b>File yang TIDAK ikut dalam zip (sengaja dikecualikan):</b><br/>"
            "• <font name='Courier'>.secret_key</font> — dibuat otomatis saat pertama kali jalan<br/>"
            "• <font name='Courier'>.env.local</font> — konfigurasi lokal (buat sendiri jika perlu)",
            bg=colors.HexColor("#fef2f2"),
            border=colors.HexColor("#fecaca"),
        ),
        PageBreak(),
    ]

    # 3. Install
    s += [
        Paragraph("3. Install Dependencies", styles["H1"]),
        Paragraph("Jalankan sekali saja setelah extract. Masuk ke folder proyek terlebih dahulu.", styles["Body"]),
        Paragraph("macOS / Linux:", styles["H2"]),
        code_block("cd appweb-sppg\npython3 -m pip install -r requirements.txt"),
        Paragraph("Windows:", styles["H2"]),
        code_block("cd appweb-sppg\npython -m pip install -r requirements.txt"),
        Spacer(1, 6),
        Paragraph("Opsional — virtual environment (disarankan untuk tim dev):", styles["H2"]),
        code_block(
            "# Mac/Linux\npython3 -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\n\n"
            "# Windows\npython -m venv .venv\n.venv\\Scripts\\activate\npip install -r requirements.txt"
        ),
        Spacer(1, 6),
        Paragraph("Paket utama yang terinstall:", styles["H2"]),
        table_data(
            ["Paket", "Kegunaan"],
            [
                ["fastapi", "Framework web API"],
                ["uvicorn", "Server HTTP"],
                ["jinja2", "Template HTML"],
                ["openpyxl / xlsxwriter", "Export Excel"],
                ["pdfplumber / pypdf", "Baca & proses PDF upload"],
                ["passlib", "Hash password login"],
                ["slowapi", "Rate limiting"],
            ],
            [4 * cm, 12 * cm],
        ),
        PageBreak(),
    ]

    # 4. Menjalankan
    s += [
        Paragraph("4. Menjalankan Aplikasi", styles["H1"]),
        Paragraph("Pilih salah satu cara berikut. Server berjalan di port <b>8001</b>.", styles["Body"]),
        Paragraph("Cara A — Skrip otomatis (Mac/Linux):", styles["H2"]),
        code_block("cd appweb-sppg\nchmod +x start-local.sh   # sekali saja\n./start-local.sh"),
        Paragraph("Cara B — Python langsung:", styles["H2"]),
        code_block("cd appweb-sppg\npython3 main.py"),
        Paragraph("Cara C — Uvicorn manual:", styles["H2"]),
        code_block("cd appweb-sppg\npython3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"),
        Paragraph("Windows (tanpa bash):", styles["H2"]),
        code_block("cd appweb-sppg\npython main.py"),
        Spacer(1, 6),
        Paragraph("Jika berhasil, terminal menampilkan:", styles["H2"]),
        code_block(
            "SPPG Keuangan — local dev\n"
            "Lokal  → http://localhost:8001/masuk\n"
            "HP/LAN → http://192.168.x.x:8001/masuk"
        ),
        Spacer(1, 4),
        callout("<b>Biarkan terminal tetap terbuka</b> selama aplikasi digunakan. Tekan <b>Ctrl+C</b> untuk menghentikan server."),
        PageBreak(),
    ]

    # 5. Akses browser
    s += [
        Paragraph("5. Akses di Browser", styles["H1"]),
        table_data(
            ["Akses dari", "URL"],
            [
                ["Komputer yang sama", "http://localhost:8001/masuk"],
                ["HP / laptop lain (WiFi sama)", "http://&lt;IP-komputer&gt;:8001/masuk"],
                ["Dashboard admin", "http://localhost:8001/dashboard"],
                ["Dashboard KA SPPG", "http://localhost:8001/dashboard-ka"],
                ["Dashboard Pembayaran", "http://localhost:8001/dashboard-bayar"],
                ["Setup user & menu", "http://localhost:8001/setup"],
            ],
            [5 * cm, 11 * cm],
        ),
        Spacer(1, 8),
        Paragraph("Cara cek IP komputer:", styles["H2"]),
        code_block("# macOS\nipconfig getifaddr en0\n\n# Windows\nipconfig | findstr IPv4\n\n# Linux\nhostname -I"),
        PageBreak(),
    ]

    # 6. Login
    s += [
        Paragraph("6. Akun Login Default", styles["H1"]),
        Paragraph("Gunakan akun berikut untuk pengujian awal. <b>Ganti password</b> sebelum deploy production.", styles["Body"]),
        table_data(
            ["Username", "Password", "Role", "Akses utama"],
            [
                ["admin", "admin123", "Administrator", "Semua modul + Setup"],
                ["swhm", "A0312", "Administrator", "Admin cadangan"],
                ["ka_sppg", "ka123", "KA SPPG", "Dashboard KA — setujui/tolak"],
                ["maker", "maker123", "Maker Pembayaran", "Dashboard Bayar — tandai LUNAS"],
                ["icha", "sppg123", "Akuntan / Member", "Input & upload terbatas"],
            ],
            [2.5 * cm, 2.5 * cm, 3 * cm, 8 * cm],
        ),
        Spacer(1, 8),
        Paragraph("Alur kerja per role:", styles["H2"]),
        table_data(
            ["Role", "Langkah kerja"],
            [
                ["Akuntan", "Input data modul → status DIAJUKAN"],
                ["KA SPPG", "Review di Dashboard KA → DISETUJUI atau DITOLAK"],
                ["Maker", "Bayar VA → tandai LUNAS di Dashboard Pembayaran"],
                ["Admin", "Kelola user, menu access, override status"],
            ],
            [3.5 * cm, 12.5 * cm],
        ),
        Spacer(1, 6),
        callout("Lihat juga dokumen <b>Alur-Proses-SPPG-Keuangan.pdf</b> di folder docs/ untuk diagram alur lengkap."),
        PageBreak(),
    ]

    # 7. Struktur dev
    s += [
        Paragraph("7. Panduan Pengembangan", styles["H1"]),
        Paragraph("Struktur kode yang perlu dipahami tim developer:", styles["Body"]),
        table_data(
            ["Path", "Isi / Keterangan"],
            [
                ["app/routes/", "Endpoint HTTP per modul (tagihan, gaji, laporan, dll)"],
                ["app/services/", "Logika bisnis (approval, finance_summary, tagihan)"],
                ["app/auth/", "Session login, middleware role guard"],
                ["app/constants.py", "Role, status, daftar modul & menu"],
                ["app/database.py", "Skema DB & seed user awal"],
                ["app/exports/", "Export CSV / Excel / PDF"],
                ["templates/", "UI Jinja2 — edit tampilan di sini"],
                ["static/", "Asset frontend"],
            ],
            [4.5 * cm, 11.5 * cm],
        ),
        Spacer(1, 8),
        Paragraph("Workflow git (opsional):", styles["H2"]),
        code_block(
            "cd appweb-sppg\ngit status\ngit checkout -b fitur/nama-fitur\n"
            "# ... edit kode ...\ngit add .\ngit commit -m \"Deskripsi perubahan\"\n"
            "git push origin fitur/nama-fitur"
        ),
        Spacer(1, 6),
        Paragraph("Hot reload:", styles["H2"]),
        Paragraph("Mode <font name='Courier'>--reload</font> aktif secara default. Perubahan file Python otomatis me-restart server. Perubahan template HTML biasanya langsung terlihat setelah refresh browser.", styles["Body"]),
        PageBreak(),
    ]

    # 8. Troubleshooting
    s += [
        Paragraph("8. Troubleshooting", styles["H1"]),
        table_data(
            ["Masalah", "Solusi"],
            [
                ["python3: command not found", "Install Python 3 dari python.org. Windows: centang 'Add to PATH'"],
                ["ModuleNotFoundError: fastapi", "Jalankan: pip install -r requirements.txt"],
                ["Address already in use :8001", "Port 8001 dipakai app lain. Tutup atau ganti: PORT=8002 ./start-local.sh"],
                ["Permission denied start-local.sh", "Jalankan: chmod +x start-local.sh"],
                ["Halaman tidak bisa diakses dari HP", "Pastikan firewall izinkan port 8001; gunakan IP WiFi yang sama"],
                ["Login gagal", "Cek username/password; DB ada di sppg_keuangan.db"],
                ["Upload gagal", "Pastikan folder uploads/ ada & writable"],
                ["DB kosong / error", "Hapus sppg_keuangan.db lalu restart — DB dibuat ulang dengan seed default"],
            ],
            [5 * cm, 11 * cm],
        ),
        Spacer(1, 10),
        Paragraph("9. Keamanan & Production", styles["H1"]),
        table_data(
            ["Item", "Rekomendasi"],
            [
                ["Password default", "Ganti semua password via halaman Setup"],
                [".secret_key", "Jangan commit ke git; file dibuat otomatis per mesin"],
                ["Database", "Backup rutin: cp sppg_keuangan.db backup/"],
                ["Zip proyek", "Jangan bagikan ke pihak luar — berisi data keuangan internal"],
                ["Production", "Gunakan reverse proxy (nginx) + HTTPS; pertimbangkan PostgreSQL jika multi-user"],
            ],
            [4.5 * cm, 11.5 * cm],
        ),
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")),
        Paragraph("Ringkasan cepat: <b>extract zip → pip install -r requirements.txt → python3 main.py → buka localhost:8001/masuk</b>", styles["Note"]),
        Paragraph("Dokumen ini dibuat otomatis untuk tim pengembang SPPG Wisma Haji Madiun.", styles["Note"]),
    ]
    return s


def main():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Panduan Setup SPPG Keuangan",
        author="SPPG Wisma Haji Madiun",
    )
    doc.build(build_story(), onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF created: {OUT}")


if __name__ == "__main__":
    main()