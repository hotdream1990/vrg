"""Repository cấu hình hệ thống (app_config) — admin chỉnh trên UI.

Secret (mật khẩu, proxy) KHÔNG bao giờ trả giá trị thật ra API — chỉ trả trạng thái đã đặt.
Crawler marketscreener đọc trực tiếp bảng này (ưu tiên hơn .env).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

# Khóa hiển thị trên trang Cấu hình. secret=True → API mask, không lộ giá trị.
CONFIG_SPEC = [
    {"key": "MARKETSCREENER_USER", "label": "Tài khoản marketscreener", "secret": False,
     "placeholder": "ttkd@vrg.vn"},
    {"key": "MARKETSCREENER_PASS", "label": "Mật khẩu marketscreener", "secret": True,
     "placeholder": "••••••••"},
    {"key": "MARKETSCREENER_PROXY", "label": "Proxy residential (tùy chọn)", "secret": True,
     "placeholder": "http://user:pass@host:port"},
]
_KEYS = {c["key"]: c for c in CONFIG_SPEC}
_CLEAR = "__CLEAR__"


def _display(value: str | None, secret: bool) -> str | None:
    """Secret → không lộ (chỉ báo đã đặt); non-secret → trả thẳng."""
    if not value:
        return None
    return "•••••• (đã đặt)" if secret else value


def list_config() -> list[dict[str, Any]]:
    """Cấu hình đã MASK cho UI admin (secret không lộ giá trị)."""
    ensure_schema()
    with session_scope() as db:
        stored = {r[0]: r[1] for r in db.execute(text("SELECT key, value FROM app_config")).all()}
    return [
        {
            "key": c["key"], "label": c["label"], "secret": c["secret"],
            "placeholder": c["placeholder"],
            "is_set": bool(stored.get(c["key"])),
            "display": _display(stored.get(c["key"]), c["secret"]),
        }
        for c in CONFIG_SPEC
    ]


def set_config(updates: dict[str, str], by: str | None = None) -> int:
    """Upsert các khóa hợp lệ. Ô để trống/None → BỎ QUA (giữ giá trị cũ).

    Truyền giá trị '__CLEAR__' để xóa một khóa.
    """
    ensure_schema()
    n = 0
    with session_scope() as db:
        for key, raw in updates.items():
            if key not in _KEYS or raw is None or raw == "":
                continue
            value = "" if raw == _CLEAR else raw
            db.execute(
                text("""
                    INSERT INTO app_config (key, value, is_secret, updated_by)
                    VALUES (:k, :v, :s, :by)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by
                """),
                {"k": key, "v": value, "s": _KEYS[key]["secret"], "by": by},
            )
            n += 1
    return n
