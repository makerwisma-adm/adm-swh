"""FastAPI application factory."""
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.auth import session as auth_session
from app.auth.middleware import MemberWriteGuardMiddleware
from app.auth.user_access_guard import UserAccessMiddleware
from app.config import BASE_DIR, IS_VERCEL, SECRET_KEY, SESSION_COOKIE_NAME, UPLOAD_DIR
from app.database import init_db, migrate_petty_cash_from_tagihan, seed_initial_tagihan
from app.services.tagihan import sync_tagihan_rekening_pemilik
from app.routes.auth import limiter
from app.routes import register_routes

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.cache_size = 0
templates.env.cache = None
templates.env.auto_reload = True
auth_session.templates = templates


def create_app() -> FastAPI:
    application = FastAPI(title="Pelaporan Keuangan SPPG Wisma Haji", version="1.0")

    # Add rate limiter state
    application.state.limiter = limiter

    @application.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """Friendly HTML on login rate-limit; JSON for API."""
        path = request.url.path.rstrip("/") or "/"
        accept = (request.headers.get("accept") or "").lower()
        wants_html = "text/html" in accept or path in ("/masuk", "/login")
        if wants_html and path in ("/masuk", "/login", ""):
            from app.auth.session import _login_context, render_template

            return render_template(
                request,
                "login.html",
                _login_context(
                    user=None,
                    error="Terlalu banyak percobaan login. Tunggu sebentar lalu coba lagi.",
                    message=None,
                    next_url="/dashboard",
                ),
                status_code=429,
            )
        return JSONResponse(
            {"error": f"Rate limit exceeded: {exc.detail}"},
            status_code=429,
        )

    @application.exception_handler(HTTPException)
    async def auth_redirect_handler(request: Request, exc: HTTPException):
        if exc.status_code in (301, 302, 303, 307, 308):
            location = (exc.headers or {}).get("Location")
            if location:
                return RedirectResponse(url=location, status_code=exc.status_code)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    # Di Vercel, static dilayani dari public/ oleh CDN
    if not IS_VERCEL:
        static_dir = os.path.join(BASE_DIR, "static")
        if os.path.exists(static_dir):
            application.mount("/static", StaticFiles(directory=static_dir), name="static")
        local_uploads = os.path.join(BASE_DIR, "uploads")
        if os.path.exists(local_uploads):
            application.mount("/uploads", StaticFiles(directory=local_uploads), name="uploads")

    application.add_middleware(UserAccessMiddleware)
    application.add_middleware(MemberWriteGuardMiddleware)
    application.add_middleware(
        SessionMiddleware,
        secret_key=SECRET_KEY,
        session_cookie=SESSION_COOKIE_NAME,
        max_age=None,  # sesi browser saja; tutup browser = login ulang
        same_site="lax",
        https_only=IS_VERCEL,
    )

    register_routes(application)
    return application


def bootstrap_database() -> None:
    try:
        init_db()
        migrate_petty_cash_from_tagihan()
        seed_initial_tagihan()
        sync_tagihan_rekening_pemilik()
    except Exception as exc:
        # Cold start di Vercel tidak boleh total gagal karena Blob/network
        print(f"⚠️  bootstrap_database: {exc}")


bootstrap_database()
app = create_app()