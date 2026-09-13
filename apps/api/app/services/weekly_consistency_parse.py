"""Nhận diện sàn · chủng loại · số · cặp tuần trong chữ nhận định Báo cáo tuần (hàm thuần).

Dùng chung cho bộ soát "chữ nhận định lệch bảng số hiện tại" (`weekly_consistency_check`). Không
DB, không mạng. Số đọc theo cả kiểu Việt lẫn kiểu Anh (báo cáo nhập từ Word cũ có "+4.40%") — khớp
MỘT cách đọc là coi như khớp, để ưu tiên ÍT báo nhầm.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.services.weekly_number_check import readings

# Dung sai sau khi làm tròn số của bảng về đúng số lẻ đã viết.
TOLERANCE = Decimal("0.05")

_B = r"(?<![\w])"   # ranh giới trái (\w gồm cả chữ tiếng Việt có dấu)
_E = r"(?![\w])"
_EXCHANGES = [
    ("OSE", re.compile(_B + r"OSE" + _E)),
    ("SHANGHAI", re.compile(_B + r"(?:SHANGHAI|Shanghai|SHFE|SHF\s?E|Thượng\s+Hải)" + _E)),
    ("SGX", re.compile(_B + r"SGX" + _E)),
    ("MRE", re.compile(_B + r"MRE" + _E)),
]
_GRADES = [
    ("RSS3", re.compile(_B + r"RSS\s?3" + _E, re.I)),
    ("TSR20", re.compile(_B + r"TSR\s?20" + _E, re.I)),
    ("SMR CV", re.compile(_B + r"SMR\s?CV" + _E, re.I)),
    ("SMR20", re.compile(_B + r"SMR\s?20" + _E, re.I)),
    ("LATEX", re.compile(_B + r"LATEX" + _E, re.I)),
]
_BULLET_RE = re.compile(r"^(?:[\s>*•+\-]|o\s)*")
_PAIR_RE = re.compile(r"Tuần\s*(\d{1,2})\s*(?:vs\.?|so với|so)\s*Tuần\s*(\d{1,2})", re.I)
_WEEK_RE = re.compile(r"Tuần\s*(\d{1,2})(?:\s*(?:và|&|-|–)\s*(\d{1,2}))?", re.I)
_HEADER_MAX = 80   # nhãn đầu dòng "Sàn SGX RSS3 (-0,92%):" không dài quá mức này
_HEADER_NO_COLON = 40

Mention = tuple[int, int, str]   # (vị trí đầu, vị trí cuối, tên chuẩn)


def _find(text: str, table: list[tuple[str, re.Pattern[str]]]) -> list[Mention]:
    return sorted((m.start(), m.end(), canon) for canon, rx in table for m in rx.finditer(text))


def exchanges_in(text: str) -> list[Mention]:
    return _find(text, _EXCHANGES)


def grades_in(text: str) -> list[Mention]:
    return _find(text, _GRADES)


def ends_with_grade(text: str) -> str | None:
    """Chủng loại đứng NGAY cuối đoạn (vd 'Sàn SGX: - RSS3' trước '(+0,24%)')."""
    t = text.rstrip(" *")
    hits = [g for s, e, g in grades_in(t) if e == len(t)]
    return hits[0] if hits else None


def ends_with_exchange(text: str) -> str | None:
    """Sàn đứng ngay cuối đoạn, cho phép kèm '(Nhật Bản)'."""
    t = re.sub(r"\s*\([^()%]*\)\s*$", "", text.rstrip(" *"))
    hits = [x for s, e, x in exchanges_in(t) if e == len(t)]
    return hits[0] if hits else None


def last_exchange_before(line: str, pos: int) -> str | None:
    hits = exchanges_in(line[:pos])
    return hits[-1][2] if hits else None


def last_grade_before(line: str, pos: int, allowed: list[str]) -> str | None:
    hits = [g for _, _, g in grades_in(line[:pos]) if g in allowed]
    return hits[-1] if hits else None


def header_of(line: str, grades_by: dict[str, list[str]]) -> tuple[str | None, str | None] | None:
    """Dòng mở đầu 1 sàn ('**Sàn SGX (Singapore):**', 'Sàn OSE RSS3 (+2,70%): …', 'SGX: …') →
    (sàn, chủng loại | None). Nhắc nhiều sàn ('Sàn SGX & MRE:') → (None, None). Không phải → None."""
    body = _BULLET_RE.sub("", line or "", count=1).lstrip("* ")
    lead = re.match(r"(?:Sàn\s+)?", body, re.I)
    first = exchanges_in(body[lead.end():])
    if not first or first[0][0] != 0:
        return None
    colon = body.find(":")
    prefix = body[:colon] if 0 <= colon <= _HEADER_MAX else body[:_HEADER_NO_COLON]
    excs = list(dict.fromkeys(x for _, _, x in exchanges_in(prefix)))
    if len(excs) != 1:
        return None, None
    exc = excs[0]
    allowed = grades_by.get(exc, [])
    grades = list(dict.fromkeys(g for _, _, g in grades_in(prefix) if g in allowed))
    if len(grades) == 1:
        return exc, grades[0]
    return exc, (allowed[0] if len(allowed) == 1 else None)


# ── Số ──
def quantize(x: float, dec: int) -> Decimal:
    return Decimal(str(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)


def same_number(token: str, negative: bool, table: float) -> bool:
    """Số viết (chuỗi gốc + dấu) khớp số bảng sau khi làm tròn bảng về đúng số lẻ đã viết."""
    for value, dec in readings(token, "any"):
        v = -value if negative else value
        if abs(v - quantize(table, dec)) <= TOLERANCE:
            return True
    return False


def is_minus(sign: str) -> bool:
    return sign in ("-", "−", "–")


def dm_of(text: str) -> tuple[int, int] | None:
    """'07/09' / '7/9' → (7, 9)."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


# ── Cặp tuần ──
def pair_index(weeks: list[dict[str, Any]], newer: int, older: int) -> int | None:
    for i in range(len(weeks) - 1):
        if weeks[i + 1]["week_no"] == newer and weeks[i]["week_no"] == older:
            return i
    return None


def pair_marker(line: str) -> tuple[int, int, int] | None:
    """'*Tuần 37 vs Tuần 36:*' → (vị trí cuối nhãn, 37, 36)."""
    m = _PAIR_RE.search(line or "")
    return (m.end(), int(m.group(1)), int(m.group(2))) if m else None


def pair_label(weeks: list[dict[str, Any]], i: int) -> str:
    return f"Tuần {weeks[i + 1]['week_no']} so Tuần {weeks[i]['week_no']}"


def pairs_for_text(text: str, weeks: list[dict[str, Any]]) -> list[int]:
    """Cặp tuần mà đoạn văn đang nói: tuần trong kỳ được nhắc tên → đúng cặp đó; không nhắc → mọi cặp."""
    nums = {int(n) for m in _WEEK_RE.finditer(text or "") for n in m.groups() if n}
    hit = [i for i in range(len(weeks) - 1) if weeks[i + 1]["week_no"] in nums]
    return hit or list(range(len(weeks) - 1))
