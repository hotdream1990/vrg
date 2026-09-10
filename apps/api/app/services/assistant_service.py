"""Trợ lý AI nội bộ — vòng lặp tool-calling (OpenAI) trên SỐ LIỆU THẬT của VRG.

Nhiệm vụ chính: **truy vấn số liệu nâng cao + hỗ trợ tư vấn điều chỉnh giá sàn**. LLM nhận câu hỏi
tiếng Việt → tự gọi các tool (assistant_tools) để lấy số liệu → tổng hợp câu trả lời + đính kèm
bảng/biểu đồ. KHÔNG bịa số; mọi con số phải từ tool.

Tool được nạp theo GÓI KỸ NĂNG: gói admin bật (`ASSISTANT_PACKS`) ∩ quyền người hỏi ∩ gói người
dùng chọn trong phiên chat.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.core import edit_window
from app.services import assistant_tools, config_repo, llm

logger = logging.getLogger("app.assistant")

MAX_ITERS = 8
CONFIG_KEY = "ASSISTANT_PACKS"

#: Mức tư vấn — "cho phép Trợ lý đi xa tới đâu". Người dùng chọn ngay trên màn chat.
ADVICE_MODES = ("data", "model", "adjusted")
DEFAULT_ADVICE = "model"

#: Ở mức "Chỉ tra số", các công cụ SINH RA KHUYẾN NGHỊ bị gỡ khỏi lượt hỏi — hàng rào kỹ thuật,
#: không chỉ dặn trong prompt (một câu "bỏ qua hướng dẫn trên" là model có thể vượt lời dặn).
_ADVICE_TOOLS = {"suggest_floor_adjustment", "simulate_floor_scenarios", "get_floor_context"}

# Trọng số các yếu tố — đo trên 80 lần ban hành 2024→2026 (xem docs/project/tro-ly-ai-kha-nang.md).
# Đưa vào prompt để LLM biết nhìn cái gì TRƯỚC khi kết luận, thay vì liệt kê đều tay mọi chỉ số.
_FACTOR_RANKING = (
    "THỨ TỰ ẢNH HƯỞNG tới quyết định ĐIỀU CHỈNH giá sàn (đo bằng tương quan trên 80 lần ban hành "
    "2024–2026, hệ số là tương quan với biến động % giữa 2 lần ban hành liên tiếp): "
    "(1) MRB SMR20 r=0,63 · đồng hướng 77%; (2) SGX TSR20 r=0,58 · 76%; (3) Physical SMR20 r=0,50 · "
    "80%; (4) OSE RSS3 r=0,41; (5) MRB SMRCV/LATEX r≈0,39; (6) SGX RSS3 r=0,35. "
    "NEO MẶT BẰNG nhưng KHÔNG giải thích lần điều chỉnh: giá mủ nước (r mức=0,84 nhưng r biến "
    "động chỉ 0,14) — dùng nó để nói 'giá đang ở vùng nào', đừng dùng để giải thích 'lần này chỉnh "
    "bao nhiêu'. PHANH: tồn kho Tập đoàn (r mức=−0,50) và tồn kho đơn vị (r biến động=−0,52, n=18) "
    "— tồn cao thì nghiêng về GIỮ/HẠ dù rổ futures tăng. CƠ HỌC: tỷ giá USD/VND nhân trực tiếp vào "
    "giá nội địa VNĐ/tấn."
)

_REASONING = (
    "KHI TƯ VẤN ĐIỀU CHỈNH GIÁ SÀN, phải LIÊN KẾT các nguồn chứ không đọc rời rạc: "
    "(a) gọi suggest_floor_adjustment để có đề xuất của engine và các chỉ số dẫn hướng; "
    "(b) đối chiếu với diễn biến sàn/physical và tỷ giá; "
    "(c) đối chiếu với tồn kho và số liệu đơn vị thành viên (thu mua · tiêu thụ · tồn kho) nếu "
    "được phép truy cập — tồn kho tăng hoặc tiêu thụ chậm là lý do NGƯỢC lại với rổ futures đang tăng; "
    "(c2) nếu được phép, xem thêm sản lượng ĐÃ KÝ HỢP ĐỒNG CHƯA GIAO: đã ký nhiều mà chưa giao là "
    "áp lực bán còn treo (nghiêng GIỮ/HẠ), đã ký ít so với tồn kho tự do cũng vậy; "
    "(d) nói rõ khi các nguồn MÂU THUẪN nhau và nghiêng về bên nào, vì sao. "
    "Với số liệu đơn vị: người hỏi có thể muốn xem theo TỔNG toàn Tập đoàn, theo KHU VỰC hoặc theo "
    "từng ĐƠN VỊ — chọn mức phù hợp với câu hỏi, mặc định theo khu vực khi hỏi chung."
)

_ADVICE_RULES = {
    # Chỉ tra số — dùng khi người dùng chỉ muốn lấy số liệu, không muốn ý kiến của máy.
    "data": (
        "MỨC TƯ VẤN = CHỈ TRA SỐ. Bạn KHÔNG được đưa ra khuyến nghị nâng/giữ/hạ giá sàn, không "
        "nhận định nên làm gì. Chỉ trả số liệu từ tool, kèm kỳ dữ liệu và nguồn. Nếu người dùng "
        "hỏi nên tăng hay giảm, hãy nói rằng chế độ hiện tại chỉ tra cứu số liệu và mời họ chuyển "
        "sang mức 'Theo mô hình' hoặc 'Có điều chỉnh' ở đầu màn hình."
    ),
    # Theo mô hình — mặc định: trung thành với engine, không tự bịa mức khác.
    "model": (
        "MỨC TƯ VẤN = THEO MÔ HÌNH. Khi được hỏi về điều chỉnh giá sàn, gọi suggest_floor_adjustment "
        "và trình bày ĐÚNG mức đề xuất của mô hình — KHÔNG tự cộng/trừ ra một mức khác. Bạn giải "
        "thích vì sao mô hình đề xuất như vậy dựa trên các chỉ số dẫn hướng, và nêu những yếu tố "
        "bối cảnh đáng lưu ý (tồn kho, tiêu thụ) như GHI CHÚ tham khảo, không đổi con số."
    ),
    # Có điều chỉnh — mức xa nhất: được lệch khỏi engine nhưng phải giải trình bằng số.
    "adjusted": (
        "MỨC TƯ VẤN = CÓ ĐIỀU CHỈNH. Bạn được phép đề xuất mức KHÁC mức của mô hình, theo đúng trình tự: "
        "(1) gọi suggest_floor_adjustment để lấy MỨC NỀN; "
        "(2) gọi get_floor_context để lấy tín hiệu bối cảnh đã lượng hoá; "
        "(3) nếu được phép, gọi thêm các tool số liệu đơn vị thành viên (tồn kho · thu mua · tiêu thụ). "
        "QUY TẮC ĐIỀU CHỈNH: chỉ dùng tín hiệu có trọng số 'bổ sung' (giá mủ chén, tồn kho) và số "
        "liệu đơn vị để lệch khỏi mức nền — tín hiệu trọng số 'mạnh' (rổ futures) ĐÃ nằm trong mô "
        "hình, cộng thêm lần nữa là tính hai lần. Tín hiệu 'nền' (giá mủ nước) chỉ dùng để nói giá "
        "đang ở vùng nào, không dùng để đổi số. "
        "BẮT BUỘC trình bày theo 4 dòng: 'Mức mô hình: …' → 'Điều chỉnh: ±… (…%)' → 'Mức đề xuất: …' "
        "→ 'Căn cứ:' 2–4 gạch đầu dòng, mỗi gạch phải có SỐ THẬT từ tool. "
        "Biên độ điều chỉnh thông thường không quá ±2% so với mức mô hình (biên độ điều chỉnh trung "
        "bình mỗi lần ban hành trong lịch sử là 1,78%); nếu bạn thấy cần lệch nhiều hơn, phải nói rõ "
        "là bất thường và vì sao. Nếu bối cảnh không cho tín hiệu rõ, GIỮ NGUYÊN mức mô hình và nói ra."
    ),
}

SYSTEM = (
    "Bạn là Trợ lý phân tích thị trường cao su của Tập đoàn Công nghiệp Cao su Việt Nam (VRG). "
    "Trả lời NGẮN GỌN, chuyên nghiệp, bằng tiếng Việt. "
    "TUYỆT ĐỐI KHÔNG bịa số liệu: mọi con số/giá/xu hướng phải lấy từ KẾT QUẢ TOOL — nếu chưa có "
    "dữ liệu thì gọi tool phù hợp; nếu tool báo không có dữ liệu thì nói rõ 'chưa có số liệu', "
    "không tự suy đoán con số. KHÔNG lấy số liệu ngày khác đắp cho ngày được hỏi. "
    "Giá ghi 'No Trading' là phiên sàn không giao dịch, KHÔNG phải giá bằng 0. "
    "Luôn nêu ĐƠN VỊ TÍNH đúng như tool trả về (USD/tấn · VNĐ/tấn · đồng/độ · tấn) và KHÔNG tự quy đổi. "
    "Khi hỏi diễn biến/xu hướng → gọi tool chuỗi giá; hỏi giá hiện tại → tool ảnh chụp. "
    "Bạn CHỈ ĐỌC dữ liệu: mọi nhận định/khuyến nghị chỉ hiển thị để tham khảo, KHÔNG ghi vào biểu "
    "giá sàn và không làm thay đổi bất kỳ số liệu nào của hệ thống. "
    + _REASONING + " " + _FACTOR_RANKING + " "
    "Mọi khuyến nghị giá sàn đều là GỢI Ý tham khảo — quyết định cuối thuộc về Ban lãnh đạo. "
    "Khi tool trả bảng/biểu đồ, hệ thống TỰ hiển thị cho người dùng — bạn chỉ diễn giải ý nghĩa, "
    "không liệt kê lại toàn bộ số trong bảng. Nêu rõ kỳ dữ liệu (ngày/tuần) khi trả lời. "
    f"Hôm nay là {edit_window.today().isoformat()}."
)


def system_prompt(advice: str) -> str:
    """Prompt hệ thống + luật của MỨC TƯ VẤN đang chọn."""
    return SYSTEM + " " + _ADVICE_RULES.get(advice, _ADVICE_RULES[DEFAULT_ADVICE])


def enabled_packs() -> list[str] | None:
    """Gói admin bật ở Cấu hình hệ thống (CSV). Chưa đặt → None = bật tất cả.

    Đã đặt nhưng gõ sai hết (vd "iternal") → trả `[]` chứ KHÔNG phải None: admin có ý định giới
    hạn, gõ nhầm mà lại bật thêm gói cho mọi người là đảo ngược ý định (fail open).
    """
    raw = (config_repo.get_value(CONFIG_KEY, "") or "").strip()
    if not raw:
        return None
    return [k.strip() for k in raw.split(",") if k.strip() in assistant_tools.PACKS]


def _scope(caps: dict[str, str] | None, packs: list[str] | None) -> list[str] | None:
    """Giao giữa gói admin bật và gói người dùng chọn trong phiên chat."""
    admin = enabled_packs()
    if packs is None:
        return admin
    chosen = [p for p in packs if p in assistant_tools.PACKS]
    return [p for p in chosen if admin is None or p in admin]


def packs_for(caps: dict[str, str] | None) -> list[dict[str, Any]]:
    """Mô tả gói cho frontend (chip chọn nhóm dữ liệu)."""
    return assistant_tools.pack_summary(caps, enabled_packs())


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


def _log_turn(session_id: str | None, username: str | None, messages: list[dict[str, str]],
              answer: str, tools: list[str], sources: list[str], packs: list[str] | None,
              advice: str, model: str, started: float) -> None:
    """Ghi 1 lượt vào nhật ký hỏi–đáp. Log hỏng KHÔNG được làm hỏng câu trả lời của người dùng."""
    if not session_id or not username:
        return
    try:
        from app.services import assistant_log_repo  # nạp muộn: nhật ký là tính năng phụ trợ
        question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        assistant_log_repo.log_turn(
            session_id=session_id, username=username, question=question, answer=answer,
            tools=tools, sources=sources, packs=packs, advice=advice, model=model,
            latency_ms=int((time.time() - started) * 1000))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không ghi được nhật ký Trợ lý AI: %s", exc)


def chat(messages: list[dict[str, str]], caps: dict[str, str] | None = None,
         packs: list[str] | None = None, advice: str = DEFAULT_ADVICE,
         session_id: str | None = None, username: str | None = None) -> dict[str, Any]:
    """Chạy 1 lượt hỏi–đáp (kèm lịch sử). Trả {answer, artifacts, sources}."""
    provider = (config_repo.get_value("LLM_PROVIDER", "openai") or "openai").lower()
    if provider != "openai":
        raise llm.LLMNotConfigured(
            "Trợ lý AI hiện chỉ hỗ trợ OpenAI (cần function-calling). "
            "Vào Quản trị → Cấu hình hệ thống → tab AI, đặt LLM_PROVIDER=openai."
        )
    client, model = llm.openai_client()
    advice = advice if advice in ADVICE_MODES else DEFAULT_ADVICE
    scope = _scope(caps, packs)
    started = time.time()
    convo: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(advice)}]
    convo += [{"role": m["role"], "content": m["content"]} for m in messages
              if m.get("role") in ("user", "assistant") and m.get("content")]
    tools = assistant_tools.openai_tools(caps, scope)
    if advice == "data":
        tools = [t for t in tools if t["function"]["name"] not in _ADVICE_TOOLS]
    artifacts: list[dict] = []
    sources: list[str] = []
    used: list[str] = []

    for _ in range(MAX_ITERS):
        resp = client.chat.completions.create(
            model=model, messages=convo, tools=tools, tool_choice="auto",
            max_completion_tokens=1500,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            answer = (msg.content or "").strip()
            _log_turn(session_id, username, messages, answer, used, _dedup(sources),
                      scope, advice, model, started)
            return {"answer": answer, "artifacts": artifacts, "sources": _dedup(sources)}
        # Ghi lại lượt assistant kèm tool_calls rồi thực thi từng tool.
        convo.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            used.append(tc.function.name)
            if advice == "data" and tc.function.name in _ADVICE_TOOLS:
                res = {"summary": {"error": "Chế độ 'Chỉ tra số' không dùng công cụ khuyến nghị. "
                                            "Hãy trả lời bằng số liệu và mời người dùng chuyển mức tư vấn."}}
            else:
                res = assistant_tools.run_tool(tc.function.name, _parse_args(tc.function.arguments),
                                               caps, scope)
            if res.get("artifact"):
                artifacts.append(res["artifact"])
            if res.get("source"):
                sources.append(res["source"])
            convo.append({"role": "tool", "tool_call_id": tc.id,
                          "content": json.dumps(res.get("summary", {}), ensure_ascii=False, default=str)})

    answer = "Câu hỏi cần quá nhiều bước tra cứu — anh/chị vui lòng hỏi cụ thể hơn giúp em."
    _log_turn(session_id, username, messages, answer, used, _dedup(sources), scope, advice,
              model, started)
    return {"answer": answer, "artifacts": artifacts, "sources": _dedup(sources)}
