"""Repository cấu hình hệ thống (app_config) — admin chỉnh trên UI.

Secret (mật khẩu, khóa API) KHÔNG bao giờ trả giá trị thật ra API — chỉ trả trạng thái đã đặt.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.db import ensure_schema, session_scope
from app.services import audit_repo

# Nhóm cấu hình → mỗi nhóm là 1 tab trên UI (thêm nhóm mới = thêm tab). Thứ tự = thứ tự tab.
CONFIG_GROUPS = [
    {"id": "ai", "label": "AI / LLM"},
    {"id": "public", "label": "Link công khai"},
    {"id": "email", "label": "Email"},
    {"id": "data_entry", "label": "Cửa sổ nhập liệu"},
]

# Khóa hiển thị trên trang Cấu hình. secret=True → API mask, không lộ giá trị.
# options (tùy chọn) → render dropdown thay vì ô nhập.
CONFIG_SPEC = [
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
    # Mật khẩu cho link công khai để đơn vị thành viên tự nhập giá mủ nước (chưa đặt = link bị khoá).
    {"key": "PUBLIC_PURCHASE_PASSWORD", "group": "public", "label": "Mật khẩu nhập giá mủ (link công khai)",
     "secret": True, "placeholder": "Đặt mật khẩu để phát cho các đơn vị (bỏ trống = khoá link)"},
    # Email thông báo (Hỗ trợ & Thông báo · Nhắc lịch). Chưa khai = hệ thống vẫn chạy, chỉ không
    # gửi mail — tin vẫn hiện trên trang cho đơn vị (xem app/services/mailer.py).
    {"key": "SMTP_HOST", "group": "email", "label": "Máy chủ SMTP", "secret": False,
     "placeholder": "vd smtp.gmail.com — bỏ trống = tắt gửi email"},
    {"key": "SMTP_PORT", "group": "email", "label": "Cổng SMTP", "secret": False,
     "placeholder": "587 (STARTTLS) · 465 (SSL)"},
    {"key": "SMTP_SECURITY", "group": "email", "label": "Bảo mật kết nối", "secret": False,
     "placeholder": "starttls", "options": ["starttls", "ssl", "none"]},
    {"key": "SMTP_USER", "group": "email", "label": "Tài khoản SMTP", "secret": False,
     "placeholder": "địa chỉ email đăng nhập máy chủ mail"},
    {"key": "SMTP_PASSWORD", "group": "email", "label": "Mật khẩu SMTP", "secret": True,
     "placeholder": "mật khẩu ứng dụng của hộp thư gửi"},
    {"key": "SMTP_FROM", "group": "email", "label": "Email người gửi", "secret": False,
     "placeholder": "vd thongbao@vrg.vn — bỏ trống thì lấy tài khoản SMTP"},
    {"key": "SMTP_SENDER_NAME", "group": "email", "label": "Tên hiển thị người gửi", "secret": False,
     "placeholder": "Hệ thống VRG"},
    {"key": "APP_BASE_URL", "group": "email", "label": "Địa chỉ hệ thống (dùng dựng link trong email)",
     "secret": False, "placeholder": "vd https://vrg.bizino.vn — thiếu thì email không có link vào xem"},
    # Cửa sổ nhập liệu — số ngày gần nhất được nhập/sửa; ngày cũ hơn chuyển sang chỉ xem. Mặc định 7.
    {"key": "MEMBER_EDIT_WINDOW_DAYS", "group": "data_entry", "secret": False,
     "label": "Số ngày sửa được — Giá mủ đơn vị (tài khoản đơn vị thành viên)",
     "placeholder": "Mặc định 7 — số ngày gần nhất được nhập/sửa (0 = chỉ hôm nay)"},
    {"key": "EDITOR_EDIT_WINDOW_DAYS", "group": "data_entry", "secret": False,
     "label": "Số ngày sửa được — chuyên viên nhập liệu (Giá mủ nguyên liệu · Physical · Tồn kho · Báo giá)",
     "placeholder": "Mặc định 7 — số ngày gần nhất được nhập/sửa (0 = chỉ hôm nay); admin không bị giới hạn"},
    # Phạm vi RÀ của bảng nhắc việc — khác cửa sổ sửa ở trên: rà xa hơn thì đơn vị thấy cả những
    # ngày đã khoá mà mình còn nợ (nhờ Ban TTKD nhập hộ), rà ngắn lại thì bảng gọn.
    {"key": "MEMBER_ALERT_DAYS", "group": "data_entry", "secret": False,
     "label": "Cảnh báo thiếu số liệu — rà bao nhiêu ngày gần nhất (đơn vị thành viên)",
     "placeholder": "Mặc định 14 — tính cả hôm nay (vd 30, 300). Đặt 0 = TẮT cảnh báo"},
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


def set_value(key: str, value: str, by: str | None = None) -> None:
    """Ghi 1 khoá cấu hình KHÔNG nằm trên trang admin (tính năng tự cấu hình trong màn nghiệp vụ).

    `set_config` cố tình chỉ nhận khoá khai trong `CONFIG_SPEC` (form admin), nên công tắc do
    chuyên viên bật/tắt ngay trong màn của mình đi đường này. Luôn coi là KHÔNG bí mật — đừng
    dùng cho mật khẩu/API key (những thứ đó phải khai ở `CONFIG_SPEC` để API mask giá trị).
    """
    ensure_schema()
    with session_scope() as db:
        old = db.execute(text("SELECT value FROM app_config WHERE key = :k"), {"k": key}).scalar()
        db.execute(
            text("""
                INSERT INTO app_config (key, value, is_secret, updated_by)
                VALUES (:k, :v, false, :by)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by
            """),
            {"k": key, "v": value, "by": by},
        )
    if old != value:
        audit_repo.log("config", "update", key, before={"value": old}, after={"value": value})


def set_config(updates: dict[str, str], by: str | None = None) -> int:
    """Upsert các khóa hợp lệ. Ô để trống/None → BỎ QUA (giữ giá trị cũ).

    Truyền giá trị '__CLEAR__' để xóa một khóa.
    """
    ensure_schema()
    n = 0
    changes: list[tuple[str, bool, str | None, str]] = []
    with session_scope() as db:
        for key, raw in updates.items():
            if key not in _KEYS or raw is None or raw == "":
                continue
            value = "" if raw == _CLEAR else raw
            secret = _KEYS[key]["secret"]
            old = db.execute(text("SELECT value FROM app_config WHERE key = :k"),
                             {"k": key}).scalar()
            db.execute(
                text("""
                    INSERT INTO app_config (key, value, is_secret, updated_by)
                    VALUES (:k, :v, :s, :by)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by
                """),
                {"k": key, "v": value, "s": secret, "by": by},
            )
            changes.append((key, bool(secret), old, value))
            n += 1
    for key, secret, old, value in changes:
        # Khoá bí mật (API key, mật khẩu…) chỉ ghi "đã đổi", KHÔNG bao giờ ghi giá trị.
        audit_repo.log(
            "config", "update", key,
            before=None if secret else {"value": old},
            after=None if secret else {"value": value},
            note="Giá trị bí mật — chỉ ghi nhận có thay đổi" if secret else None,
        )
    return n
