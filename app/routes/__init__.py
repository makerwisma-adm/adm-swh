"""Register all HTTP route modules."""
from fastapi import FastAPI

from app.routes import (
    api,
    auth,
    dashboard_bayar,
    dashboard_ka,
    exports,
    gaji_relawan,
    gaji_staff,
    insentif_mitra,
    insentif_pic,
    laporan,
    mitra_portal,
    pendapatan_mitra,
    pengajuan_dana_mitra,
    pengeluaran_mitra,
    pengembalian_dana,
    personnel_api,
    petty_cash,
    tagihan,
    sewa_kendaraan,
    setup,
    transfer_bgn,
    upload,
)


def register_routes(app: FastAPI) -> None:
    for module in (
        auth,
        dashboard_bayar,
        dashboard_ka,
        transfer_bgn,
        laporan,
        mitra_portal,
        pendapatan_mitra,
        gaji_relawan,
        gaji_staff,
        insentif_pic,
        personnel_api,
        insentif_mitra,
        pengembalian_dana,
        sewa_kendaraan,
        pengajuan_dana_mitra,
        pengeluaran_mitra,
        petty_cash,
        tagihan,
        api,
        exports,
        upload,
        setup,
    ):
        app.include_router(module.router)