"""Dashboard KA SPPG — persetujuan pengajuan DIAJUKAN."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth.session import is_ka_sppg, render_template, require_ka_sppg, require_login
from app.db import get_db
from app.constants import STATUS_DISETUJUI
from app.services.approval import bulk_reject_tagihan, bulk_set_tagihan_status, get_ka_dashboard_context
from app.services.finance_summary import get_bgn_saldo_snapshot
from app.services.lunas_laporan import get_lunas_laporan_context
from app.services.user_access import user_has_module
from app.utils.formatters import format_rupiah, format_tanggal_display

router = APIRouter()


@router.get("/dashboard-ka", response_class=HTMLResponse)
async def dashboard_ka_page(
    request: Request,
    user=Depends(require_login),
    search: str = "",
    kategori: str = "",
    tab: str = "diajukan",
    dari: str = "",
    sampai: str = "",
):
    if not is_ka_sppg(user) and not user_has_module(user, "dashboard_ka"):
        from app.auth.session import default_home_path, redirect_with_flash

        return redirect_with_flash(
            request,
            default_home_path(user),
            "Akses Dashboard KA SPPG tidak diizinkan untuk akun Anda.",
        )
    if tab == "lunas" and is_ka_sppg(user):
        from app.services.ka_notifications import mark_ka_notifications_read

        mark_ka_notifications_read(user["id"], None)

    ctx = get_ka_dashboard_context(
        search=search,
        kategori=kategori,
        tab=tab,
        ka_user_id=user.get("id"),
        dari=dari,
        sampai=sampai,
    )
    lunas_ctx = get_lunas_laporan_context(
        scope="ka",
        kategori=kategori,
        search=search,
        dari=dari or None,
        sampai=sampai or None,
        user=user,
    )
    return render_template(request, "dashboard_ka.html", {
        "user": user,
        "active_menu": "dashboard_ka",
        "format_rupiah": format_rupiah,
        "format_tanggal": format_tanggal_display,
        "lunas_export_href": lunas_ctx["export_csv_href"],
        "lunas_export_count": lunas_ctx["item_count"],
        "filters_dari": dari,
        "filters_sampai": sampai,
        "bgn_saldo": get_bgn_saldo_snapshot(),
        **ctx,
    })


@router.post("/api/dashboard-ka/approve")
async def api_dashboard_ka_approve(request: Request, user=Depends(require_ka_sppg)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not ids:
            return JSONResponse({"error": "Pilih minimal satu pengajuan."}, status_code=400)

        conn = get_db()
        updated = bulk_set_tagihan_status(conn, ids, STATUS_DISETUJUI, user)
        conn.commit()
        conn.close()
        if updated == 0:
            return JSONResponse(
                {"error": "Tidak ada pengajuan yang dapat disetujui. Pastikan status masih DIAJUKAN."},
                status_code=400,
            )
        return JSONResponse({"success": True, "updated": updated})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/dashboard-ka/reject")
async def api_dashboard_ka_reject(request: Request, user=Depends(require_ka_sppg)):
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        note = (data.get("note") or data.get("rejection_note") or "").strip()
        if not ids:
            return JSONResponse({"error": "Pilih minimal satu pengajuan."}, status_code=400)
        if len(note) < 3:
            return JSONResponse({"error": "Alasan penolakan wajib diisi (minimal 3 karakter)."}, status_code=400)

        conn = get_db()
        updated = bulk_reject_tagihan(conn, ids, user, note)
        conn.commit()
        conn.close()
        if updated == 0:
            return JSONResponse(
                {"error": "Tidak ada pengajuan yang dapat ditolak. Pastikan status masih DIAJUKAN."},
                status_code=400,
            )
        return JSONResponse({"success": True, "updated": updated})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/dashboard-ka/notifications/read")
async def api_dashboard_ka_notifications_read(request: Request, user=Depends(require_ka_sppg)):
    try:
        data = await request.json()
        mark_all = bool(data.get("all"))
        raw_ids = data.get("ids", [])
        ids = None if mark_all else [int(i) for i in raw_ids if str(i).isdigit()]
        from app.services.ka_notifications import mark_ka_notifications_read

        updated = mark_ka_notifications_read(user["id"], ids)
        return JSONResponse({"success": True, "updated": updated})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)