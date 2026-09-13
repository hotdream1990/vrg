"""Soát CHIỀU giá trong văn tự do (I, II, IV): '{SÀN} {CHỦNG LOẠI}? … tăng/giảm/hạ nhiệt…' so với dấu
% của bảng. Hàm thuần — chỉ báo khi CHẮC (cảnh báo mềm "Có thể lệch chiều"):

- Chủ ngữ phải là tên sàn (có/không kèm chủng loại) đứng TRƯỚC động từ, cách ≤ 6 từ, cùng mệnh đề
  (tách ở . ; : và các từ nối 'trong khi', 'nhưng', 'song', 'còn', 'tuy nhiên'…). Nhiều sàn nối bằng
  ',' / 'và' ('SGX TSR20, MRE SMR CV và MRE LATEX đều giữ vững sắc xanh') dùng chung động từ.
- Bỏ mệnh đề nói về phiên/ngày/đầu–cuối tuần, kỳ hạn/hợp đồng tháng, tồn kho, kỳ vọng/dự báo, phủ định.
- Sàn không kèm chủng loại mà các chủng loại trái chiều nhau → bỏ. |%| < 0,1 → coi như đi ngang, bỏ.
"""

from __future__ import annotations

import re
from typing import Any

from app.services import weekly_consistency_parse as p
from app.services.weekly_ai_compose import pct

_UP = {"tăng", "đi lên", "sắc xanh", "nhích lên"}
_VERB_RE = re.compile(r"(?<!\w)(gia tăng|tăng giảm|tăng|đi lên|sắc xanh|nhích lên|giảm|hạ nhiệt|suy yếu"
                      r"|sắc đỏ|đi xuống)(?!\w)", re.I)
_SPLIT_RE = re.compile(r"(?<!\d)[.;:!?](?!\d)|(?<!\w)(?:trong khi|nhưng|song|còn|ngược lại|tuy nhiên"
                       r"|trái lại|mặc dù|dù|thay vì|so với|hơn là|trước khi|sau khi)(?!\w)", re.I)
_SKIP_CLAUSE_RE = re.compile(r"phiên|ngày|đầu tuần|cuối tuần|giữa tuần|kỳ hạn|hợp đồng|tháng|\d/\d|nhịp"
                             r"|kỳ vọng|dự báo|có thể|nguy cơ|nếu|lo ngại|tồn kho", re.I)
# Giữa chủ ngữ và động từ: phủ định/so sánh, "sức ép/áp lực giảm" (lực tác động, chưa chắc giá đã giảm)
# hoặc dấu câu/ngoặc (vd "(OSE), đồng Yên suy yếu" — chủ ngữ thật là đồng Yên) → không chắc, bỏ.
_HEDGE_RE = re.compile(r"(?<!\w)(không|chưa|khó|ít|kém|hơn|chậm|bớt|sức ép|áp lực)(?!\w)|[,()]", re.I)
_JOIN_RE = re.compile(r"^(?:[\s,&*]|và|cùng|lẫn|sàn|Sàn)*$")
_MAX_WORDS = 6
_FLAT_PCT = 0.1
_SNIPPET = 90


def _subjects(clause: str, grades_by: dict[str, list[str]]) -> list[tuple[int, int, str, str | None]]:
    """(đầu, cuối, sàn, chủng loại | None) — chủng loại chỉ tính khi đứng NGAY sau tên sàn."""
    out = []
    grades = p.grades_in(clause)
    for s, e, exc in p.exchanges_in(clause):
        adj = next(((ge, gg) for gs, ge, gg in grades if gs >= e and not clause[e:gs].strip(" *")), None)
        if adj and adj[1] in grades_by.get(exc, []):
            out.append((s, adj[0], exc, adj[1]))
        elif exc in grades_by:
            out.append((s, e, exc, None))
    return out


def _groups(clause: str, subs: list[tuple[int, int, str, str | None]]) -> list[list[tuple]]:
    groups: list[list[tuple]] = []
    for sub in subs:
        if groups and _JOIN_RE.match(clause[groups[-1][-1][1]:sub[0]]):
            groups[-1].append(sub)
        else:
            groups.append([sub])
    return groups


def _polarity(clause: str, end: int, next_start: int) -> tuple[bool, int] | None:
    """(tăng?, vị trí cuối động từ) của động từ đầu tiên ≤ 6 từ sau chủ ngữ; None nếu không chắc."""
    window = clause[end:next_start]
    m = _VERB_RE.search(window)
    if not m or len(window[:m.start()].split()) > _MAX_WORDS:
        return None
    verb = m.group(1).lower()
    if verb in ("gia tăng", "tăng giảm") or _HEDGE_RE.search(window[:m.start()]):
        return None
    return verb in _UP, end + m.end()


def _row_pcts(rows: dict, exc: str, grade: str | None, grades_by: dict, pairs: list[int]) -> list[tuple]:
    grades = [grade] if grade else grades_by.get(exc, [])
    out = []
    for g in grades:
        cps = (rows.get((exc, g)) or {}).get("changes_pct") or []
        out += [(g, i, cps[i]) for i in pairs if i < len(cps) and cps[i] is not None]
    return out


def check_direction(lines: list[str], rows_list: list[dict[str, Any]], weeks: list[dict[str, Any]],
                    fixed_pairs: list[int] | None = None) -> list[str]:
    """`fixed_pairs` = cặp tuần cố định (Phần I: cặp của tuần mốc); None = suy từ 'Tuần N' trong đoạn."""
    rows = {(r["exchange"], r["grade"]): r for r in rows_list or [] if r.get("exchange")}
    grades_by: dict[str, list[str]] = {}
    for exc, g in rows:
        grades_by.setdefault(exc, []).append(g)
    out: list[str] = []
    for line in lines or []:
        pairs = fixed_pairs if fixed_pairs is not None else p.pairs_for_text(line, weeks)
        for clause in _SPLIT_RE.split(line or ""):
            if not clause or _SKIP_CLAUSE_RE.search(clause):
                continue
            subs = _subjects(clause, grades_by)
            groups = _groups(clause, subs)
            for gi, group in enumerate(groups):
                nxt = groups[gi + 1][0][0] if gi + 1 < len(groups) else len(clause)
                pol = _polarity(clause, group[-1][1], nxt)
                if pol is None:
                    continue
                snippet = clause[group[0][0]:pol[1]].strip()[:_SNIPPET]
                for _, _, exc, grade in group:
                    msg = _conflict(rows, exc, grade, grades_by, pairs, pol[0], weeks, snippet)
                    if msg:
                        out.append(msg)
    return list(dict.fromkeys(out))


def _conflict(rows: dict, exc: str, grade: str | None, grades_by: dict, pairs: list[int], up: bool,
              weeks: list[dict[str, Any]], snippet: str) -> str | None:
    vals = _row_pcts(rows, exc, grade, grades_by, pairs)
    if not vals or any(abs(v) < _FLAT_PCT for _, _, v in vals):
        return None
    signs = {v > 0 for _, _, v in vals}
    if len(signs) != 1 or signs.pop() == up:
        return None
    g, i, v = vals[0]
    return (f"Có thể lệch chiều: “{snippet}” nhưng bảng {exc} {g} {pct(v, 2)} "
            f"({p.pair_label(weeks, i)}).")
