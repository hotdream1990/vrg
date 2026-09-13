"""Kiểm tra văn AI của Báo cáo tuần — số có căn cứ trong ngữ cảnh không · từ ngữ tuyệt đối.

Hàm THUẦN (không DB, không mạng). Chỉ để CẢNH BÁO cho chuyên viên soát lại, không tự sửa văn.

Cách đối chiếu số: số trong NGỮ CẢNH được hiểu theo cả kiểu Việt ("2.763,6") lẫn kiểu Anh ("2,728.2"
trong tài liệu ANRPC). Số trong VĂN KIỂM TRA hiểu theo `locale`: "vi" (mặc định — văn báo cáo AI viết,
prompt bắt kiểu Việt; số viết kiểu Anh coi như không đối chiếu được) hoặc "any" (tóm tắt tài liệu đính
kèm, có thể giữ kiểu Anh). Số được coi là CÓ CĂN CỨ nếu một cách hiểu của nó bằng một số trong ngữ cảnh
sau khi làm tròn số ngữ cảnh (nửa lên) về đúng số chữ số thập phân đã viết — so trị tuyệt đối ("giảm
26,3" ứng với "-26,3" trong bảng). Riêng số NGUYÊN < 100 (5%, 12 tấn…) phải có ĐÚNG số nguyên đó trong
ngữ cảnh — không khớp nhờ làm tròn (4,6 không làm căn cứ cho "5%"). Ngày, số tuần, năm (trừ khi đứng
cạnh đơn vị: "2030 USD/tấn"), số thứ tự đầu mục và mã chủng loại (SMR20, SVR 10, RSS 3…) bỏ qua.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

ABSOLUTE_WORDS = ["hoàn toàn", "100%", "đương nhiên", "chắc chắn", "tuyệt đối"]

_MAX_DECIMALS = 6

# Ngày: 27/08 · 03–04/9 · 24/8/2026 · 7/2026 · 35-36/2026 (nhãn kỳ) — thay bằng khoảng trắng.
_DATE_RE = re.compile(
    r"(?<![\d.,])\d{1,2}(?:\s*[–-]\s*\d{1,2})?/\d{1,2}(?:/\d{2,4})?(?!\d)"
    r"|(?<![\d.,])\d{1,2}(?:\s*[–-]\s*\d{1,2})?/\d{4}(?!\d)"
)
# Số tuần: "Tuần 35", "T36/T35", "Tuần 35 và 36", "tuần 35 - 36".
_WEEK_NUM = r"\d{1,2}(?![\d.,]\d)(?!\d)"
_WEEK_RE = re.compile(
    rf"\b(?:[Tt]uần|TUẦN|T)\s?{_WEEK_NUM}"
    rf"(?:\s*(?:và|&|–|-|/)\s*(?:(?:[Tt]uần|T)\s?)?{_WEEK_NUM})*"
)
# Tháng/quý/ngày đứng riêng: "tháng 7", "quý 3", "ngày 25".
_CAL_RE = re.compile(r"\b(?:[Tt]háng|[Qq]uý|[Nn]gày)\s+\d{1,2}(?![\d.,]\d)(?!\d)")
# Nhãn mục kiểu "IV.1", "III.2".
_ROMAN_RE = re.compile(r"\b[IVX]+\.\d\b")
# Số thứ tự đầu mục: "1. ", "a) ", "2) " (sau các ký hiệu gạch '>', '-', '•', '*').
_ORDINAL_RE = re.compile(r"^(\s*(?:[>\-–•*]+\s*)*)(?:\d{1,2}|[a-zA-Z])[.)](?=\s)")
# Mã chủng loại có dấu cách: "SVR 10", "CSR 20", "RSS 3", "SVR CV 50", "Latex 60%".
_GRADE_RE = re.compile(r"\b(?:SVR|SMR|STR|TSR|RSS|CSR|SIR)\s*(?:CV\s*)?\d+[A-Za-z]*\b|\b[Ll][Aa][Tt][Ee][Xx]\s*60\s*%")
# Số: không dính chữ/số hai bên (bỏ mã SMR20 — kể cả phần đuôi "0" —, RSS3, SVR 3L, Q2…).
_NUM_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)")
_YEAR_RE = re.compile(r"20\d{2}")
# Năm đứng cạnh đơn vị thì là SỐ LIỆU ("2030 USD/tấn"), không phải năm.
_UNIT_AFTER_RE = re.compile(r"\s*(?:%|USD|US\s*cent|tấn|CNY|JPY|MYR|THB|Yên|yên)", re.IGNORECASE)
_MAX_EXACT_INT = 100

_VN_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
_EN_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def _clean_line(line: str) -> str:
    s = _ORDINAL_RE.sub(lambda m: m.group(1) + " ", line)
    for rx in (_DATE_RE, _WEEK_RE, _CAL_RE, _ROMAN_RE, _GRADE_RE):
        s = rx.sub(" ", s)
    return s


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        clean = _clean_line(line)
        for m in _NUM_RE.finditer(clean):
            if not _YEAR_RE.fullmatch(m.group()) or _UNIT_AFTER_RE.match(clean, m.end()):
                out.append(m.group())
    return out


def _reading(tok: str, thousands: str, decimal: str) -> tuple[Decimal, int]:
    int_part, _, frac = tok.partition(decimal)
    digits = int_part.replace(thousands, "") + ("." + frac if frac else "")
    return Decimal(digits), len(frac)


def readings(tok: str, locale: str = "any") -> list[tuple[Decimal, int]]:
    """Các cách hiểu (giá trị, số chữ số thập phân) của một chuỗi số: kiểu Việt và/hoặc kiểu Anh.
    `locale="vi"` → chỉ kiểu Việt (chấm nghìn, phẩy thập phân)."""
    out: list[tuple[Decimal, int]] = []
    if _VN_RE.fullmatch(tok):
        out.append(_reading(tok, ".", ","))
    if locale != "vi" and _EN_RE.fullmatch(tok):
        r = _reading(tok, ",", ".")
        if r not in out:
            out.append(r)
    return out


class _ContextIndex:
    """Tập số trong ngữ cảnh, làm tròn sẵn theo từng số chữ số thập phân (tính lười)."""

    def __init__(self, context: str) -> None:
        pairs = [r for tok in _tokens(context) for r in readings(tok)]
        self._values = {v for v, _ in pairs}
        self._integers = {v for v, d in pairs if d == 0}   # token số nguyên đúng như viết
        self._rounded: dict[int, set[Decimal]] = {}

    def has(self, value: Decimal, decimals: int) -> bool:
        if decimals == 0 and value < _MAX_EXACT_INT:  # số nhỏ dễ "trùng" nhờ làm tròn → khớp đúng
            return value in self._integers
        d = min(decimals, _MAX_DECIMALS)
        if d not in self._rounded:
            self._rounded[d] = {r for v in self._values if (r := _quantize(v, d)) is not None}
        return value in self._rounded[d]


def _quantize(v: Decimal, d: int) -> Decimal | None:
    """Làm tròn nửa lên; chuỗi số quá dài (mã số, số điện thoại…) vượt độ chính xác → bỏ."""
    try:
        return v.quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def unverified_numbers(lines: Iterable[str], context: str, locale: str = "vi") -> list[str]:
    """Các số trong văn KHÔNG đối chiếu được với ngữ cảnh (chuỗi gốc, không trùng, theo thứ tự).
    `locale`: "vi" = văn báo cáo AI (chỉ đọc kiểu Việt) · "any" = tóm tắt đính kèm (Việt hoặc Anh)."""
    idx = _ContextIndex(context or "")
    seen: set[str] = set()
    out: list[str] = []
    for line in lines or []:
        for tok in _tokens(line or ""):
            if tok in seen:
                continue
            seen.add(tok)
            if not any(idx.has(v, d) for v, d in readings(tok, locale)):
                out.append(tok)
    return out


_ABS_RES = [(w, re.compile(rf"(?<!\w){re.escape(w)}(?!\w)", re.IGNORECASE)) for w in ABSOLUTE_WORDS]


def absolute_words(lines: Iterable[str]) -> list[str]:
    """Từ ngữ tuyệt đối xuất hiện trong văn (theo ranh giới từ, không phân biệt hoa thường)."""
    text = "\n".join(s for s in (lines or []) if s)
    return [w for w, rx in _ABS_RES if rx.search(text)]
