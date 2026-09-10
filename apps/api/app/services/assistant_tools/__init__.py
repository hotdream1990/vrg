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
    contract_tools, floor_tools, internal_tools, market_tools, unit_tools,
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
    "contract": {"label": "Hợp đồng & khách hàng", "cap": "sales_contract", "core": False,
                 "desc": "Cam kết · đã giao · đã ký chưa giao · doanh thu · khách hàng · hợp đồng mẹ"},
}

_MODULES = {"market": market_tools, "floor": floor_tools, "internal": internal_tools,
            "unit": unit_tools, "contract": contract_tools}

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


#: Những việc Trợ lý CHƯA làm được — hiện thẳng trên giao diện để người dùng không kỳ vọng nhầm
#: rồi tưởng hệ thống trả lời sai. Cập nhật danh sách này mỗi khi mở thêm khả năng mới.
LIMITS: list[str] = [
    "Chỉ ĐỌC số liệu — không nhập, không sửa, không ghi khuyến nghị vào biểu giá sàn.",
    "Chưa trả lời được câu hỏi quy trình/nghiệp vụ (vd 'quy trình ban hành giá sàn thế nào') — "
    "mới tra được số, chưa tra được tài liệu nội bộ.",
    "Chưa có dữ liệu ngoài hệ thống: dầu thô, cao su tổng hợp, tin vĩ mô thế giới.",
    "Bản tin/báo cáo chỉ đọc được bản ĐÃ LƯU; bản đang dựng dở trên màn hình thì chưa thấy.",
    "Không tự dự báo giá tương lai — mọi mức đề xuất đều từ mô hình hồi quy trên lịch sử ban hành.",
    "Mỗi câu hỏi tra tối đa 400 ngày dữ liệu.",
]

#: Nhãn ngắn tiếng Việt của từng công cụ — dùng cho bảng "Trợ lý làm được gì?" trên giao diện.
#: Để ở SERVER, cạnh registry, thay vì chép sang frontend: đổi tên/ thêm công cụ chỉ sửa một nơi.
#: Thiếu nhãn thì frontend tự rút gọn `desc`, không bao giờ hiện tên hàm cho người dùng.
TOOL_LABELS: dict[str, str] = {
    # Thị trường thế giới
    "get_exchange_prices": "Giá các sàn quốc tế mới nhất",
    "get_price_trend": "Diễn biến giá một sàn theo ngày",
    "get_fx_rates": "Tỷ giá và diễn biến tỷ giá",
    "get_physical_prices": "Giá physical châu Á (USD/tấn)",
    # Giá sàn & tư vấn
    "get_floor_prices": "Giá sàn Tập đoàn hiện hành",
    "get_floor_history": "Lịch sử các lần ban hành giá sàn",
    "suggest_floor_adjustment": "Gợi ý nâng/giữ/hạ giá sàn",
    "simulate_floor_scenarios": "Kịch bản giá sàn khi thị trường biến động",
    "get_floor_context": "Tín hiệu bối cảnh quanh quyết định giá sàn",
    # Nội bộ Tập đoàn
    "get_inventory_trend": "Tồn kho thành phẩm theo tuần",
    "get_market_quote": "Báo giá mủ thị trường",
    "get_raw_material_prices": "Giá thu mua mủ nguyên liệu",
    "get_latest_bulletin": "Bản tin / báo cáo đã phát hành",
    "get_data_freshness": "Dữ liệu cập nhật tới ngày nào",
    # Đơn vị thành viên
    "get_unit_purchase": "Sản lượng và giá thu mua của đơn vị",
    "get_unit_consumption": "Tiêu thụ và doanh thu của đơn vị",
    "get_unit_stock": "Tồn kho của đơn vị tại một ngày",
    "get_unit_plan_progress": "Tiến độ kế hoạch năm",
    "get_submission_status": "Đơn vị nào chưa nộp báo cáo",
    # Hợp đồng & khách hàng
    "get_undelivered_volume": "Đã ký hợp đồng nhưng chưa giao",
    "get_contract_deliveries": "Các đợt giao hàng trong kỳ",
    "get_contract_summary": "Hợp đồng ký mới trong kỳ",
    "get_top_customers": "Khách hàng mua nhiều nhất",
    "get_master_contracts": "Hợp đồng mẹ và tiến độ",
}

#: Số ký tự tối đa của mô tả công cụ hiển thị cho người dùng (mô tả gốc viết cho mô hình nên dài).
_DESC_LIMIT = 200


def _short_desc(description: str) -> str:
    """Câu đầu của mô tả công cụ — đủ để người dùng hiểu công cụ đó tra ra cái gì."""
    text = " ".join(description.split())
    head = text.split(". ")[0].rstrip(".")
    return head if len(head) <= _DESC_LIMIT else head[:_DESC_LIMIT].rsplit(" ", 1)[0] + "…"


def pack_summary(caps: dict[str, str] | None = None,
                 enabled: list[str] | None = None) -> list[dict[str, Any]]:
    """Mô tả các gói cho frontend: chip chọn nhóm + bảng "Trợ lý làm được gì".

    `items` liệt kê từng công cụ để người dùng biết chính xác Trợ lý chạm tới dữ liệu nào —
    kể cả gói đang tắt/không đủ quyền (biết là CÓ tính năng đó, chỉ chưa dùng được).
    """
    on = set(allowed_packs(caps, enabled))
    return [{"key": k, "label": m["label"], "desc": m["desc"], "core": m["core"],
             "active": k in on, "cap": m["cap"],
             "tools": sum(1 for t in TOOLS.values() if t["pack"] == k),
             "items": [{"name": n, "label": TOOL_LABELS.get(n, ""),
                        "desc": _short_desc(t["schema"]["description"])}
                       for n, t in TOOLS.items() if t["pack"] == k]}
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
