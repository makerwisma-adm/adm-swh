"""Akses menu kustom per pengguna."""
import json
from typing import Any, Dict, List, Optional, Set

from app.constants import (
    AUTH_ONLY_PATHS,
    MODULE_ACCESS_GROUPS,
    MODULE_BY_KEY,
    MODULE_HOME_PRIORITY,
    ROLE_ADMIN,
    ROLE_KA_SPPG,
    ROLE_MAKER,
    ROLE_MEMBER,
    ROLE_MITRA,
    ROLE_VIEWER,
)

_ALWAYS_ALLOWED_PREFIXES = ("/static", "/uploads")


def _all_module_keys() -> List[str]:
    return [m["key"] for m in MODULE_BY_KEY.values()]


def role_default_menu_keys(role: str) -> Set[str]:
    role = (role or ROLE_MEMBER).lower()
    if role == ROLE_ADMIN:
        return set(_all_module_keys())
    if role == ROLE_KA_SPPG:
        return {"dashboard_ka", "transfer_bgn"}
    if role == ROLE_MAKER:
        return {"dashboard_bayar", "transfer_bgn", "laporan"}
    if role == ROLE_MITRA:
        return {"portal_mitra", "insentif_mitra", "pendapatan_mitra", "pengeluaran_mitra"}
    keys = set(_all_module_keys())
    keys.discard("setup")
    keys.discard("portal_mitra")
    keys.discard("dashboard_ka")
    keys.discard("dashboard_bayar")
    return keys


def parse_menu_access_raw(raw: Any) -> Optional[List[str]]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, list):
        keys = [str(k).strip() for k in raw if str(k).strip()]
        return keys or None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            keys = [k.strip() for k in text.split(",") if k.strip()]
            return keys or None
        if isinstance(data, list):
            keys = [str(k).strip() for k in data if str(k).strip()]
            return keys or None
    return None


def serialize_menu_access(keys: Optional[List[str]]) -> Optional[str]:
    if not keys:
        return None
    valid = [k for k in keys if k in MODULE_BY_KEY]
    if not valid:
        return None
    return json.dumps(sorted(set(valid)))


def get_user_menu_keys(user: Optional[Dict[str, Any]]) -> Set[str]:
    if not user:
        return set()
    if (user.get("role") or "").lower() == ROLE_ADMIN:
        return set(_all_module_keys())

    custom = parse_menu_access_raw(user.get("menu_access"))
    if custom is not None:
        return {k for k in custom if k in MODULE_BY_KEY}

    return role_default_menu_keys(user.get("role"))


def user_has_module(user: Optional[Dict[str, Any]], module_key: str) -> bool:
    return module_key in get_user_menu_keys(user)


def user_default_home_path(user: Optional[Dict[str, Any]]) -> str:
    keys = get_user_menu_keys(user)
    for key in MODULE_HOME_PRIORITY:
        if key in keys:
            mod = MODULE_BY_KEY.get(key)
            if mod:
                return mod["href"]
    for key in keys:
        mod = MODULE_BY_KEY.get(key)
        if mod:
            return mod["href"]
    return "/masuk"


def path_to_module_key(path: str) -> Optional[str]:
    path = path.rstrip("/") or "/"
    if path == "/":
        return "dashboard"

    for mod in MODULE_BY_KEY.values():
        for prefix in mod.get("path_prefixes") or [mod["href"]]:
            p = prefix.rstrip("/") or "/"
            if path == p or path.startswith(p + "/"):
                return mod["key"]
    return None


def user_can_access_path(user: Optional[Dict[str, Any]], path: str) -> bool:
    if not user:
        return False

    path = path.rstrip("/") or "/"
    if path in AUTH_ONLY_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in _ALWAYS_ALLOWED_PREFIXES):
        return True

    if (user.get("role") or "").lower() == ROLE_ADMIN:
        return True

    module_key = path_to_module_key(path)
    if module_key is None:
        return False

    return module_key in get_user_menu_keys(user)


def validate_menu_access_keys(keys: List[str], role: str) -> List[str]:
    role = (role or ROLE_MEMBER).lower()
    if role == ROLE_ADMIN:
        return []

    valid = sorted({k for k in keys if k in MODULE_BY_KEY and k != "setup"})
    if not valid:
        raise ValueError("Pilih minimal satu modul yang boleh diakses.")
    if role == ROLE_MITRA:
        required = {"portal_mitra", "insentif_mitra", "pendapatan_mitra", "pengeluaran_mitra"}
        if not required.issubset(set(valid)):
            raise ValueError("Akun mitra wajib memiliki akses Portal Mitra, Insentif, Pendapatan, dan Pengeluaran.")
    if role == ROLE_KA_SPPG and "dashboard_ka" not in valid:
        raise ValueError("Akun KA SPPG wajib memiliki akses Dashboard KA SPPG.")
    if role == ROLE_MAKER and "dashboard_bayar" not in valid:
        raise ValueError("Akun Maker wajib memiliki akses Dashboard Pembayaran.")
    return valid


def filter_modules_for_user(
    user: Optional[Dict[str, Any]],
    modules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter daftar modul portal/dashboard sesuai menu_access pengguna."""
    keys = get_user_menu_keys(user)
    result = []
    for mod in modules:
        key = mod.get("key")
        if not key:
            href = mod.get("href", "")
            for m in MODULE_BY_KEY.values():
                if m.get("href") == href:
                    key = m["key"]
                    break
        if key and key in keys:
            result.append(mod)
    return result


def menu_access_summary(user: Dict[str, Any]) -> str:
    keys = sorted(get_user_menu_keys(user))
    if (user.get("role") or "").lower() == ROLE_ADMIN:
        return "Semua modul"
    labels = [MODULE_BY_KEY[k]["label"] for k in keys if k in MODULE_BY_KEY]
    if len(labels) <= 2:
        return ", ".join(labels)
    return f"{len(labels)} modul"