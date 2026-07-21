"""Phân giải nhanh chuỗi giá physical Reuters (copy từ MarketScreener) → bản ghi USD/tấn.

Ngày do NGƯỜI DÙNG chọn trên trang (không lấy từ text). Nhận 2 dạng text:

Dạng 1 — mỗi dòng có tiền tố 'Grade:' và dấu gạch trước giá:
    Grade: Thai RSS3 (August) - 97.39 baht/kg
    Grade: Thai STR20 (August) - 78.88 baht/kg
    Grade: Thai 60-percent latex (bulk/August) - 57.90 baht/kg
    Grade: Malaysia SMR20 (August) - $2.21/kg
    Grade: Indonesia SIR20 - NA

Dạng 2 — bảng 2 cột (chủng loại / giá) ngăn nhau bằng khoảng trắng, có thể kèm ghi chú sau dấu '*':
    July 20 (Reuters) -
    Grade Prices
    RSS3        NA
    60% latex (bulk) NA
    SMR20      $2.24/kg
    SIR20         $2.34/kg * Prices as of July 16

Quy đổi về USD/tấn (nhất quán data cũ + ô nhập tay): US$/kg ×1000; baht/kg ÷ USD/THB
(kéo tỷ giá gần nhất ≤ ngày). NA/không khớp grade/thiếu tỷ giá → đánh dấu, KHÔNG nhập.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import text as sql

from app.core.db import ensure_schema, session_scope
from app.services.price_repo import _to_usd_tonne

# Nhãn Reuters → grade chuẩn (khớp cụ thể trước; latex bulk/drum trước rss/str…).
_GRADE_PATTERNS = [
    (re.compile(r"latex.*bulk", re.I), "Thai Latex 60% (Bulk)"),
    (re.compile(r"latex.*drum", re.I), "Thai Latex 60% (Drums)"),
    (re.compile(r"\brss\s*3\b", re.I), "RSS3"),
    (re.compile(r"\bstr\s*20\b", re.I), "STR20"),
    (re.compile(r"\bsmr\s*20\b", re.I), "SMR20"),
    (re.compile(r"\bsir\s*20\b", re.I), "SIR20"),
    (re.compile(r"\buss\b", re.I), "USS"),
]
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
# Reuters chỉ báo Latex Bulk; Drums = Bulk + 100 USD/tấn (chuyên viên vẫn dùng — verify data: diff=100).
_DRUMS_PREMIUM = 100
_LATEX_BULK = "Thai Latex 60% (Bulk)"
_LATEX_DRUMS = "Thai Latex 60% (Drums)"
# Giá+đơn vị nằm ở CUỐI dòng (grade chứa số như RSS3/STR20 → phải neo cuối, tránh bắt nhầm).
_BAHT = re.compile(r"(\d+(?:[.,]\d+)?)\s*baht\s*/?\s*kg\s*$", re.I)
_USD_KG = re.compile(r"(?:us)?\$\s*(\d+(?:[.,]\d+)?)\s*/\s*kg\s*$", re.I)
# NA có thể ngăn bằng dấu ('- NA') hoặc chỉ khoảng trắng ('RSS3    NA' — dạng bảng 2 cột).
_NA_END = re.compile(r"(?:[-:–]\s*)?(?:\b(?:n/?a|null)\b|[-—])\s*$", re.I)
_GRADE_PREFIX = re.compile(r"^\s*grade\s*[:\-–]?\s*", re.I)  # bỏ tiền tố 'Grade:' nếu có
_TAIL_NOTE = re.compile(r"\s*\*\s*(\S.*?)\s*$")              # ghi chú cuối dòng, vd '* Prices as of July 16'


def _note_date(note: str, as_of: date) -> date | None:
    """Ngày trong ghi chú 'Prices as of July 16' → date. Reuters không ghi năm → suy từ `as_of`
    (nếu vượt as_of thì lùi 1 năm). Dùng để CẢNH BÁO khi giá thuộc ngày khác ngày người dùng chọn."""
    m = re.search(r"as\s+of\s+([A-Za-z]+)\s+(\d{1,2})\b", note, re.I)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        d = date(as_of.year, month, int(m.group(2)))
    except ValueError:
        return None
    return d.replace(year=d.year - 1) if d > as_of else d


def _match_grade(label: str) -> str | None:
    for pat, grade in _GRADE_PATTERNS:
        if pat.search(label):
            return grade
    return None


def _thb_at(as_of: date) -> float | None:
    """USD/THB ĐÚNG NGÀY `as_of` để quy đổi baht/kg. TUYỆT ĐỐI KHÔNG carry-forward (không lấy tỷ giá
    ngày khác dựng số cho ngày này). Thiếu tỷ giá đúng ngày → None → dòng baht/kg = no_fx, KHÔNG nhập."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(sql(
            "SELECT price FROM fact_price WHERE source='fx' AND grade='USD/THB' "
            "AND as_of = CAST(:d AS date) LIMIT 1"), {"d": as_of.isoformat()}).first()
    return float(row[0]) if row else None


def _contract(label: str) -> str:
    """Tháng giao hàng trong ngoặc, vd '(August)' / '(bulk/August)' → 'August'."""
    m = re.search(r"\(([^)]*)\)", label)
    if not m:
        return ""
    for tok in re.split(r"[/,]", m.group(1)):
        if tok.strip().lower() in _MONTHS:
            return tok.strip().title()
    return ""


def _native(line: str) -> tuple[float | None, str | None]:
    """(giá, đơn vị gốc) từ CUỐI dòng: '… 100.83 baht/kg' hoặc '… $2.21/kg'. Không thấy → (None, None)."""
    s = line.strip()
    m = _BAHT.search(s)
    if m:
        return float(m.group(1).replace(",", ".")), "baht/kg"
    m = _USD_KG.search(s)
    if m:
        return float(m.group(1).replace(",", ".")), "US$/kg"
    return None, None


def _is_na(line: str) -> bool:
    """Dòng ghi NA (không có giá) — vd '… SIR20 - NA' / '… SIR20: NA'."""
    return bool(_NA_END.search(line.strip()))


def parse(text: str, as_of: date | None = None) -> dict:
    """Phân giải text Reuters → {as_of, usd_thb, note, rows}. Ngày `as_of` do người dùng chọn (mặc định hôm nay).
    Nhận các dạng dòng: 'Thai RSS3 (August): 100.83 baht/kg', 'Grade: Thai RSS3 (August) - 97.39 baht/kg'
    và dạng bảng 2 cột 'SMR20    $2.24/kg' (NA chỉ ngăn bằng khoảng trắng, ghi chú sau dấu '*').
    `note` = ghi chú Reuters kèm trong text (vd 'Prices as of July 16') — báo cho người nhập tự đối chiếu ngày.
    """
    d = as_of or date.today()
    thb = _thb_at(d)
    rows: list[dict] = []
    notes: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "reuters" in line.lower():
            continue
        body = _GRADE_PREFIX.sub("", line)          # bỏ 'Grade:' rồi soi grade + giá trên cả dòng
        m_note = _TAIL_NOTE.search(body)
        if m_note:                                  # tách ghi chú cuối dòng để giá vẫn nằm ở cuối
            note = m_note.group(1)
            if note not in notes:
                notes.append(note)
            body = body[:m_note.start()].strip()
        grade = _match_grade(body)
        price, unit = _native(body)
        na = _is_na(body)
        if grade is None and price is None and not na:
            continue                                # dòng không phải giá (tiêu đề/ghi chú)
        row = {"label": body, "grade": grade, "native_price": price,
               "native_unit": unit, "contract": _contract(body), "usd_tonne": None, "status": "ok"}
        if grade is None:
            row["status"] = "unmatched"
        elif na or price is None:
            row["status"] = "na" if na else "no_unit"
        elif unit == "baht/kg" and thb is None:
            row["status"] = "no_fx"                 # baht/kg nhưng thiếu USD/THB → chưa quy đổi được
        else:
            row["usd_tonne"] = _to_usd_tonne(price, unit, thb)
            if row["usd_tonne"] is None:
                row["status"] = "no_fx"
        rows.append(row)
    _add_drums(rows)
    note = "; ".join(notes) or None
    return {"as_of": d, "usd_thb": thb, "note": note,
            "note_as_of": _note_date(note, d) if note else None, "rows": rows}


def _add_drums(rows: list[dict]) -> None:
    """Nội suy Latex Drums = Bulk + 100 USD/tấn nếu Reuters chỉ có Bulk (đã quy đổi được, chưa có Drums)."""
    bulk = next((r for r in rows if r["grade"] == _LATEX_BULK and r["status"] == "ok"), None)
    if not bulk or any(r["grade"] == _LATEX_DRUMS for r in rows):
        return
    rows.append({"label": f"{_LATEX_DRUMS} (nội suy Bulk + {_DRUMS_PREMIUM})", "grade": _LATEX_DRUMS,
                 "native_price": None, "native_unit": None, "contract": bulk["contract"],
                 "usd_tonne": bulk["usd_tonne"] + _DRUMS_PREMIUM, "status": "derived"})
