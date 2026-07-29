"""Pendapatan mitra routes — laporan read-only dari data insentif mitra."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.auth.session import is_mitra, render_template, require_login
from app.services.mitra_access import get_mitra_nama
from app.services.mitra_page_filter import apply_mitra_page_filter
from app.services.mitra_portal import build_mitra_portal_context
from app.services.pendapatan_mitra_page import build_pendapatan_mitra_page_context
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/pendapatan-mitra", response_class=HTMLResponse)
async def pendapatan_mitra_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    status: str = "",
    periode: str = "",
    tanggal: str = "",
    dari: str = "",
    sampai: str = "",
):
    ctx = build_pendapatan_mitra_page_context(
        search=search,
        status=status,
        periode=periode,
        tanggal=tanggal,
        dari=dari,
        sampai=sampai,
    )
    portal_ctx = {}
    if is_mitra(user):
        ctx = apply_mitra_page_filter(ctx, get_mitra_nama(user))
        portal_ctx = build_mitra_portal_context(user)

    return render_template(request, "pendapatan_mitra.html", {
        **portal_ctx,
        **ctx,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "pendapatan_mitra",
    })