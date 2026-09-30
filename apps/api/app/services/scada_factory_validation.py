"""Kiểm + chuẩn hoá form cấu hình kết nối SCADA của nhà máy (tách khỏi `scada_factory_repo` cho gọn).

Tag / linked server / database đi thẳng vào chuỗi OPENQUERY nên phải qua regex nghiêm ở đây
(lớp 1) và kiểm lại lúc dựng câu truy vấn (lớp 2, `scada_historian_sql`).
"""

from __future__ import annotations

from typing import Any

from app.services import scada_plant_layout as plant_layout
from app.services.scada_historian_sql import valid_ident, valid_tag


def _text(value: Any, label: str, max_len: int, *, spaces: bool = False) -> str:
    """Ô chữ bắt buộc. `spaces=False` (host, tài khoản) → không cho khoảng trắng bên trong."""
    s = value.strip() if isinstance(value, str) else ""
    if not s:
        raise ValueError(f"{label} không được để trống.")
    if len(s) > max_len or (not spaces and any(ch.isspace() for ch in s)):
        raise ValueError(f"{label} không hợp lệ (tối đa {max_len} ký tự"
                         f"{'' if spaces else ', không chứa khoảng trắng'}).")
    return s


def _opt_tag(value: Any, label: str) -> str | None:
    s = value.strip() if isinstance(value, str) else ""
    if not s:
        return None
    if not valid_tag(s):
        raise ValueError(f"{label} «{s}» không hợp lệ — chỉ gồm chữ, số, dấu cách giữa tên và "
                         "_ . $ # - (tối đa 128).")
    return s


def _layout_key(value: Any) -> str | None:
    """Sơ đồ vận hành: rỗng = không có sơ đồ; khác rỗng phải là khoá bố cục CÓ THẬT."""
    s = value.strip() if isinstance(value, str) else ""
    if not s:
        return None
    keys = plant_layout.layout_keys()
    if s not in keys:
        raise ValueError(f"Sơ đồ vận hành «{s}» không có — chọn một trong: "
                         f"{', '.join(keys) or '(chưa có sơ đồ nào)'}.")
    return s


def clean(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    """Kiểm + chuẩn hoá dữ liệu form → cột DB. Sai → `ValueError` (câu tiếng Việt, router → 400).

    `password` rỗng/None: tạo mới = lỗi; sửa = giữ mật khẩu cũ (không có khoá `password` ở kết quả).
    Không có khoá `layout_key` trong `data` → kết quả cũng không có (sửa = giữ sơ đồ đang gán).
    """
    out: dict[str, Any] = {
        "name": _text(data.get("name"), "Tên nhà máy", 200, spaces=True),
        "host": _text(data.get("host"), "Máy chủ (host)", 255),
        "username": _text(data.get("username"), "Tài khoản SQL Server", 128),
    }
    port = 1433 if data.get("port") is None else data.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("Cổng phải là số nguyên 1–65535.")
    out["port"] = port
    for key, col, default, label in (("database", "database_name", "Runtime", "Database"),
                                     ("linked_server", "linked_server", "INSQL", "Linked server")):
        val = data.get(key)
        val = (val.strip() if isinstance(val, str) else "") or default
        if not valid_ident(val):
            raise ValueError(f"{label} «{val}» không hợp lệ — chỉ gồm chữ, số và _ (tối đa 128).")
        out[col] = val
    tags = [t.strip() for t in (data.get("energy_tags") or []) if isinstance(t, str) and t.strip()]
    if len(tags) not in (0, 1, 4):
        raise ValueError("Tag điện năng phải có 0, 1 (đã là kWh) hoặc 4 phần tử (thanh ghi R0..R3).")
    out["energy_tags"] = [_opt_tag(t, "Tag điện năng") for t in tags]
    out["water_tag"] = _opt_tag(data.get("water_tag"), "Tag nước")
    out["bales_tag"] = _opt_tag(data.get("bales_tag"), "Tag số bành")
    # Historian coi `abc` và `ABC` là MỘT cột: khai trùng thì hai chỉ số đọc chung một số.
    seen: set[str] = set()
    for tag in (t for t in (*out["energy_tags"], out["water_tag"], out["bales_tag"]) if t):
        if tag.lower() in seen:
            raise ValueError(f"Tag «{tag}» bị khai trùng (không phân biệt hoa thường) — mỗi tag một chỗ.")
        seen.add(tag.lower())
    out["enabled"] = bool(data.get("enabled", True))
    # Form không gửi `layout_key` (vd form cũ chưa có ô này) → không có khoá ở kết quả = giữ nguyên.
    if "layout_key" in data:
        out["layout_key"] = _layout_key(data["layout_key"])
    password = data.get("password")
    if isinstance(password, str) and password != "":
        out["password"] = password
    elif creating:
        raise ValueError("Mật khẩu không được để trống khi thêm nhà máy.")
    return out
