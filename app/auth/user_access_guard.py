"""Middleware: batasi halaman sesuai akses menu kustom pengguna."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.session import get_current_user, is_admin, redirect_with_flash
from app.services.user_access import user_can_access_path, user_default_home_path


class UserAccessMiddleware(BaseHTTPMiddleware):
    """Non-admin hanya boleh membuka modul yang dicentang di Setup."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if path.startswith("/static") or path.startswith("/uploads"):
            return await call_next(request)

        user = get_current_user(request)
        if not user or is_admin(user):
            return await call_next(request)

        if user_can_access_path(user, path):
            return await call_next(request)

        # Akuntan boleh akses /api/setup/* tanpa memandang menu_access
        if path.startswith("/api/setup"):
            return await call_next(request)

        # Akuntan boleh akses /setup tanpa memandang menu_access
        if path.startswith("/setup"):
            return await call_next(request)

        home = user_default_home_path(user)
        if path.startswith("/api/"):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {"error": "Akses ditolak. Modul ini tidak diizinkan untuk akun Anda."},
                status_code=403,
            )

        return redirect_with_flash(
            request,
            home,
            "Akses ditolak. Modul ini tidak diizinkan untuk akun Anda.",
        )