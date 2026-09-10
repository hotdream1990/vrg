"""Bộ công cụ Trợ lý AI — chia theo GÓI KỸ NĂNG bật/tắt được.

Mỗi gói là một nhóm công cụ cùng chủ đề; chỉ gói đang bật (và người hỏi đủ quyền) mới được nạp
schema vào lượt gọi LLM. Lợi ích: câu trả lời tập trung hơn, tiết kiệm token, và không lộ nhóm
dữ liệu mà tài khoản đó vốn không có quyền xem.

Thêm công cụ mới = thêm vào `TOOLS` của đúng module gói; không cần sửa file này.
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.permissions import has_cap
from app.services.assistant_tools import (
    floor_tools, internal_tools, market_tools, unit_tools,
)

#: Gói kỹ năng. `cap` = quyền tối thiểu để dùng gói (None = ai vào được Trợ lý cũng dùng được);
#: `core` = gói nền, luôn bật, admin không tắt được (thiếu nó thì Trợ lý mất lý do tồn tại).
PACKS: dict[str, dict[str, Any]] = {
    "market": {"label": "Thị trường thế giới", "cap": None, "core": True,
               "desc": "Sàn quốc tế · giá physical · tỷ giá · diễn biến"},
    "floor": {"label": "Giá sàn & tư vấn điều chỉnh", "cap": None, "core": True,
              "desc": "Giá sàn hiện hành · lịch sử ban hành · gợi ý NÂNG/GIỮ/HẠ · kịch bản"},
    "internal": {"label": "Số liệu nội bộ Tập đoàn", "cap": None, "core": False,
                 "desc": "Giá mủ nguyên liệu · báo giá mủ · tồn kho · bản tin · độ tươi dữ liệu"},
    "unit": {"label": "Đơn vị thành viên", "cap": "unit_daily", "core": False,
             "desc": "Thu mua · tiêu thụ · tồn kho · kế hoạch năm · tình trạng nộp (tổng · khu vực · đơn vị)"},
}

_MODULES = {"market": market_tools, "floor": floor_tools,
            "internal": internal_tools, "unit": unit_tools}

#: {tên tool: {run, schema, pack}} — gộp từ các module gói.
TOOLS: dict[str, dict[str, Any]] = {}
for _pack, _mod in _MODULES.items():
    for _name, _spec in _mod.TOOLS.items():
        TOOLS[_name] = {**_spec, "pack": _pack}


def allowed_packs(caps: dict[str, str] | None = None,
                  enabled: list[str] | None = None) -> list[str]:
    """Các gói dùng được: nằm trong `enabled` (None = tất cả) VÀ người hỏi đủ quyền.

    Gói `core` luôn có mặt — tắt gói nền là Trợ lý không còn trả lời được câu hỏi cơ bản.
    """
    out = []
    for key, meta in PACKS.items():
        if not meta["core"] and enabled is not None and key not in enabled:
            continue
        cap = meta["cap"]
        if cap and not (caps is not None and has_cap(caps, cap)):
            continue
        out.append(key)
    return out


def openai_tools(caps: dict[str, str] | None = None,
                 enabled: list[str] | None = None) -> list[dict]:
    """Schema tool cho OpenAI function-calling, đã lọc theo gói bật + quyền người hỏi."""
    packs = set(allowed_packs(caps, enabled))
    return [{"type": "function", "function": t["schema"]}
            for t in TOOLS.values() if t["pack"] in packs]


def pack_summary(caps: dict[str, str] | None = None,
                 enabled: list[str] | None = None) -> list[dict[str, Any]]:
    """Mô tả các gói cho frontend (chip hiển thị) + trạng thái dùng được hay không."""
    on = set(allowed_packs(caps, enabled))
    return [{"key": k, "label": m["label"], "desc": m["desc"], "core": m["core"],
             "active": k in on, "tools": sum(1 for t in TOOLS.values() if t["pack"] == k)}
            for k, m in PACKS.items()]


def run_tool(name: str, args: dict, caps: dict[str, str] | None = None,
             enabled: list[str] | None = None) -> dict:
    """Thực thi 1 tool. Chặn lần hai theo gói/quyền (LLM có thể gọi tên tool ngoài danh sách)."""
    tool = TOOLS.get(name)
    if not tool:
        return {"summary": {"error": f"Không có công cụ '{name}'."}}
    if tool["pack"] not in set(allowed_packs(caps, enabled)):
        return {"summary": {"error": f"Công cụ '{name}' không nằm trong nhóm dữ liệu được phép."}}
    fn: Callable = tool["run"]
    try:
        return fn(args or {})
    except Exception as exc:  # noqa: BLE001 - lỗi 1 tool không được làm hỏng cả lượt hỏi
        return {"summary": {"error": f"Lỗi khi chạy '{name}': {exc}"}}
