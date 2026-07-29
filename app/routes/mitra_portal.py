"""Portal khusus akun mitra."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.session import is_mitra, render_template, require_login
from app.services.mitra_portal import build_mitra_portal_context
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/portal-mitra", response_class=HTMLResponse)
async def mitra_portal_page(request: Request, user=Depends(require_login)):
    if not is_mitra(user):
        return RedirectResponse("/dashboard", status_code=303)
    return render_template(request, "portal_mitra.html", {
        **build_mitra_portal_context(user),
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "active_menu": "portal_mitra",
    })