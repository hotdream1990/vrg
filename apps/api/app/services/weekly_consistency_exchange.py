"""Soát nhận định III.1 (sàn quốc tế) với bảng số HIỆN TẠI — % · giá TB · cao/thấp · sàn thiếu/thừa.

Hàm thuần trên `build_report`. Nhận diện 3 kiểu chữ:
- v2 (code dựng): '**Sàn SGX (Singapore):**' rồi '> *Tuần 37 vs Tuần 36:* RSS3 tăng lên **2.767,6 USD/tấn**
  (+1,3%); TSR20 …' và '>> **RSS3:** Cao nhất **2.788,0 USD/tấn** … ngày 10/09; Thấp nhất …'.
- v1 (AI viết thẳng): 'Sàn SGX RSS3 (-0,92%): …' rồi '> Cao nhất tuần: Đạt 2.707,0 USD/tấn (ngày 7/9)'.
- Bản nhập từ Word cũ: 'Sàn OSE: Giá trung bình tuần giảm mạnh 2,05%', '… RSS3 giảm 1,24% và TSR20 …'.
Kiểu v1/Word cũ không ghi cặp tuần → chỉ soát khi báo cáo 1 tuần (chắc chắn là cặp cuối).
"""

from __future__ import annotations

import re
from typing import Any

from app.services import weekly_consistency_parse as p
from app.services.weekly_ai_compose import pct, vn

_PCT_RE = re.compile(r"\(\s*([+\-−–]?)\s*(\d+(?:[.,]\d+)?|N/A)\s*%\s*\)", re.I)
_VERB_PCT_RE = re.compile(
    r"(Giá trung bình(?:\s+tuần)?|RSS\s?3|TSR\s?20|SMR\s?CV|SMR\s?20|LATEX)\s+(tăng|giảm)"
    r"(?:\s+(?:mạnh|nhẹ))?\s+(\d+(?:[.,]\d+)?)\s*%", re.I)
_PRICE_RE = re.compile(r"\*\*\s*([\d.,]+)\s*USD/tấn\s*\*\*(?:\s*\(\s*([+\-−–]?)\s*([\d.,]+)\s*%\s*\))?")
_HILO_RE = re.compile(r"(cao nhất|thấp nhất)(?:\s+tuần)?((?:(?!cao nhất|thấp nhất)[^;\d~\n.]){0,40}?)"
                      r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*USD\s*/\s*tấn", re.I)
_DATE_RE = re.compile(r"(?<![\d/\-–])(\d{1,2})/(\d{1,2})(?![\d/])")
_GAP_WORDS_RE = re.compile(r"không có giá|chưa có giá|chưa quy đổi|thiếu tỷ giá|N/A|nghỉ|không giao dịch"
                           r"|không có dữ liệu", re.I)


class _Ctx:
    """Bảng tra của báo cáo: dòng theo (sàn, chủng loại), chủng loại theo sàn, cao/thấp."""

    def __init__(self, rep: dict[str, Any]) -> None:
        self.weeks = rep.get("weeks") or []
        self.rows = {(r["exchange"], r["grade"]): r for r in rep.get("exchange_rows") or []}
        self.grades_by: dict[str, list[str]] = {}
        for exc, grade in self.rows:
            self.grades_by.setdefault(exc, []).append(grade)
        self.stats = {(s["exchange"], s["grade"]): s for s in rep.get("range_stats") or []}

    def grade_for(self, exc: str | None, grade: str | None) -> str | None:
        allowed = self.grades_by.get(exc or "", [])
        if grade in allowed:
            return grade
        return allowed[0] if grade is None and len(allowed) == 1 else None


def _pct_issue(c: _Ctx, exc: str, grade: str, i: int, sign: str, num: str) -> str | None:
    row = c.rows.get((exc, grade)) or {}
    pcts = row.get("changes_pct") or []
    table = pcts[i] if i < len(pcts) else None
    na = num.upper() == "N/A"
    if na and table is None:
        return None
    if not na and table is not None and p.same_number(num, p.is_minus(sign), table):
        return None
    written = "N/A" if na else f"{'-' if p.is_minus(sign) else sign}{num}%"
    shown = "N/A" if table is None else pct(table, 2)
    return f"Nhận định ghi {exc} {grade} {written} nhưng bảng hiện {shown} ({p.pair_label(c.weeks, i)})."


def _v2_line(c: _Ctx, line: str, ctx_exc: str | None) -> list[str]:
    marker = p.pair_marker(line)
    i = p.pair_index(c.weeks, marker[1], marker[2]) if marker else None
    if i is None:
        return []
    out, start = [], marker[0]
    for seg_off, seg in _segments(line, start):
        exc = p.last_exchange_before(line, seg_off) or ctx_exc
        for m in _PRICE_RE.finditer(seg):
            grade = c.grade_for(exc, p.last_grade_before(seg, m.start(), c.grades_by.get(exc or "", [])))
            if not exc or not grade:
                continue
            vals = c.rows[(exc, grade)].get("values") or []
            table = vals[i + 1] if i + 1 < len(vals) else None
            if table is None or not p.same_number(m.group(1), False, table):
                shown = "N/A" if table is None else f"{vn(table)} USD/tấn"
                out.append(f"Nhận định ghi giá TB {exc} {grade} Tuần {c.weeks[i + 1]['week_no']} "
                           f"{m.group(1)} USD/tấn nhưng bảng hiện {shown}.")
            if m.group(3):
                out.append(_pct_issue(c, exc, grade, i, m.group(2), m.group(3)) or "")
            break   # 1 đoạn ';' = 1 chủng loại
    return [s for s in out if s]


def _segments(line: str, start: int) -> list[tuple[int, str]]:
    out, off = [], start
    for part in line[start:].split(";"):
        out.append((off, part))
        off += len(part) + 1
    return out


def _v1_pcts(c: _Ctx, line: str, ctx_exc: str | None, ctx_grade: str | None) -> list[str]:
    if len(c.weeks) != 2:
        return []
    out = []
    for m in _PCT_RE.finditer(line):
        before = line[:m.start()]
        exc = p.ends_with_exchange(before)
        grade = c.grade_for(exc, None) if exc else None
        if not exc and (g := p.ends_with_grade(before)):
            exc = p.last_exchange_before(line, m.start()) or ctx_exc
            grade = c.grade_for(exc, g)
        if exc and grade:
            out.append(_pct_issue(c, exc, grade, 0, m.group(1), m.group(2)))
    for m in _VERB_PCT_RE.finditer(line):
        exc = p.last_exchange_before(line, m.start()) or ctx_exc
        avg = m.group(1).lower().startswith("giá")
        grade = (c.grade_for(exc, ctx_grade) if avg
                 else c.grade_for(exc, (p.grades_in(m.group(1)) or [(0, 0, "")])[0][2]))
        if exc and grade:
            out.append(_pct_issue(c, exc, grade, 0, "-" if m.group(2).lower() == "giảm" else "+", m.group(3)))
    return [s for s in out if s]


def _hilo(c: _Ctx, line: str, ctx_exc: str | None, ctx_grade: str | None) -> list[str]:
    out = []
    for m in _HILO_RE.finditer(line):
        if "khoảng" in m.group(2).lower():
            continue
        exc = p.last_exchange_before(line, m.start()) or ctx_exc
        grade = c.grade_for(exc, p.last_grade_before(line, m.start(), c.grades_by.get(exc or "", []))
                            or ctx_grade)
        if not exc or not grade:
            continue
        high = m.group(1).lower() == "cao nhất"
        tail = re.split(r";|cao nhất|thấp nhất", line[m.end():], maxsplit=1, flags=re.I)[0][:60]
        dm = _DATE_RE.search(tail)
        written_dm = (int(dm.group(1)), int(dm.group(2))) if dm else None
        out.append(_hilo_issue(c, exc, grade, high, m.group(3), written_dm) or "")
    return [s for s in out if s]


def _hilo_issue(c: _Ctx, exc: str, grade: str, high: bool, num: str,
                written_dm: tuple[int, int] | None) -> str | None:
    kind = "cao nhất" if high else "thấp nhất"
    where = f" ({written_dm[0]}/{written_dm[1]})" if written_dm else ""
    s = c.stats.get((exc, grade))
    if not s:
        return f"Nhận định ghi {exc} {grade} {kind} {num} USD/tấn{where} nhưng bảng không có giá USD trong kỳ."
    value, dm = (s["high"], s["high_date"]) if high else (s["low"], s["low_date"])
    stat_dm = p.dm_of(dm)
    same_value = p.same_number(num, False, value)
    # Hai ngày bằng giá thì bảng lấy ngày SỚM hơn → chỉ chắc lệch ngày khi chữ ghi ngày SỚM hơn bảng.
    earlier = bool(written_dm and stat_dm and _ord(written_dm, c) < _ord(stat_dm, c))
    if same_value and not earlier:
        return None
    shown = f"{vn(value)} USD/tấn ({stat_dm[0]}/{stat_dm[1]})" if stat_dm else f"{vn(value)} USD/tấn"
    return f"Nhận định ghi {exc} {grade} {kind} {num} USD/tấn{where} nhưng bảng hiện {shown}."


def _ord(dm: tuple[int, int], c: _Ctx) -> int:
    """Thứ tự ngày trong kỳ; kỳ vắt năm (tháng 12 → tháng 1) thì tháng đầu năm xếp sau."""
    crosses = any(w["mon"][5:7] == "12" for w in c.weeks) and any(w["fri"][5:7] == "01" for w in c.weeks)
    month = dm[1] + (12 if crosses and dm[1] <= 2 else 0)
    return month * 31 + dm[0]


def _coverage(c: _Ctx, lines: list[str], sections: dict[str, list[str]]) -> list[str]:
    """Sàn bảng có giá mà nhận định không nhắc · nhận định nhắc sàn mà bảng N/A cả kỳ (không giải thích)."""
    text = "\n".join(lines)
    if not text.strip():
        return []
    mentioned = {x for _, _, x in p.exchanges_in(text)}
    out = []
    for exc, grades in c.grades_by.items():
        has = any(v is not None for g in grades for v in (c.rows[(exc, g)].get("values") or [])[1:])
        if has and exc not in mentioned:
            out.append(f"Nhận định III.1 chưa nhắc tới sàn {exc} (bảng có giá trong kỳ).")
        elif not has and exc in mentioned and not _GAP_WORDS_RE.search("\n".join(sections.get(exc, []))):
            out.append(f"Nhận định III.1 nhắc tới sàn {exc} nhưng bảng không có giá cả kỳ.")
    return out


def check_exchange_notes(rep: dict[str, Any]) -> list[str]:
    c = _Ctx(rep)
    lines = [s for s in ((rep.get("narrative") or {}).get("exchange_notes") or []) if s and s.strip()]
    out: list[str] = []
    sections: dict[str, list[str]] = {}
    ctx_exc = ctx_grade = None
    for line in lines:
        head = p.header_of(line, c.grades_by)
        if head is not None:
            ctx_exc, ctx_grade = head
        elif not line.lstrip().startswith(">"):
            ctx_exc = ctx_grade = None
        for exc in {x for _, _, x in p.exchanges_in(line)} | ({ctx_exc} if ctx_exc else set()):
            sections.setdefault(exc, []).append(line)
        out += _v2_line(c, line, ctx_exc) if p.pair_marker(line) else _v1_pcts(c, line, ctx_exc, ctx_grade)
        out += _hilo(c, line, ctx_exc, ctx_grade)
    out += _coverage(c, lines, sections)
    return list(dict.fromkeys(out))
