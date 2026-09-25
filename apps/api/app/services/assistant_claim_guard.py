"""Hàng rào: Trợ lý NÓI đã chỉnh phương án nháp nhưng lượt đó không có công cụ phương án nào chạy
thành công.

Đo trên prod 25/09/2026 (0.4.88, LLM thật): 2/8 lượt trả lời "đã hoàn tác" / "đã đưa vào bảng
phương án" mà không gọi công cụ — bảng không đổi, người dùng tin là đã đổi. Luật trong prompt
("chỉ nói đã chỉnh khi công cụ thành công") không đủ chắc ⇒ kiểm bằng code sau khi LLM trả lời:
1. lần đầu phát hiện → trả lời bị gạt đi, LLM phải gọi một công cụ phương án (tool_choice=required,
   chỉ để lại 2 công cụ đó — đo thực tế: chỉ nhắc thì có lượt nó xin lỗi rồi vẫn không làm);
2. vẫn sai → giữ câu trả lời nhưng nối thêm lời đính chính (không để người dùng hiểu sai).

Chỉ xét khi câu hỏi CÓ dạng yêu cầu chỉnh (tăng/giảm/đặt/hoàn tác/đưa vào bảng…) VÀ câu trả lời có
câu vừa khẳng định đã làm vừa nhắc tới phương án/bản nháp/bảng — "SHFE đã tăng 8%" không bị bắt.
"""
from __future__ import annotations

import re

_REQUEST = re.compile(
    r"tăng|giảm|đặt|hoàn tác|bỏ lần|bỏ thay đổi|đưa (?:vào|về|lên|luôn)|lập (?:lại )?(?:phương án|bảng|bản nháp)"
    r"|chỉnh|nâng|hạ |giữ như|làm lại|vào bảng|như mô hình", re.IGNORECASE)
_CLAIM = re.compile(
    r"\bđã\s+(?:được\s+)?(?:hoàn tác|chỉnh|tăng|giảm|đặt|lập|đưa|cập nhật|điều chỉnh|sửa|bỏ|thêm|áp)",
    re.IGNORECASE)
_TARGET = re.compile(r"bản nháp|phương án|bảng", re.IGNORECASE)
#: Yêu cầu RÕ RÀNG phải chỉnh bảng — đo thực tế LLM có lượt không gọi công cụ mà cũng không nói dối
#: (chỉ trả lời suông), nên với những câu này không cần đợi câu khẳng định sai mới bắt làm lại.
_EXPLICIT = re.compile(
    r"hoàn tác|bỏ lần|vào bảng|lập (?:lại )?(?:phương án|bảng|bản nháp)"
    r"|(?:tăng|giảm|nâng|hạ)[^.?!\n]{0,30}(?:tí|chút|ít)\b",   # "tăng lên tí xíu", KHÔNG bắt "giải thích một chút"
    re.IGNORECASE)
#: Công cụ được phép (và BẮT BUỘC gọi một trong số đó) ở lượt làm lại.
PROPOSAL_TOOLS = ("create_floor_proposal", "adjust_floor_proposal")
_SENTENCE = re.compile(r"[^.!?\n]+")

def retry_message(question: str) -> str:
    """Lời nhắc ở lượt làm lại — nêu đúng yêu cầu của người dùng và cách làm từng loại.

    Đo prod 0.4.89: bản cũ chỉ lấy ví dụ "hoàn tác = undo" nên với câu "đưa luôn vào bảng" LLM bị ép
    gọi công cụ đã chọn nhầm undo, rồi trả lời "chưa có gì để hoàn tác" và mất luôn phần phân tích.
    """
    return (
        "KIỂM TRA TỰ ĐỘNG: trong lượt này CHƯA có công cụ create_floor_proposal/adjust_floor_proposal "
        f"nào chạy thành công — bảng phương án CHƯA đổi. Yêu cầu của người dùng: «{question[:300]}». "
        "Gọi ĐÚNG một công cụ để làm đúng yêu cầu đó: đưa mức bạn vừa đề xuất vào bảng = "
        "adjust_floor_proposal op set đúng mức đề xuất cho chủng loại đó (chưa có phương án thì công "
        "cụ tự lập; mức đề xuất trùng mức mô hình thì create_floor_proposal base model); lập phương án "
        "= create_floor_proposal; tăng/giảm/đặt = adjust_floor_proposal op step/percent/amount/set; "
        "CHỈ dùng op undo khi người dùng xin hoàn tác/bỏ lần vừa rồi. Sau đó trả lời lại ĐẦY ĐỦ: giữ "
        "nguyên phần phân tích/số liệu của câu trả lời trước nếu vẫn đúng, cộng kết quả công cụ.")

CORRECTION = ("\n\n_Lưu ý: phương án nháp **chưa thay đổi** trong lượt này. Anh/chị nhắn lại yêu cầu "
              "hoặc sửa trực tiếp trên bảng phương án._")


def is_change_request(question: str) -> bool:
    return bool(_REQUEST.search(question or ""))


def claims_change(answer: str) -> bool:
    """Có câu nào vừa khẳng định 'đã <làm gì>' vừa nói tới phương án/bản nháp/bảng không."""
    return any(_CLAIM.search(s) and _TARGET.search(s) for s in _SENTENCE.findall(answer or ""))


def false_claim(question: str, answer: str, changed: bool) -> bool:
    """Trả lời khẳng định đã chỉnh phương án trong khi lượt này không có thay đổi thật."""
    return not changed and is_change_request(question) and claims_change(answer)


def needs_retry(question: str, answer: str, changed: bool) -> bool:
    """Phải bắt làm lại: báo sai là đã chỉnh, HOẶC yêu cầu rõ ràng mà chưa chỉnh gì."""
    return false_claim(question, answer, changed) or (not changed and bool(_EXPLICIT.search(question or "")))
