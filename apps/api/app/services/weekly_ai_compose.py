"""Dựng PHẦN SỐ của nhận định III.1 / III.2 Báo cáo tuần bằng code (hàm thuần, không DB/mạng).

AI chỉ viết CỤM NGUYÊN NHÂN cho từng (sàn, cặp tuần) theo nhãn `SÀN | T35/T34 | nguyên nhân`; tên
sàn, giá TB, %, cao/thấp, ngày, giá nội tệ, ghi chú không có giá lấy thẳng từ `build_report` → số
trong nhận định không thể lệch bảng. Ngày thiếu lấy từ `rep["exchange_gap_days"]` (có cấu trúc, tách "không
có giá" với "thiếu tỷ giá" — ngày thiếu tỷ giá sàn VẪN giao dịch, không gọi là nghỉ). Định dạng bám mẫu tuần 35–36: dòng thường = gạch chính, `>` =
gạch cấp 2, `>>` = gạch cấp 3, `**đậm**`, `*nghiêng*`.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

EXCHANGE_NAMES = {
    "OSE": "Sàn OSE (Nhật Bản)", "SHANGHAI": "Sàn SHANGHAI (Trung Quốc)",
    "SGX": "Sàn SGX (Singapore)", "MRE": "Sàn MRE (Malaysia)",
}
_STRONG_PCT = 2.0   # |%| ≥ 2 → "mạnh"
_MILD_PCT = 0.5     # |%| < 0.5 → "nhẹ"
_CONNECTORS = {"được", "do", "nhờ", "khi", "trong", "chịu", "bởi", "theo", "sau", "dù", "mặc",
               "phản", "cùng", "hưởng", "trước", "vì", "giữa", "với", "nhưng", "song", "tuy"}
_CAUSE_RE = re.compile(r"^[\s>*•-]*\[?\s*(OSE|SHANGHAI|SGX|MRE)\s*\]?\s*[|:]\s*T(?:uần)?\s*(\d{1,2})"
                       r"\s*(?:/|vs)\s*T(?:uần)?\s*(\d{1,2})\s*[|:]\s*(.+)$", re.IGNORECASE)


# ── Định dạng số kiểu Việt ──
def rounded(x: float, dec: int = 1) -> Decimal:
    """Làm tròn nửa lên (xa 0) đúng `dec` số lẻ — MỌI chữ/dấu chọn theo đúng số sẽ in ra."""
    return Decimal(str(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)


def vn(x: float | None, dec: int = 1) -> str:
    """2763.6 → '2.763,6' (làm tròn nửa lên). None → 'N/A'. Làm tròn ra 0 thì không in dấu '-'."""
    if x is None:
        return "N/A"
    q = rounded(x, dec)
    s = f"{abs(q):,.{dec}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if q < 0 else "") + s


def signed(x: float | None, dec: int = 1) -> str:
    """'+35,4' / '-26,3'; làm tròn ra 0 → '0,0' (không dấu — tránh '+0,0' khi thực tế âm)."""
    if x is None:
        return "N/A"
    return ("+" if rounded(x, dec) > 0 else "") + vn(x, dec)


def pct(x: float | None, dec: int = 1) -> str:
    """% có dấu kiểu Việt: '+1,3%' / '-1,0%' / '0,0%'. None → 'N/A'."""
    return "N/A" if x is None else signed(x, dec) + "%"


def direction(p: float | None, dec: int = 1) -> str:
    """Chiều giá theo ĐÚNG % in ra (`dec` số lẻ): 'tăng' / 'giảm' / 'đi ngang'."""
    if p is None:
        return "N/A"
    q = rounded(p, dec)
    return "tăng" if q > 0 else ("giảm" if q < 0 else "đi ngang")


def vn_native(x: float | None, unit: str | None) -> str:
    """Giá nội tệ: CNY/tấn số nguyên; còn lại 1 số lẻ (2 số lẻ nếu nguồn có số lẻ thứ hai)."""
    if x is None:
        return "N/A"
    if unit == "CNY/tấn":
        return vn(x, 0)
    return vn(x, 2) if round(x * 100) % 10 else vn(x, 1)


def dm_range(weeks: list[dict[str, Any]]) -> str:
    """'24/8 – 4/9' của các tuần TRONG KỲ (bỏ tuần mốc)."""
    span = weeks[1:] or weeks
    a, b = span[0]["mon"], span[-1]["fri"]
    return f"{int(a[8:10])}/{int(a[5:7])} – {int(b[8:10])}/{int(b[5:7])}"


# ── Nguyên nhân do AI viết ──
def parse_causes(lines: list[str]) -> dict[tuple[str, int, int], str]:
    """'OSE | T35/T34 | do ...' → {('OSE', 35, 34): 'do ...'}; dòng không đúng nhãn bị bỏ."""
    out: dict[tuple[str, int, int], str] = {}
    for line in lines:
        m = _CAUSE_RE.match(line or "")
        if m:
            cause = clean_cause(m.group(4))
            if cause:
                out[(m.group(1).upper(), int(m.group(2)), int(m.group(3)))] = cause
    return out


def clean_cause(s: str) -> str:
    s = re.sub(r"\*+", "", s or "").strip().strip(" ,;.")
    first = s.split(" ", 1)[0].lower()
    return s[0].lower() + s[1:] if s and first in _CONNECTORS else s


# ── III.1 ──
def _verb(p: float | None) -> str:
    """Động từ theo % ĐÃ LÀM TRÒN 1 số lẻ (số in trong ngoặc) — không lệch chữ với số."""
    if p is None:
        return "đạt"
    q = rounded(p)
    a = abs(q)
    if q == 0:
        return "đi ngang ở mức"
    if q > 0:
        return "tăng mạnh lên" if a >= _STRONG_PCT else ("nhích nhẹ lên" if a < _MILD_PCT else "tăng lên")
    return ("điều chỉnh giảm mạnh xuống" if a >= _STRONG_PCT
            else ("điều chỉnh nhẹ xuống" if a < _MILD_PCT else "điều chỉnh giảm xuống"))


def _grade_move(row: dict[str, Any], i: int) -> str | None:
    """Cụm giá cặp tuần i (values[i] → values[i+1]); None nếu tuần sau không có giá."""
    vals, pcts = row.get("values") or [], row.get("changes_pct") or []
    curr = vals[i + 1] if i + 1 < len(vals) else None
    if curr is None:
        return None
    p = pcts[i] if i < len(pcts) else None
    tail = f" ({pct(p)})" if p is not None else ""
    return f"{_verb(p)} **{vn(curr)} USD/tấn**{tail}"


def _join_vi(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " và " + items[-1]


def _dm(iso: str) -> str:
    return f"{int(iso[8:10])}/{int(iso[5:7])}"


_GAP_KINDS = (("no_price", "không có giá"), ("no_fx", "chưa quy đổi được USD"))


def gap_parts(items: list[dict[str, Any]], all_grades: list[str]) -> list[str]:
    """Ngày thiếu cả kỳ của 1 sàn (`exchange_gap_days`) → ['Không có giá ngày 25/8 và 31/8',
    'Chưa quy đổi được USD ngày 3/9 và 4/9 do thiếu tỷ giá USD/JPY', 'LATEX không có giá trong kỳ'…]."""
    parts = []
    for kind, lead in _GAP_KINDS:
        by_days: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for it in items:
            if it.get(kind):
                by_days.setdefault(tuple(it[kind]), []).append(it)
        for days, its in by_days.items():
            grades = [it["grade"] for it in its]
            who = lead[0].upper() + lead[1:] if set(grades) >= set(all_grades) else f"{', '.join(grades)} {lead}"
            whole = len(days) >= len(its[0].get("days") or [])
            when = "trong kỳ" if whole else f"ngày {_join_vi([_dm(d) for d in days])}"
            pairs = list(dict.fromkeys(it["fx_pair"] for it in its if it.get("fx_pair")))
            tail = f" do thiếu tỷ giá {', '.join(pairs)}" if kind == "no_fx" and pairs else ""
            parts.append(f"{who} {when}{tail}")
    return parts


def _range_text(s: dict[str, Any], lead: bool) -> str:
    unit = s.get("native_unit")

    def price(v: float, native: float | None) -> str:
        nat = f" (~**{vn_native(native, unit)} {unit}**)" if unit and native is not None else ""
        return f"**{vn(v)} USD/tấn**{nat}"

    if lead:
        return (f"**Cao nhất** đạt {price(s['high'], s.get('high_native'))} vào ngày {s['high_date']}; "
                f"**Thấp nhất** ghi nhận {price(s['low'], s.get('low_native'))} vào ngày {s['low_date']}.")
    return (f"Cao nhất {price(s['high'], s.get('high_native'))} ngày {s['high_date']}; "
            f"Thấp nhất {price(s['low'], s.get('low_native'))} ngày {s['low_date']}.")


def exchange_notes(rep: dict[str, Any], causes: dict[tuple[str, int, int], str]) -> list[str]:
    """Nhận định III.1 đủ số (từ bảng) + nguyên nhân AI."""
    weeks = rep.get("weeks") or []
    rows_by: dict[str, list[dict[str, Any]]] = {}
    for r in rep.get("exchange_rows") or []:
        rows_by.setdefault(r["exchange"], []).append(r)
    stats = {(s["exchange"], s["grade"]): s for s in rep.get("range_stats") or []}
    gaps: dict[str, list[dict[str, Any]]] = {}
    for g in rep.get("exchange_gap_days") or []:
        gaps.setdefault(g["exchange"], []).append(g)
    out: list[str] = []
    for exc, rows in rows_by.items():
        out.append(f"**{EXCHANGE_NAMES.get(exc, 'Sàn ' + exc)}:**")
        multi, n_head = len(rows) > 1, len(out)
        for i in range(len(weeks) - 1):
            moves = [(r["grade"], m) for r in rows if (m := _grade_move(r, i))]
            if not moves:
                continue
            a, b = weeks[i]["week_no"], weeks[i + 1]["week_no"]
            text = ("; ".join(f"{g} {m}" for g, m in moves) if multi
                    else f"Giá trung bình {moves[0][1]}")
            cause = causes.get((exc, b, a))
            out.append(f"> *Tuần {b} vs Tuần {a}:* {text}" + (f", {cause}." if cause else "."))
        grades = [r["grade"] for r in rows]
        parts = gap_parts(gaps.get(exc, []), grades)
        gap = f" *({'; '.join(parts)})*" if parts else ""
        ex_stats = [stats[(exc, g)] for g in grades if (exc, g) in stats]
        head = f"> *Mức giá biến động ({dm_range(weeks)}):*" if weeks else "> *Mức giá biến động:*"
        if not ex_stats:  # cả kỳ không có giá USD nào → 1 dòng lý do, không để tiêu đề trơ trọi
            if len(out) == n_head:
                out.append(f"> *{'; '.join(parts) or 'Không có giá trong kỳ'}*")
        elif not multi:
            out.append(f"{head} {_range_text(ex_stats[0], lead=True)}{gap}")
        else:
            out.append(head + gap)
            out += [f">> **{s['grade']}:** {_range_text(s, lead=False)}" for s in ex_stats]
    return out


# ── III.2 ──
def physical_lines(rep: dict[str, Any]) -> list[str]:
    """Gạch cao/thấp cả kỳ từng chủng loại giao ngay (2 số lẻ, kèm tuần) — bám mẫu tuần 35–36."""
    out = []
    for s in rep.get("physical_range_stats") or []:
        out.append(f"**{s['grade']}:** Cao nhất {vn(s['high'], 2)} USD/tấn ({s['high_date']} – Tuần "
                   f"{s['high_week_no']}), Thấp nhất {vn(s['low'], 2)} USD/tấn ({s['low_date']} – Tuần "
                   f"{s['low_week_no']}).")
    return out
