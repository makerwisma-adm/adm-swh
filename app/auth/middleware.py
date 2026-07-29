"""HTTP middleware for role-based write protection."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.session import (
    AUTH_ONLY_PATHS,
    MEMBER_WRITE_PATHS,
    _is_member_pdm_delete_path,
    _is_member_petty_cash_write_path,
    _is_member_tagihan_attachment_path,
    get_current_user,
    is_admin,
    is_mitra,
    is_viewer,
    redirect_with_flash,
)
from app.services.approval import is_ka_sppg, is_maker


def _is_ka_write_path(path: str) -> bool:
    return path.startswith("/api/dashboard-ka")


def _is_bayar_write_path(path: str) -> bool:
    return path.startswith("/api/dashboard-bayar")


class MemberWriteGuardMiddleware(BaseHTTPMiddleware):
    """Member: upload terbatas. Viewer: hanya lihat."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            path = request.url.path.rstrip("/") or "/"
            user = get_current_user(request)
            if user and not is_admin(user):
                if is_ka_sppg(user):
                    if path not in AUTH_ONLY_PATHS and not _is_ka_write_path(path):
                        if path.startswith("/api/"):
                            return JSONResponse(
                                {"error": "Akses ditolak. KA SPPG hanya dapat menyetujui dari Dashboard KA."},
                                status_code=403,
                            )
                        from app.auth.session import default_home_path

                        return redirect_with_flash(
                            request,
                            default_home_path(user),
                            "Akses ditolak. KA SPPG hanya dapat menyetujui dari Dashboard KA.",
                        )
                elif is_maker(user):
                    if path not in AUTH_ONLY_PATHS and not _is_bayar_write_path(path):
                        if path.startswith("/api/"):
                            return JSONResponse(
                                {"error": "Akses ditolak. Maker hanya dapat memproses pembayaran VA dari Dashboard Pembayaran."},
                                status_code=403,
                            )
                        from app.auth.session import default_home_path

                        return redirect_with_flash(
                            request,
                            default_home_path(user),
                            "Akses ditolak. Maker hanya dapat memproses pembayaran VA dari Dashboard Pembayaran.",
                        )
                elif is_viewer(user) or is_mitra(user):
                    if path not in AUTH_ONLY_PATHS:
                        if path.startswith("/api/"):
                            return JSONResponse(
                                {"error": "Akses ditolak. Akun Anda hanya dapat melihat data."},
                                status_code=403,
                            )
                        from app.auth.session import default_home_path

                        return redirect_with_flash(
                            request,
                            default_home_path(user),
                            "Akses ditolak. Akun Anda hanya dapat melihat data.",
                        )
                elif (
                    path not in MEMBER_WRITE_PATHS
                    and not _is_member_pdm_delete_path(path)
                    and not _is_member_petty_cash_write_path(path)
                    and not _is_member_tagihan_attachment_path(path)
                ):
                    if path.startswith("/api/"):
                        return JSONResponse(
                            {
                                "error": (
                                    "Akses ditolak. Member hanya dapat upload di halaman "
                                    "Tagihan, Petty Cash, Gaji Relawan, dan Pengajuan Dana Mitra."
                                )
                            },
                            status_code=403,
                        )
                    return redirect_with_flash(
                        request,
                        "/tagihan",
                        "Akses ditolak. Anda tidak dapat mengubah data.",
                    )
        return await call_next(request)