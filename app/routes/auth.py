"""Auth, dashboard, and tagihan page routes."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.hash import pbkdf2_sha256
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.session import (
    ROLE_MEMBER,
    _login_context,
    _safe_next_url,
    default_home_path,
    get_current_user,
    redirect_with_flash,
    render_template,
    require_login,
)
from app.services.user_access import user_has_module
from app.config import SESSION_COOKIE_NAME
from app.db import get_db
from app.services.dashboard import get_dashboard_context
from app.services.tagihan_page import build_tagihan_page_context
from app.utils.formatters import format_rupiah, format_tanggal_display

limiter = Limiter(key_func=get_remote_address)
LOGIN_RATE_LIMIT = "30 per minute"

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(default_home_path(user))
    return RedirectResponse("/masuk")


@router.get("/masuk", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "", message: str = "", error: str = ""):
    if message:
        qs = f"?next={next}" if next else ""
        return RedirectResponse(f"/masuk{qs}", status_code=303)
    user = get_current_user(request)
    return render_template(request, "login.html", _login_context(
        user=user,
        error=error or None,
        message=None,
        next_url=_safe_next_url(next),
    ))


@router.get("/login", response_class=HTMLResponse)
async def login_redirect(request: Request, next: str = "", message: str = "", error: str = ""):
    from urllib.parse import urlencode
    params = {}
    if next:
        params["next"] = next
    if error:
        params["error"] = error
    qs = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"/masuk{qs}", status_code=303)


@router.post("/masuk", response_class=HTMLResponse)
@router.post("/login", response_class=HTMLResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/dashboard"),
):
    username = username.strip()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not pbkdf2_sha256.verify(password, user["password_hash"]):
        return render_template(request, "login.html", _login_context(
            user=None,
            error="Username atau password salah. Periksa kembali lalu coba lagi.",
            message=None,
            next_url=_safe_next_url(next),
            username_value=username,
        ), status_code=401)

    request.session.clear()
    request.session["user"] = {
        "user_id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"] or ROLE_MEMBER,
    }

    user_dict = dict(user)
    dest = _safe_next_url(next, user_dict)
    return RedirectResponse(dest, status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    resp = RedirectResponse("/masuk", status_code=303)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user=Depends(require_login)):
    from app.auth.session import render_template
    from app.services.user_access import parse_menu_access_raw

    user = dict(user)
    user["menu_access_list"] = parse_menu_access_raw(user.get("menu_access")) or []
    return render_template(request, "profile.html", {"user": user})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user=Depends(require_login),
    chart_dari: str = "",
    chart_sampai: str = "",
):
    if not user_has_module(user, "dashboard"):
        return redirect_with_flash(
            request,
            default_home_path(user),
            "Akses Dashboard tidak diizinkan untuk akun Anda.",
        )
    return render_template(request, "dashboard.html", {
        **get_dashboard_context(user, chart_dari=chart_dari, chart_sampai=chart_sampai),
        "format_rupiah": format_rupiah,
        "active_menu": "dashboard",
    })

@router.get("/tagihan", response_class=HTMLResponse)
async def tagihan_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    status: str = "",
    rekening: str = "",
    tanggal: str = "",
    kategori: str = "",
    dari: str = "",
    sampai: str = "",
    message: str = "",
    success: bool = False
):
    if kategori == "petty_cash":
        return RedirectResponse("/petty-cash", status_code=303)
    if kategori == "gaji_relawan":
        return RedirectResponse("/gaji-relawan", status_code=303)
    if kategori == "gaji_staff":
        return RedirectResponse("/gaji-staff", status_code=303)
    if kategori == "insentif_pic":
        return RedirectResponse("/insentif-pic", status_code=303)
    if kategori == "insentif_mitra":
        return RedirectResponse("/insentif-mitra", status_code=303)
    if kategori == "pengembalian_dana":
        return RedirectResponse("/pengembalian-dana", status_code=303)
    if kategori == "sewa_kendaraan":
        return RedirectResponse("/sewa-kendaraan", status_code=303)
    if kategori == "pengajuan_dana_mitra":
        return RedirectResponse("/pengajuan-dana-mitra", status_code=303)
    if kategori in ("pic", "tagihan_bulanan"):
        return RedirectResponse("/tagihan", status_code=303)

    return render_template(request, "tagihan.html", {
        **build_tagihan_page_context(
            search=search,
            status=status,
            rekening=rekening,
            tanggal=tanggal,
            kategori=kategori,
            dari=dari,
            sampai=sampai,
        ),
        "user": user,
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "message": message,
        "success": success,
    })
