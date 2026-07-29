"""Authentication, authorization, and template helpers."""
import re
from typing import Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import PUBLIC_APP_URL, PUBLIC_LOGIN_URL
from app.constants import (
    AUTH_ONLY_PATHS,
    MEMBER_WRITE_PATHS,
    PORTAL_MODULES,
    ROLE_ADMIN,
    ROLE_KA_SPPG,
    ROLE_MAKER,
    ROLE_MEMBER,
    ROLE_MITRA,
    ROLE_VIEWER,
)
from app.services.approval import can_approve, can_mark_paid, can_submit_status, is_ka_sppg, is_maker
from app.services.mitra_access import get_mitra_nama
from app.services.user_access import (
    get_user_menu_keys,
    user_can_access_path,
    user_default_home_path,
)
from app.services.settings import get_theme_context
from app.db import get_db

templates = None


def get_current_user(request: Request):
    """Ambil user dari session middleware."""
    try:
        data = request.session.get("user")
        if not data or not data.get("user_id"):
            return None
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (data["user_id"],)).fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception:
        return None


def user_role(user: Optional[Dict]) -> str:
    if not user:
        return ""
    return (user.get("role") or ROLE_MEMBER).lower()


def is_admin(user: Optional[Dict]) -> bool:
    return user_role(user) == ROLE_ADMIN


def is_viewer(user: Optional[Dict]) -> bool:
    return user_role(user) == ROLE_VIEWER


def is_mitra(user: Optional[Dict]) -> bool:
    return user_role(user) == ROLE_MITRA


def require_ka_sppg(request: Request):
    user = require_login(request)
    if not is_ka_sppg(user) and not is_admin(user):
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya KA SPPG yang dapat mengakses halaman ini.")
    return user


def can_member_upload(user: Optional[Dict]) -> bool:
    return user_role(user) == ROLE_MEMBER


def _member_owns_pdm_item(conn, item_id: int, user_id: int) -> bool:
    row = conn.execute(
        """
        SELECT t.created_by, t.upload_id, u.created_by AS upload_creator
        FROM tagihan t
        LEFT JOIN uploads u ON u.id = t.upload_id
        WHERE t.id = ? AND t.kategori = 'pengajuan_dana_mitra'
        """,
        (item_id,),
    ).fetchone()
    if not row:
        return False
    if row["created_by"] == user_id:
        return True
    if row["upload_id"] and row["upload_creator"] == user_id:
        return True
    return False


def _is_member_pdm_delete_path(path: str) -> bool:
    if path == "/api/pengajuan-dana-mitra/bulk-delete":
        return True
    return bool(re.match(r"^/pengajuan-dana-mitra/\d+/delete$", path))


def _is_member_petty_cash_write_path(path: str) -> bool:
    if path == "/petty-cash/upload":
        return True
    if re.match(r"^/api/petty-cash/\d+/nota$", path):
        return True
    if re.match(r"^/api/petty-cash/\d+/ket$", path):
        return True
    return False


def _is_member_tagihan_attachment_path(path: str) -> bool:
    return bool(re.match(r"^/api/tagihan/\d+/(pict|nota|bukti)$", path))


def redirect_with_flash(
    request: Request,
    url: str,
    message: str = "",
    success: bool = False,
    status_code: int = 303,
) -> RedirectResponse:
    if message:
        request.session["flash"] = {"message": message, "success": success}
    return RedirectResponse(url, status_code=status_code)


def render_template(request: Request, name: str, context: Dict = None, status_code: int = 200):
    ctx = {k: v for k, v in (context or {}).items() if k != "request"}
    flash = request.session.pop("flash", None)
    if flash:
        ctx["message"] = flash.get("message", "")
        ctx["success"] = bool(flash.get("success", False))
    elif ctx.get("message"):
        ctx["strip_message_params"] = True
    ctx.setdefault("public_app_url", PUBLIC_APP_URL)
    ctx.setdefault("public_login_url", PUBLIC_LOGIN_URL)
    ctx.setdefault("theme", get_theme_context())
    user = ctx.get("user") or get_current_user(request)
    if user:
        ctx["user"] = user
        ctx["is_admin"] = is_admin(user)
        ctx["is_akuntan"] = can_member_upload(user)
        ctx["is_ka_sppg"] = is_ka_sppg(user)
        ctx["is_maker"] = is_maker(user)
        ctx["is_mitra"] = is_mitra(user)
        ctx["mitra_nama"] = get_mitra_nama(user)
        ctx["can_edit"] = is_admin(user) or (can_member_upload(user) and not is_ka_sppg(user) and not is_maker(user))
        ctx["can_approve"] = can_approve(user)
        ctx["can_mark_paid"] = can_mark_paid(user)
        ctx["can_submit"] = can_submit_status(user)
        if is_ka_sppg(user):
            from app.services.ka_notifications import count_unread_ka_notifications

            ctx["ka_unread_notification_count"] = count_unread_ka_notifications(user["id"])
        else:
            ctx.setdefault("ka_unread_notification_count", 0)
        ctx["can_upload"] = is_admin(user) or can_member_upload(user)
        ctx["can_download"] = is_admin(user) or can_member_upload(user)
        ctx.setdefault("can_delete_upload", can_member_upload(user))
        ctx["user_role"] = user_role(user)
        ctx["user_menu_keys"] = get_user_menu_keys(user)
    else:
        ctx.setdefault("is_admin", False)
        ctx.setdefault("is_akuntan", False)
        ctx.setdefault("is_ka_sppg", False)
        ctx.setdefault("is_maker", False)
        ctx.setdefault("is_mitra", False)
        ctx.setdefault("mitra_nama", "")
        ctx.setdefault("can_edit", False)
        ctx.setdefault("can_approve", False)
        ctx.setdefault("can_mark_paid", False)
        ctx.setdefault("can_submit", False)
        ctx.setdefault("can_upload", False)
        ctx.setdefault("can_download", False)
        ctx.setdefault("can_delete_upload", False)
        ctx.setdefault("user_role", "")
        ctx.setdefault("user_menu_keys", set())
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def _login_context(**extra):
    return {
        "portal_modules": PORTAL_MODULES,
        "public_app_url": PUBLIC_APP_URL,
        "public_login_url": PUBLIC_LOGIN_URL,
        **extra,
    }


def default_home_path(user: Optional[Dict] = None) -> str:
    if user:
        return user_default_home_path(user)
    return "/dashboard"


def _safe_next_url(next_url: str, user: Optional[Dict] = None) -> str:
    default_path = default_home_path(user)
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return default_path
    if next_url.startswith("/login") or next_url.startswith("/masuk") or next_url.startswith("/logout"):
        return default_path
    if user:
        base = next_url.split("?", 1)[0].rstrip("/") or "/"
        if not user_can_access_path(user, base):
            return default_path
    return next_url


def require_login(request: Request):
    user = get_current_user(request)
    if not user:
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        from urllib.parse import quote

        location = f"/masuk?next={quote(next_path, safe='')}"
        raise HTTPException(status_code=302, headers={"Location": location})
    return user


def require_admin(request: Request):
    user = require_login(request)
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya admin yang dapat mengubah data.")
    return user