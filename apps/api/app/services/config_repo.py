"""Repository cấu hình hệ thống (app_config) — admin chỉnh trên UI.

Secret (mật khẩu, khóa API) KHÔNG bao giờ trả giá trị thật ra API — chỉ trả trạng thái đã đặt.
Crawler marketscreener đọc trực tiếp bảng này (ưu tiên hơn .env).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.db import ensure_schema, session_scope

# Nhóm cấu hình → mỗi nhóm là 1 tab trên UI (thêm nhóm mới = thêm tab). Thứ tự = thứ tự tab.
CONFIG_GROUPS = [
    {"id": "marketscreener", "label": "Marketscreener"},
    {"id": "ai", "label": "AI / LLM"},
]

# Khóa hiển thị trên trang Cấu hình. secret=True → API mask, không lộ giá trị.
# options (tùy chọn) → render dropdown thay vì ô nhập.
CONFIG_SPEC = [
    {"key": "MARKETSCREENER_USER", "group": "marketscreener", "label": "Tài khoản marketscreener",
     "secret": False, "placeholder": "ttkd@vrg.vn"},
    {"key": "MARKETSCREENER_PASS", "group": "marketscreener", "label": "Mật khẩu marketscreener",
     "secret": True, "placeholder": "••••••••"},
    # provider=... → chỉ hiện khi LLM_PROVIDER khớp (form hiển thị key+model đúng nhà cung cấp).
    {"key": "LLM_PROVIDER", "group": "ai", "label": "Nhà cung cấp LLM", "secret": False,
     "placeholder": "openai", "options": ["openai"]},
    {"key": "OPENAI_API_KEY", "group": "ai", "provider": "openai", "label": "OpenAI API Key",
     "secret": True, "placeholder": "sk-..."},
    {"key": "OPENAI_MODEL", "group": "ai", "provider": "openai", "label": "Model OpenAI",
     "secret": False, "placeholder": "Chọn model"},  # options nạp động từ tài khoản
    {"key": "ANTHROPIC_API_KEY", "group": "ai", "provider": "anthropic", "label": "Anthropic API Key",
     "secret": True, "placeholder": "sk-ant-..."},
    {"key": "ANTHROPIC_MODEL", "group": "ai", "provider": "anthropic", "label": "Model Anthropic",
     "secret": False, "placeholder": "Chọn model",
     "options": ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]},
]

# Model OpenAI gợi ý khi chưa có key (sau khi đặt key → lấy danh sách thật từ tài khoản).
_OPENAI_MODEL_FALLBACK = ["gpt-5.4-mini", "gpt-5.4", "gpt-4o-mini", "gpt-4o"]


def list_openai_models() -> list[str]:
    """Danh sách model OpenAI cho dropdown. Có key → lấy THẬT từ tài khoản; không thì fallback."""
    key = get_value("OPENAI_API_KEY") or (settings.openai_api_key or None)
    if not key:
        return _OPENAI_MODEL_FALLBACK
    try:
        from openai import OpenAI
        ids = [m.id for m in OpenAI(api_key=key).models.list().data
               if m.id.startswith("gpt-") and "instruct" not in m.id]
        return sorted(ids, reverse=True) or _OPENAI_MODEL_FALLBACK
    except Exception:  # noqa: BLE001 - key sai/mạng lỗi → vẫn cho fallback
        return _OPENAI_MODEL_FALLBACK
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
            "placeholder": c["placeholder"], "group": c["group"],
            "options": c.get("options"), "provider": c.get("provider"),
            "is_set": bool(stored.get(c["key"])),
            "display": _display(stored.get(c["key"]), c["secret"]),
        }
        for c in CONFIG_SPEC
    ]


def get_value(key: str, fallback: str | None = None) -> str | None:
    """Lấy giá trị THẬT của 1 khóa cho backend dùng (KHÔNG lộ ra API). Trống → fallback."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT value FROM app_config WHERE key = :k"), {"k": key}).first()
    return (row[0] if row and row[0] else None) or fallback


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
