"""Trợ lý AI nội bộ — vòng lặp tool-calling (OpenAI) trên SỐ LIỆU THẬT của VRG.

LLM nhận câu hỏi tiếng Việt → tự gọi các tool (assistant_tools) để lấy số liệu → tổng hợp
câu trả lời + đính kèm bảng/biểu đồ (artifact). KHÔNG bịa số; mọi con số phải từ tool.
"""
from __future__ import annotations

import json
from typing import Any

from app.core import edit_window
from app.services import assistant_tools, config_repo, llm

MAX_ITERS = 6

SYSTEM = (
    "Bạn là Trợ lý phân tích thị trường cao su của Tập đoàn Công nghiệp Cao su Việt Nam (VRG). "
    "Trả lời NGẮN GỌN, chuyên nghiệp, bằng tiếng Việt. "
    "TUYỆT ĐỐI KHÔNG bịa số liệu: mọi con số/giá/xu hướng phải lấy từ KẾT QUẢ TOOL — nếu chưa có "
    "dữ liệu thì gọi tool phù hợp; nếu tool báo không có dữ liệu thì nói rõ 'chưa có số liệu', "
    "không tự suy đoán con số. "
    "Khi hỏi về diễn biến/xu hướng → gọi tool chuỗi giá; hỏi giá hiện tại → tool snapshot; "
    "hỏi NÊN TĂNG/GIẢM/ĐIỀU CHỈNH giá sàn → gọi suggest_floor_adjustment rồi giải thích dựa trên "
    "đề xuất + các chỉ số dẫn hướng (drivers), luôn nhắc đây là GỢI Ý tham khảo, quyết định cuối "
    "thuộc về Ban lãnh đạo. "
    "Khi tool trả bảng/biểu đồ, hệ thống TỰ hiển thị cho người dùng — bạn chỉ cần diễn giải ý nghĩa "
    "(không cần liệt kê lại toàn bộ số trong bảng). Nêu rõ kỳ dữ liệu (ngày/tuần) khi trả lời. "
    f"Hôm nay là {edit_window.today().isoformat()}."
)


def _parse_args(raw: str | None) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _dedup(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Chạy 1 lượt hỏi–đáp (kèm lịch sử hội thoại). Trả {answer, artifacts, sources}."""
    provider = (config_repo.get_value("LLM_PROVIDER", "openai") or "openai").lower()
    if provider != "openai":
        raise llm.LLMNotConfigured(
            "Trợ lý AI hiện chỉ hỗ trợ OpenAI (cần function-calling). "
            "Vào Quản trị → Cấu hình hệ thống → tab AI, đặt LLM_PROVIDER=openai."
        )
    client, model = llm.openai_client()
    convo: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
    convo += [{"role": m["role"], "content": m["content"]} for m in messages
              if m.get("role") in ("user", "assistant") and m.get("content")]
    tools = assistant_tools.openai_tools()
    artifacts: list[dict] = []
    sources: list[str] = []

    for _ in range(MAX_ITERS):
        resp = client.chat.completions.create(
            model=model, messages=convo, tools=tools, tool_choice="auto",
            max_completion_tokens=1500,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"answer": (msg.content or "").strip(), "artifacts": artifacts, "sources": _dedup(sources)}
        # Ghi lại lượt assistant kèm tool_calls rồi thực thi từng tool.
        convo.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            res = assistant_tools.run_tool(tc.function.name, _parse_args(tc.function.arguments))
            if res.get("artifact"):
                artifacts.append(res["artifact"])
            if res.get("source"):
                sources.append(res["source"])
            convo.append({"role": "tool", "tool_call_id": tc.id,
                          "content": json.dumps(res.get("summary", {}), ensure_ascii=False, default=str)})

    return {"answer": "Câu hỏi cần quá nhiều bước tra cứu — anh/chị vui lòng hỏi cụ thể hơn giúp em.",
            "artifacts": artifacts, "sources": _dedup(sources)}
