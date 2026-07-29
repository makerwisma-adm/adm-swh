"""Batasi halaman yang dapat diakses akun mitra."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.session import get_current_user, is_mitra, redirect_with_flash
from app.constants import MITRA_ALLOWED_PATHS, MITRA_DEFAULT_PATH


class MitraAccessMiddleware(BaseHTTPMiddleware):
    """Mitra hanya boleh membuka portal, insentif, dan pengeluaran."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if path.startswith("/static") or path.startswith("/uploads"):
            return await call_next(request)

        user = get_current_user(request)
        if user and is_mitra(user) and path not in MITRA_ALLOWED_PATHS:
            if path.startswith("/api/"):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    {"error": "Akses ditolak. Akun mitra hanya dapat melihat insentif dan pengeluaran."},
                    status_code=403,
                )
            return redirect_with_flash(
                request,
                MITRA_DEFAULT_PATH,
                "Halaman ini tidak tersedia untuk akun mitra.",
            )
        return await call_next(request)