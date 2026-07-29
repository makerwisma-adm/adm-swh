"""API personel untuk modul gaji & setup."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.session import require_login
from app.services.personnel import (
    PERSONNEL_TYPES,
    create_personnel,
    delete_personnel,
    list_personnel,
    list_personnel_grouped,
    update_personnel,
)

router = APIRouter()


@router.get("/api/personnel")
async def api_list_personnel(
    user=Depends(require_login),
    tipe: str = "",
    aktif_only: bool = True,
):
    if tipe:
        return {"items": list_personnel(tipe, aktif_only=aktif_only)}
    return {
        "grouped": list_personnel_grouped(aktif_only=aktif_only),
        "types": PERSONNEL_TYPES,
    }