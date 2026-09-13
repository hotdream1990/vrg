"""Kỳ báo cáo tuần — 1 tuần hoặc GỘP nhiều tuần liền nhau (vd tuần 35–36 có lễ Quốc khánh).

Hàm thuần (không DB, không mạng) để service bảng số, nguồn thị trường, tin tức và PDF dùng chung
MỘT cách tính tuần/nhãn. Khoá báo cáo vẫn là Thứ 2 ISO của tuần ĐẦU kỳ; số tuần gộp nằm trong
payload (`span_weeks`). Cột mốc so sánh (`weeks[0]`) luôn là tuần liền TRƯỚC kỳ báo cáo.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

MIN_SPAN = 1
MAX_SPAN = 3  # gộp tối đa 3 tuần — bảng A4 dọc còn đọc được (Sàn · SP · 4 cột giá · 3 cột +/-)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_key_for(d: date) -> str:
    """Ngày Thứ 2 (ISO) của tuần chứa `d` — dùng làm khoá tuần."""
    return monday_of(d).isoformat()


def clamp_span(n: Any) -> int:
    try:
        v = int(n)
    except (TypeError, ValueError):
        return MIN_SPAN
    return max(MIN_SPAN, min(MAX_SPAN, v))


def _dm(d: date) -> str:
    return f"{d.day}/{d.month}"


def range_text(start: date, end: date) -> str:
    """'24/8 – 28/8/2026' (cùng năm) · '29/12/2025 – 2/1/2026' (khác năm)."""
    if start.year == end.year:
        return f"{_dm(start)} – {_dm(end)}/{end.year}"
    return f"{_dm(start)}/{start.year} – {_dm(end)}/{end.year}"


def _week(mon: date) -> dict[str, Any]:
    fri = mon + timedelta(days=4)
    iso = mon.isocalendar()
    return {
        "week_no": iso[1], "year": iso[0],
        "mon": mon.isoformat(), "fri": fri.isoformat(),
        "label": f"Tuần {iso[1]} ({_dm(mon)} - {_dm(fri)})",   # tiêu đề cột bảng (bám mẫu)
        "short": f"T{iso[1]}",
        "range": range_text(mon, fri),
    }


def _join_vi(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " và " + items[-1]


def period(week_key: str, span: Any = 1) -> dict[str, Any]:
    """Toàn bộ nhãn/mốc ngày của kỳ báo cáo bắt đầu từ Thứ 2 `week_key`, gộp `span` tuần."""
    n = clamp_span(span)
    first_mon = monday_of(date.fromisoformat(week_key))
    weeks = [_week(first_mon + timedelta(days=7 * i)) for i in range(-1, n)]  # [mốc, tuần 1..n]
    base, span_weeks = weeks[0], weeks[1:]
    first, last = span_weeks[0], span_weeks[-1]
    nxt = _week(first_mon + timedelta(days=7 * n))
    start, end = date.fromisoformat(first["mon"]), date.fromisoformat(last["fri"])

    same_year = first["year"] == last["year"]
    if n == 1:
        title = f"Tuần {first['week_no']} năm {first['year']}"
        span_label = f"{first['week_no']}/{first['year']}"
    elif same_year:
        title = f"Tuần {_join_vi([str(w['week_no']) for w in span_weeks])} năm {first['year']}"
        span_label = f"{first['week_no']}-{last['week_no']}/{first['year']}"
    else:  # kỳ vắt qua năm ISO, vd tuần 53/2026 và 1/2027
        title = "Tuần " + _join_vi([f"{w['week_no']}/{w['year']}" for w in span_weeks])
        span_label = f"{first['week_no']}/{first['year']}-{last['week_no']}/{last['year']}"

    date_range = f"{_dm(start)}/{start.year} – {_dm(end)}/{end.year}"
    return {
        "week_key": first_mon.isoformat(),
        "span_weeks": n,
        "weeks": weeks,
        "week_no": first["week_no"], "year": first["year"],
        "last_week_no": last["week_no"], "last_year": last["year"],
        "prev_week_no": base["week_no"], "prev_year": base["year"],
        "next_week_no": nxt["week_no"], "next_year": nxt["year"],
        "date_range": date_range,                                   # '24/8/2026 – 4/9/2026'
        "title_label": title,                                       # 'Tuần 35 và 36 năm 2026'
        "span_label": span_label,                                   # '35-36/2026'
        "prev_label": f"Tuần {base['week_no']}/{base['year']} ({base['range']})",
        "movement_label": f"Tuần {span_label} ({range_text(start, end)})",
        "next_label": f"Tuần {nxt['week_no']}/{nxt['year']}",
        "prev_col_label": base["label"],
        "curr_col_label": last["label"],
        "list_label": f"Tuần {span_label} ({date_range})",
        "date_from": base["mon"],                                   # đầu tuần mốc (để truy vấn giá)
        "date_to": last["fri"],                                     # cuối kỳ báo cáo
        "span_from": first["mon"],
    }
