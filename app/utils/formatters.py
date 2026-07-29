"""Formatting and parsing helpers."""
import re
from datetime import datetime
from typing import Optional

from dateutil import parser as date_parser

from app.constants import ID_MONTH_NAMES

def format_rupiah(amount: int) -> str:
    if amount is None:
        return "Rp0"
    if amount < 0:
        return "-Rp" + f"{abs(amount):,.0f}".replace(",", ".")
    return "Rp" + f"{amount:,.0f}".replace(",", ".")

ID_MONTH_NAMES = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def format_tanggal_display(tgl_str: str) -> str:
    """Format tanggal: Tanggal - Bulan(huruf) - Tahun(angka), contoh 11 - Juni - 2026."""
    if not tgl_str:
        return "—"
    raw = tgl_str.strip()
    iso = raw if len(raw) == 10 and raw[4] == "-" and raw[7] == "-" else _parse_id_date(raw)
    if not iso:
        return tgl_str
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        bulan = ID_MONTH_NAMES[dt.month] if 1 <= dt.month <= 12 else str(dt.month)
        return f"{dt.day} - {bulan} - {dt.year}"
    except Exception:
        return tgl_str


def format_tanggal_pengajuan(tgl_str: str) -> str:
    """Format seperti formulir PDF: 20 Mei 2026."""
    if not tgl_str:
        return "—"
    raw = tgl_str.strip()
    iso = raw if len(raw) == 10 and raw[4] == "-" and raw[7] == "-" else _parse_id_date(raw)
    if not iso:
        return tgl_str
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        bulan = ID_MONTH_NAMES[dt.month] if 1 <= dt.month <= 12 else str(dt.month)
        return f"{dt.day} {bulan} {dt.year}"
    except Exception:
        return tgl_str


def _parse_slash_date(tgl_str: str) -> Optional[str]:
    """Parse tanggal format M/D/YYYY dari tanda tangan PDF, contoh 6/10/2026."""
    if not tgl_str:
        return None
    raw = tgl_str.strip()
    for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_id_date(tgl_str: str) -> Optional[str]:
    if not tgl_str:
        return None
    import re
    norm = tgl_str.strip().lower()
    for indo, eng in [
        ("januari", "jan"), ("februari", "feb"), ("maret", "mar"), ("april", "apr"),
        ("mei", "may"), ("juni", "jun"), ("juli", "jul"),
        ("agustus", "aug"), ("agu", "aug"), ("agt", "aug"),
        ("september", "sep"), ("sept", "sep"),
        ("oktober", "oct"), ("okt", "oct"),
        ("november", "nov"),
        ("desember", "dec"), ("des", "dec"),
    ]:
        norm = re.sub(r"\b" + indo + r"\b", eng, norm)
    try:
        dt = date_parser.parse(norm, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def _parse_rp_amount(text: str) -> int:
    """Parse Indonesian Rupiah amounts.

    Handles:
    - Rp prefix: "Rp300.000", "Rp 1,234,567"
    - Comma as decimal: "300,5" → 300 (comma = thousands sep in ID)
    - Dot as thousands: "1.234.567" → 1234567
    - Negative: "-500.000" → -500000
    - Plain: "300000", "300,000"
    """
    import re
    raw = text.strip()

    # Extract numeric portion
    m = re.search(r"-?[\d.,]+", raw)
    if not m:
        return 0

    num_str = m.group(0)
    is_negative = num_str.startswith("-")
    num_str = num_str.lstrip("-")

    # Count separators
    comma_count = num_str.count(",")
    dot_count = num_str.count(".")

    # If both exist, figure out which is decimal separator
    if comma_count > 0 and dot_count > 0:
        # Last separator is decimal
        if num_str.rfind(",") > num_str.rfind("."):
            # Comma is decimal (e.g. "1.234,56")
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            # Dot is decimal (unlikely in ID format)
            num_str = num_str.replace(",", "")
    elif comma_count > 0:
        # Only commas: "2,000,000" → 2000000 (or "300,5" → 300?)
        # In ID accounting: comma = thousands sep, no decimal
        num_str = num_str.replace(",", "")
    elif dot_count > 0:
        # Only dots: "1.234.567" → 1234567
        num_str = num_str.replace(".", "")

    try:
        result = int(float(num_str))
        return -result if is_negative else result
    except ValueError:
        return 0
