"""HTTP middleware for role-based write protection."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.session import get_current_user, is_admin, redirect_with_flash
from app.services.user_access import user_can_access_path, user_default_home_path

import os

def _debug_log(msg):
    if os.getenv("DEBUG_MIDDLEWARE"):
        print(f"[UserAccessMiddleware] {msg}", flush=True)


class UserAccessMiddleware(BaseHTTPMiddleware):
    """Non-admin hanya boleh membuka modul yang dicentang di Setup."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if path.startswith("/static") or path.startswith("/uploads"):
            return await call_next(request)

        user = get_current_user(request)
        _debug_log(f"path={path!r} user={user}")

        if not user or is_admin(user):
            _debug_log("pass: no user or is_admin")
            return await call_next(request)

        # Akuntan (member) bypass untuk /setup dan /api/setup
        if (user.get("role") or "").lower() == "member":
            if path.startswith("/setup") or path.startswith("/api/setup"):
                _debug_log("pass: member bypass for /setup")
                return await call_next(request)

        can_access = user_can_access_path(user, path)
        _debug_log(f"user_can_access_path={can_access}")

        if can_access:
            _debug_log("pass: user_can_access_path=True")
            return await call_next(request)

        home = user_default_home_path(user)
        if path.startswith("/api/"):
            from fastapi.responses import JSONResponse

            _debug_log(f"reject API: home={home!r}")
            return JSONResponse(
                {"error": "Akses ditolak. Modul ini tidak diizinkan untuk akun Anda."},
                status_code=403,
            )

        _debug_log(f"reject HTML: home={home!r}")
        return redirect_with_flash(
            request,
            home,
            "Akses ditolak. Modul ini tidak diizinkan untuk akun Anda.",
        )
