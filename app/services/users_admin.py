"""Admin user management."""
import re
from typing import Any, Dict, List, Optional

from passlib.hash import pbkdf2_sha256

from app.constants import ROLE_ADMIN, ROLE_KA_SPPG, ROLE_MAKER, ROLE_MEMBER, ROLE_MITRA, ROLE_VIEWER
from app.db import get_db
from app.services.user_access import (
    parse_menu_access_raw,
    serialize_menu_access,
    validate_menu_access_keys,
)

VALID_ROLES = {ROLE_ADMIN, ROLE_KA_SPPG, ROLE_MAKER, ROLE_MEMBER, ROLE_VIEWER, ROLE_MITRA}
_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")


def list_users() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, full_name, role, mitra_nama, menu_access FROM users ORDER BY role, username"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        row = dict(r)
        row["menu_access_list"] = parse_menu_access_raw(row.get("menu_access")) or []
        result.append(row)
    return result


def _count_admins(conn, exclude_id: Optional[int] = None) -> int:
    if exclude_id:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = ? AND id != ?",
            (ROLE_ADMIN, exclude_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = ?", (ROLE_ADMIN,)
        ).fetchone()
    return row[0] or 0


def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str,
    mitra_nama: str = "",
    menu_access: Optional[List[str]] = None,
) -> Dict[str, Any]:
    username = (username or "").strip().lower()
    full_name = (full_name or "").strip()
    role = (role or ROLE_MEMBER).strip().lower()
    mitra_nama = (mitra_nama or "").strip()
    password = password or ""

    if not _USERNAME_RE.match(username):
        raise ValueError("Username 3–32 karakter: huruf kecil, angka, underscore.")
    if len(password) < 4:
        raise ValueError("Password minimal 4 karakter.")
    if not full_name:
        raise ValueError("Nama lengkap wajib diisi.")
    if role not in VALID_ROLES:
        raise ValueError("Role tidak valid.")
    if role == ROLE_MITRA and not mitra_nama:
        raise ValueError("Nama mitra wajib diisi untuk akun mitra.")

    menu_json = None
    if role != ROLE_ADMIN and menu_access is not None:
        menu_keys = validate_menu_access_keys(menu_access, role)
        menu_json = serialize_menu_access(menu_keys)

    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
        conn.close()
        raise ValueError("Username sudah digunakan.")

    conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role, mitra_nama, menu_access) VALUES (?,?,?,?,?,?)",
        (username, pbkdf2_sha256.hash(password), full_name, role, mitra_nama or None, menu_json),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return {
        "id": user_id,
        "username": username,
        "full_name": full_name,
        "role": role,
        "mitra_nama": mitra_nama or None,
        "menu_access": parse_menu_access_raw(menu_json),
    }


def update_user(
    user_id: int,
    *,
    actor_id: int,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    password: Optional[str] = None,
    mitra_nama: Optional[str] = None,
    menu_access: Optional[List[str]] = None,
) -> Dict[str, Any]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("User tidak ditemukan.")

    new_name = (full_name or row["full_name"] or "").strip()
    new_role = (role or row["role"] or ROLE_MEMBER).strip().lower()
    if role is not None and new_role != ROLE_MITRA:
        new_mitra_nama = ""
    else:
        new_mitra_nama = (mitra_nama if mitra_nama is not None else row["mitra_nama"] or "").strip()
    if not new_name:
        conn.close()
        raise ValueError("Nama lengkap wajib diisi.")
    if new_role not in VALID_ROLES:
        conn.close()
        raise ValueError("Role tidak valid.")
    if new_role == ROLE_MITRA and not new_mitra_nama:
        conn.close()
        raise ValueError("Nama mitra wajib diisi untuk akun mitra.")

    menu_json = row["menu_access"]
    if menu_access is not None or (role is not None and new_role != ROLE_ADMIN):
        if new_role == ROLE_ADMIN:
            menu_json = None
        else:
            existing = parse_menu_access_raw(row["menu_access"]) or []
            keys = menu_access if menu_access is not None else existing
            menu_keys = validate_menu_access_keys(keys, new_role)
            menu_json = serialize_menu_access(menu_keys)

    if row["role"] == ROLE_ADMIN and new_role != ROLE_ADMIN and _count_admins(conn, user_id) == 0:
        conn.close()
        raise ValueError("Minimal satu admin harus tersisa.")
    if user_id == actor_id and new_role != ROLE_ADMIN and row["role"] == ROLE_ADMIN:
        if _count_admins(conn, user_id) == 0:
            conn.close()
            raise ValueError("Anda adalah admin terakhir — tidak bisa mengubah role.")

    params = [new_name, new_role, new_mitra_nama or None, menu_json]
    sql = "UPDATE users SET full_name = ?, role = ?, mitra_nama = ?, menu_access = ?"
    if password and password.strip():
        if len(password.strip()) < 4:
            conn.close()
            raise ValueError("Password minimal 4 karakter.")
        sql += ", password_hash = ?"
        params.append(pbkdf2_sha256.hash(password.strip()))
    sql += " WHERE id = ?"
    params.append(user_id)
    conn.execute(sql, params)
    conn.commit()
    conn.close()
    return {
        "id": user_id,
        "username": row["username"],
        "full_name": new_name,
        "role": new_role,
        "mitra_nama": new_mitra_nama or None,
        "menu_access": parse_menu_access_raw(menu_json),
    }


def delete_user(user_id: int, actor_id: int) -> None:
    if user_id == actor_id:
        raise ValueError("Tidak bisa menghapus akun sendiri.")

    conn = get_db()
    row = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("User tidak ditemukan.")
    if row["role"] == ROLE_ADMIN and _count_admins(conn, user_id) == 0:
        conn.close()
        raise ValueError("Tidak bisa menghapus admin terakhir.")

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()