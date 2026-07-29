"""App-wide theme and branding settings."""
import json
from typing import Any, Dict, Optional

from app.constants import DEFAULT_THEME, THEME_PRESETS
from app.db import get_db

_settings_cache: Optional[Dict[str, str]] = None

SETTING_KEYS = (
    "theme_preset",
    "color_primary",
    "color_accent",
    "color_secondary",
    "color_icon",
    "icon_style",
)


def _defaults() -> Dict[str, str]:
    base = dict(DEFAULT_THEME)
    base["theme_preset"] = "classic"
    return base


def invalidate_settings_cache() -> None:
    global _settings_cache
    _settings_cache = None


def get_raw_settings(force: bool = False) -> Dict[str, str]:
    global _settings_cache
    if _settings_cache is not None and not force:
        return dict(_settings_cache)

    defaults = _defaults()
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    conn.close()

    merged = dict(defaults)
    for row in rows:
        if row["key"] in SETTING_KEYS and row["value"]:
            merged[row["key"]] = row["value"]
    _settings_cache = merged
    return dict(merged)


def save_settings(values: Dict[str, str], user_id: int) -> Dict[str, str]:
    cleaned: Dict[str, str] = {}
    preset = (values.get("theme_preset") or "classic").strip()
    if preset in THEME_PRESETS:
        cleaned.update(THEME_PRESETS[preset])
        cleaned["theme_preset"] = preset

    for key in SETTING_KEYS:
        if key == "theme_preset":
            continue
        raw = values.get(key)
        if raw is None:
            continue
        val = str(raw).strip()
        if not val:
            continue
        if key.startswith("color_") and not _valid_hex(val):
            continue
        if key == "icon_style" and val not in ("rounded", "soft", "sharp"):
            continue
        cleaned[key] = val

    if "theme_preset" not in cleaned:
        cleaned["theme_preset"] = preset if preset in THEME_PRESETS else "classic"

    conn = get_db()
    for key, val in cleaned.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_by)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_by = excluded.updated_by,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, val, user_id),
        )
    conn.commit()
    conn.close()
    invalidate_settings_cache()
    return get_theme_context(force=True)


def _valid_hex(color: str) -> bool:
    c = color.lstrip("#")
    return len(c) in (3, 6) and all(ch in "0123456789abcdefABCDEF" for ch in c)


def get_theme_context(force: bool = False) -> Dict[str, Any]:
    raw = get_raw_settings(force=force)
    preset = raw.get("theme_preset", "classic")
    preset_meta = THEME_PRESETS.get(preset, THEME_PRESETS["classic"])
    icon_style = raw.get("icon_style", "rounded")
    return {
        "preset": preset,
        "preset_label": preset_meta.get("label", "Klasik BGN"),
        "primary": raw.get("color_primary", DEFAULT_THEME["color_primary"]),
        "accent": raw.get("color_accent", DEFAULT_THEME["color_accent"]),
        "secondary": raw.get("color_secondary", DEFAULT_THEME["color_secondary"]),
        "icon": raw.get("color_icon", DEFAULT_THEME["color_icon"]),
        "icon_style": icon_style,
        "icon_radius": {"rounded": "12px", "soft": "20px", "sharp": "4px"}.get(icon_style, "12px"),
        "presets": [
            {"id": k, **v}
            for k, v in THEME_PRESETS.items()
        ],
    }


def settings_for_api() -> Dict[str, Any]:
    ctx = get_theme_context()
    return {
        "theme_preset": ctx["preset"],
        "color_primary": ctx["primary"],
        "color_accent": ctx["accent"],
        "color_secondary": ctx["secondary"],
        "color_icon": ctx["icon"],
        "icon_style": ctx["icon_style"],
        "presets": ctx["presets"],
    }