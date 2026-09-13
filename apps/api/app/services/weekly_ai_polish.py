"""Soát văn AI Báo cáo tuần sau khi sinh: dòng còn TỪ TUYỆT ĐỐI hoặc CHỮ TIẾNG ANH sót → nhờ AI viết lại
đúng dòng đó (1 lượt cho cả báo cáo). Prompt đã dặn nhưng thực tế vẫn lọt ("hoàn toàn", "firm").

An toàn số liệu: chỉ nhận dòng viết lại khi GIỮ NGUYÊN mọi con số và ký hiệu đầu dòng (>, >>, -, **…**);
lệch → giữ dòng gốc (cảnh báo vẫn hiện để chuyên viên sửa tay). AI lỗi → trả nguyên văn, không làm hỏng lượt.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services import llm
from app.services.weekly_number_check import absolute_words, english_words

logger = logging.getLogger(__name__)

MAX_TOKENS_POLISH = 1500
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
_LEAD_RE = re.compile(r"^\s*(>>|>|-)?\s*(\*\*[^*]+\*\*)?")
_ITEM_RE = re.compile(r"^\s*\[(\d+)\]\s?(.*)$")

_SYSTEM = ("Bạn là biên tập viên báo cáo thị trường cao su bằng tiếng Việt. Chỉ sửa câu chữ theo yêu cầu, "
           "không thêm/bớt ý, không đổi con số.")


def needs_polish(line: str) -> bool:
    return bool(absolute_words([line]) or english_words([line]))


def _signature(line: str) -> tuple[list[str], str]:
    """(dãy số theo thứ tự, phần mở đầu dòng) — phải giữ nguyên sau khi viết lại."""
    lead = _LEAD_RE.match(line)
    return _NUM_RE.findall(line), (lead.group(0).strip() if lead else "")


def accept(original: str, rewritten: str | None) -> str:
    """Nhận bản viết lại khi còn nội dung, giữ nguyên số + ký hiệu đầu dòng và đã hết lỗi; không thì giữ gốc."""
    new = (rewritten or "").strip()
    if not new or _signature(new) != _signature(original) or needs_polish(new):
        return original
    return new


def _prompt(items: list[str]) -> str:
    listing = "\n".join(f"[{i}] {s}" for i, s in enumerate(items))
    return (
        "Viết lại TỪNG dòng dưới đây, giữ nguyên ý, giữ NGUYÊN mọi con số, dấu %, đơn vị, ngày và ký hiệu đầu "
        "dòng ('>', '>>', '-', '**…**'). Chỉ sửa 2 lỗi: (1) thay từ tuyệt đối (hoàn toàn, 100%, đương nhiên, "
        "chắc chắn, tuyệt đối) bằng từ trung lập (vd 'chưa được hấp thụ hết', 'nhiều khả năng', 'rõ rệt'); "
        "(2) dịch từ tiếng Anh còn sót sang tiếng Việt (firm → vững, outlook → triển vọng, deficit → thâm hụt, "
        "y-o-y → so cùng kỳ…), giữ tên riêng/mã như ANRPC, SHFE, RSS3, WTI, DXY, PMI, FOB.\n"
        "Trả về đúng số dòng, mỗi dòng bắt đầu bằng số thứ tự trong ngoặc vuông như đầu vào.\n\n"
        f"{listing}"
    )


def polish_sections(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """{khoá phần: [dòng]} → cùng cấu trúc, các dòng lỗi được viết lại (1 lượt AI cho mọi dòng lỗi)."""
    refs = [(key, i) for key, lines in sections.items() for i, s in enumerate(lines) if s and needs_polish(s)]
    if not refs:
        return sections
    items = [sections[k][i] for k, i in refs]
    try:
        out = llm.complete(_SYSTEM, _prompt(items), max_tokens=MAX_TOKENS_POLISH)
    except Exception:  # noqa: BLE001 - soát là bước phụ, lỗi thì giữ nguyên văn
        logger.warning("[weekly-ai] soát văn lỗi — giữ nguyên", exc_info=True)
        return sections
    rewritten: dict[int, str] = {}
    for line in (out or "").splitlines():
        m = _ITEM_RE.match(line)
        if m and int(m.group(1)) < len(items):
            rewritten[int(m.group(1))] = m.group(2)
    result = {k: list(v) for k, v in sections.items()}
    for n, (key, i) in enumerate(refs):
        result[key][i] = accept(items[n], rewritten.get(n))
    return result


def polish_macro(macro: list[dict[str, Any]], extra: dict[str, list[str]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Soát chung các phần viết (`extra`) + gạch của từng tiểu mục IV trong 1 lượt."""
    merged = {**extra, **{f"macro:{i}": m.get("bullets") or [] for i, m in enumerate(macro)}}
    done = polish_sections(merged)
    new_macro = [{**m, "bullets": done[f"macro:{i}"]} for i, m in enumerate(macro)]
    return new_macro, {k: done[k] for k in extra}
