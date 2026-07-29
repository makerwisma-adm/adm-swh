"""Admin setup: users & theme."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth.session import is_admin, redirect_with_flash, render_template, require_admin, require_login
from app.constants import ICON_STYLES, MODULE_ACCESS_GROUPS, ROLE_OPTIONS
from app.services.user_access import parse_menu_access_raw
from app.services.settings import get_theme_context, save_settings, settings_for_api
from app.services.personnel import (
    PERSONNEL_TYPES,
    create_personnel,
    delete_personnel,
    list_personnel_grouped,
    update_personnel,
)
from app.services.users_admin import create_user, delete_user, list_users, update_user

router = APIRouter()


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, user=Depends(require_login)):
    if not is_admin(user) and not can_member_upload(user):
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/", status_code=303)

    return render_template(request, "setup.html", {
        "user": user,
        "users": list_users(),
        "theme": get_theme_context(),
        "role_options": ROLE_OPTIONS,
        "module_access_groups": MODULE_ACCESS_GROUPS,
        "icon_styles": ICON_STYLES,
        "personnel_types": PERSONNEL_TYPES,
        "personnel_grouped": list_personnel_grouped(),
        "active_menu": "setup",
        "can_manage_users": is_admin(user),
        "can_manage_personel": is_admin(user) or can_member_upload(user),
        "is_admin": is_admin(user),
        "is_akuntan": can_member_upload(user),
    })


@router.get("/api/setup/users")
async def api_list_users(user=Depends(require_admin)):
    return list_users()


@router.post("/api/setup/users")
async def api_create_user(request: Request, user=Depends(require_admin)):
    try:
        data = await request.json()
        created = create_user(
            username=data.get("username", ""),
            password=data.get("password", ""),
            full_name=data.get("full_name", ""),
            role=data.get("role", "member"),
            mitra_nama=data.get("mitra_nama", ""),
            menu_access=data.get("menu_access"),
        )
        return JSONResponse({"success": True, "user": created})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.patch("/api/setup/users/{user_id}")
async def api_update_user(user_id: int, request: Request, user=Depends(require_login)):
    is_self = user["id"] == user_id
    is_admin_user = is_admin(user)
    if not is_admin_user and not is_self:
        return JSONResponse({"error": "Akses ditolak"}, status_code=403)
    try:
        data = await request.json()
        if is_self and not is_admin_user:
            updated = update_user(
                user_id,
                actor_id=user["id"],
                full_name=data.get("full_name"),
                password=data.get("password") or None,
            )
        else:
            updated = update_user(
                user_id,
                actor_id=user["id"],
                full_name=data.get("full_name"),
                role=data.get("role"),
                password=data.get("password") or None,
                mitra_nama=data.get("mitra_nama"),
                menu_access=data.get("menu_access"),
            )
        return JSONResponse({"success": True, "user": updated})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/setup/users/{user_id}")
async def api_delete_user(user_id: int, user=Depends(require_admin)):
    try:
        delete_user(user_id, actor_id=user["id"])
        return JSONResponse({"success": True})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/setup/personnel")
async def api_setup_list_personnel(user=Depends(require_login)):
    return {
        "grouped": list_personnel_grouped(),
        "types": PERSONNEL_TYPES,
    }


@router.post("/api/setup/personnel")
async def api_setup_create_personnel(request: Request, user=Depends(require_login)):
    try:
        data = await request.json()
        created = create_personnel(
            tipe=data.get("tipe", ""),
            nama=data.get("nama", ""),
            no=data.get("no", ""),
            atas_nama=data.get("atas_nama", ""),
            nomor_rekening=data.get("nomor_rekening", ""),
            bank=data.get("bank", ""),
            pos=data.get("pos", ""),
            aktif=data.get("aktif", True),
        )
        return JSONResponse({"success": True, "personnel": created})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.patch("/api/setup/personnel/{personnel_id}")
async def api_setup_update_personnel(
    personnel_id: int,
    request: Request,
    user=Depends(require_login),
):
    try:
        data = await request.json()
        updated = update_personnel(
            personnel_id,
            tipe=data.get("tipe"),
            nama=data.get("nama"),
            no=data.get("no"),
            atas_nama=data.get("atas_nama"),
            nomor_rekening=data.get("nomor_rekening"),
            bank=data.get("bank"),
            pos=data.get("pos"),
            aktif=data.get("aktif"),
        )
        return JSONResponse({"success": True, "personnel": updated})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/setup/personnel/{personnel_id}")
async def api_setup_delete_personnel(personnel_id: int, user=Depends(require_login)):
    try:
        delete_personnel(personnel_id)
        return JSONResponse({"success": True})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/setup/settings")
async def api_get_settings(user=Depends(require_admin)):
    return settings_for_api()


@router.post("/api/setup/settings")
async def api_save_settings(request: Request, user=Depends(require_admin)):
    try:
        data = await request.json()
        theme = save_settings(data, user_id=user["id"])
        return JSONResponse({"success": True, "theme": theme})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/setup/settings", response_class=HTMLResponse)
async def setup_save_settings_form(request: Request, user=Depends(require_admin)):
    form = await request.form()
    save_settings(dict(form), user_id=user["id"])
    return redirect_with_flash(
        request,
        "/setup#tema",
        "Pengaturan tema berhasil disimpan.",
        success=True,
    )