"""Sinh nhận định AI cho Bản tin biến động — mỗi nhóm 1 câu + đoạn tổng thể.

Nhận tóm tắt số liệu các nhóm (frontend đã tính), dựng prompt, gọi LLM 1 lượt, parse JSON.
Không lưu DB — mỗi lần bấm tạo mới. Lỗi cấu hình LLM → raise llm.LLMNotConfigured (router trả 400).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.services import llm

_SYSTEM = (
    "Bạn là chuyên viên phân tích thị trường của Ban Thị trường Kinh doanh, Tập đoàn Công "
    "nghiệp Cao su Việt Nam (VRG). Nhiệm vụ: viết nhận định NGẮN GỌN, khách quan, tiếng Việt, "
    "phục vụ lãnh đạo đọc nhanh tình hình biến động thị trường. "
    "CHỈ dựa trên số liệu được cung cấp — TUYỆT ĐỐI không bịa thêm số liệu, mốc thời gian hay "
    "sự kiện ngoài dữ liệu. Nếu một nhóm chưa có số liệu, ghi ngắn gọn 'Chưa đủ dữ liệu để nhận định.'"
)


def _build_user(groups: list[dict[str, Any]]) -> str:
    blocks = []
    for g in groups:
        blocks.append(f"### [{g.get('key')}] {g.get('label')}\n{(g.get('summary') or '(trống)').strip()}")
    keys = ", ".join(f'"{g.get("key")}"' for g in groups)
    return (
        "Dưới đây là tóm tắt số liệu thị trường theo từng NHÓM (đã tính sẵn xu hướng/%thay đổi):\n\n"
        + "\n\n".join(blocks)
        + "\n\n---\nYêu cầu:\n"
        "- Với MỖI nhóm ở trên, viết ĐÚNG 1 câu nhận định (nêu xu hướng chính + hàm ý cho giá cao su/điều hành).\n"
        "- Sau đó viết 1 đoạn 'Tổng thể' 2–3 câu tổng hợp bức tranh chung các nhóm.\n"
        "- Văn phong báo cáo nội bộ, súc tích, không markdown, không lặp lại số liệu thô quá nhiều.\n"
        "- Chỉ dùng thông tin CÓ trong số liệu; không thêm sự kiện bên ngoài.\n\n"
        "CHỈ trả về JSON hợp lệ đúng định dạng (không kèm giải thích, không bọc ```):\n"
        '{"groups": {' + keys + '}, "overall": "..."}\n'
        "trong đó value mỗi key nhóm là câu nhận định của nhóm đó."
    )


def _parse_json(raw: str) -> dict[str, Any]:
    """Bóc JSON từ output LLM (chịu được trường hợp bọc ```json ... ```)."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.S)
    if fence:
        text = fence.group(1)
    else:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            text = m.group(0)
    return json.loads(text)


def generate(groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Sinh nhận định cho các nhóm + tổng thể. Trả {groups:[{key,label,assessment}], overall, generated_at}."""
    out_raw = llm.complete(_SYSTEM, _build_user(groups), max_tokens=1100)
    parsed = _parse_json(out_raw)
    by_key = parsed.get("groups") if isinstance(parsed.get("groups"), dict) else {}
    result_groups = [
        {"key": g.get("key"), "label": g.get("label"),
         "assessment": str(by_key.get(g.get("key"), "")).strip()}
        for g in groups
    ]
    return {
        "groups": result_groups,
        "overall": str(parsed.get("overall", "")).strip(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
