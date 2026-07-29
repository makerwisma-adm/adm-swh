#!/usr/bin/env python3
"""
Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun
Entry point — logika aplikasi ada di paket app/
"""

from app.factory import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    import socket
    import uvicorn

    port = 8001
    local_ip = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except OSError:
        pass

    print("🚀 Menjalankan Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun")
    print(f"   Lokal  → http://localhost:{port}/masuk")
    if local_ip:
        print(f"   HP/LAN → http://{local_ip}:{port}/masuk")
    print("   Login: admin / admin123  |  KA: ka_sppg / ka123  |  Maker: maker / maker123")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)