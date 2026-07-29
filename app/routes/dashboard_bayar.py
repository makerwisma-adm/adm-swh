"""Dashboard Pembayaran — tandai pengajuan DISETUJUI menjadi DIBAYARKAN."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth.session import can_mark_paid, render_template, require_login
from app.constants import STATUS_LUNAS
from app.db import get_db
from app.services.approval import bulk_set_tagihan_status, get_bayar_dashboard_context
from app.services.finance_summary import get_bgn_saldo_snapshot
from app.services.lunas_laporan import get_lunas_laporan_context
from app.services.user_access import user_has_module
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/dashboard-bayar", response_class=HTMLResponse)
async def dashboard_bayar_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    kategori: str = "",
    dari: str = "",
    sampai: str = "",
):
    if not can_mark_paid(user) and not user_has_module(user, "dashboard_bayar"):
        from app.auth.session import default_home_path, redirect_with_flash

        return redirect_with_flash(
            request,
            default_home_path(user),
            "Akses Dashboard Pembayaran tidak diizinkan untuk akun Anda.",
        )
    ctx = get_bayar_dashboard_context(search=search, kategori=kategori)
    lunas_ctx = get_lunas_laporan_context(
        scope="maker",
        kategori=kategori,
        search=search,
        dari=dari or None,
        sampai=sampai or None,
        user=user,
    )
    return render_template(request, "dashboard_bayar.html", {
        "user": user,
        "active_menu": "dashboard_bayar",
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "lunas_export_href": lunas_ctx["export_csv_href"],
        "lunas_export_count": lunas_ctx["item_count"],
        "filters_dari": dari,
        "filters_sampai": sampai,
        "bgn_saldo": get_bgn_saldo_snapshot(),
        **ctx,
    })


@router.post("/api/dashboard-bayar/pay")
async def api_dashboard_bayar_pay(request: Request, user=Depends(require_login)):
    if not can_mark_paid(user):
        return JSONResponse({"error": "Akses ditolak. Hanya Maker Pembayaran atau admin yang dapat memproses VA."}, status_code=403)
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "Pilih minimal satu pengajuan."}, status_code=400)

        conn = get_db()
        updated = bulk_set_tagihan_status(conn, ids, STATUS_LUNAS, user)
        conn.commit()
        conn.close()
        if updated == 0:
            return JSONResponse(
                {"error": "Tidak ada pengajuan yang dapat ditandai lunas. Pastikan status masih DISETUJUI."},
                status_code=400,
            )
        return JSONResponse({"success": True, "updated": updated})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)