"""Ghi chú tự động dưới bảng Báo cáo tuần — "sàn X không có giá ngày …" (hàm thuần, không DB).

Văn mẫu tuần 35–36:
  "Tuần 31/8 - 4/9: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 31/8; sàn OSE và SHANGHAI
   chưa quy đổi được USD ngày 3/9 và 4/9 (thiếu tỷ giá USD/JPY, USD/CNY)."
Quy tắc: xét Thứ 2–6 ĐÃ QUA (< hôm nay — hôm nay có thể chưa quét) của từng tuần TRONG KỲ (không gồm
tuần mốc). Mỗi ngày của 1 chủng loại ở một trong 3 trạng thái:
  - có giá USD/tấn → không ghi chú;
  - KHÔNG CÓ GIÁ (`NO_PRICE`): ô thiếu hoặc giá 0 (No Trading);
  - CHƯA QUY ĐỔI ĐƯỢC USD (`NO_FX`): có giá nội tệ nhưng thiếu tỷ giá ĐÚNG ngày đó — sàn vẫn giao
    dịch, KHÔNG phải nghỉ. Không đắp tỷ giá ngày khác → ngày này vẫn không vào TB USD.
Sàn nhiều chủng loại luôn ghi chủng loại trong ngoặc; các vế cùng trạng thái + cùng tập ngày gộp làm
một; các vế xếp theo ngày thiếu sớm nhất (cùng ngày thì "không có giá" trước). Thiếu đủ 5 ngày của
tuần → "chưa có giá … cả tuần".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, NamedTuple

from app.services.weekly_report_tables import Series, is_price

NO_PRICE = "no_price"
NO_FX = "no_fx"
_WEEKDAYS = 5

# (sàn, [(chủng loại, chuỗi ngày → ô lưới sàn, cặp tỷ giá quy đổi | None)])
Group = tuple[str, list[tuple[str, Series, str | None]]]


class Entry(NamedTuple):
    kind: str                   # NO_PRICE | NO_FX
    label: str                  # 'OSE' · 'MRE (LATEX)' · 'STR20'
    days: tuple[str, ...]       # ngày thiếu ISO
    fx_pairs: tuple[str, ...]   # cặp tỷ giá thiếu (chỉ NO_FX)


def _dm(iso: str) -> str:
    return f"{int(iso[8:10])}/{int(iso[5:7])}"


def _join_vi(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " và " + items[-1]


def weekdays_before(week: dict[str, Any], today: date) -> list[str]:
    """Thứ 2–6 của tuần, TRƯỚC `today` (hôm nay chưa chắc đã quét giá → không tính thiếu)."""
    mon = date.fromisoformat(week["mon"])
    return [d.isoformat() for i in range(_WEEKDAYS) if (d := mon + timedelta(days=i)) < today]


def day_state(v: Any) -> str | None:
    """None = có giá USD. `v` = ô lưới sàn {usd, native?} hoặc thẳng giá USD/tấn (giao ngay)."""
    cell = v if isinstance(v, dict) else {"usd": v}
    if is_price(cell.get("usd")):
        return None
    return NO_FX if is_price(cell.get("native")) else NO_PRICE


def missing_days(series: Series, days: list[str], kind: str = NO_PRICE) -> tuple[str, ...]:
    return tuple(d for d in days if day_state(series.get(d)) == kind)


def _when(miss: tuple[str, ...], whole_week: bool) -> str:
    return "cả tuần" if whole_week and len(miss) == _WEEKDAYS else f"ngày {_join_vi([_dm(d) for d in miss])}"


def _lines(weeks: list[dict[str, Any]], today: date, entries_for: Callable[[list[str]], list[Entry]],
           render: Callable[[str, list[Entry], str], str]) -> list[str]:
    out = []
    for w in weeks:
        days = weekdays_before(w, today)
        merged: dict[tuple[str, tuple[str, ...]], list[Entry]] = {}
        for e in entries_for(days) if days else []:
            merged.setdefault((e.kind, e.days), []).append(e)
        if not merged:
            continue
        order = sorted(merged.items(), key=lambda kv: (kv[0][1][0], kv[0][0] != NO_PRICE))
        clauses = [render(kind, es, _when(miss, len(days) == _WEEKDAYS)) for (kind, miss), es in order]
        out.append(f"Tuần {_dm(w['mon'])} - {_dm(w['fri'])}: {'; '.join(clauses)}.")
    return out


def _exchange_entries(groups: list[Group], days: list[str]) -> list[Entry]:
    entries: list[Entry] = []
    for exc, grades in groups:
        for kind in (NO_PRICE, NO_FX):
            by_miss: dict[tuple[str, ...], list[tuple[str, str | None]]] = {}
            for grade, series, pair in grades:
                if miss := missing_days(series, days, kind):
                    by_miss.setdefault(miss, []).append((grade, pair))
            for miss, items in by_miss.items():
                names = ", ".join(g for g, _ in items)
                label = f"{exc} ({names})" if len(grades) > 1 else exc
                pairs = tuple(p for _, p in items if p) if kind == NO_FX else ()
                entries.append(Entry(kind, label, miss, pairs))
    return entries


def _render_exchange(kind: str, es: list[Entry], when: str) -> str:
    who = f"sàn {_join_vi([e.label for e in es])}"
    if kind == NO_FX:
        pairs = list(dict.fromkeys(p for e in es for p in e.fx_pairs))
        return f"{who} chưa quy đổi được USD {when}" + (f" (thiếu tỷ giá {', '.join(pairs)})" if pairs else "")
    return f"{who} chưa có giá cả tuần" if when == "cả tuần" else f"{who} không có giá {when}"


def exchange_gap_lines(weeks: list[dict[str, Any]], groups: list[Group], today: date | None = None) -> list[str]:
    """`groups` từ `group_exchange_series` (chuỗi ngày → ô lưới sàn) theo thứ tự hiển thị."""
    return _lines(weeks, today or date.today(), lambda days: _exchange_entries(groups, days), _render_exchange)


def exchange_day_gaps(weeks: list[dict[str, Any]], groups: list[Group],
                      today: date | None = None) -> list[dict[str, Any]]:
    """Ngày thiếu CẢ KỲ theo từng (sàn, chủng loại) — dữ liệu có cấu trúc cho nhận định III.1 + cao/thấp.

    → [{exchange, grade, fx_pair, days (mọi ngày đã xét), no_price: [ISO], no_fx: [ISO]}], chỉ chủng
    loại có ngày thiếu.
    """
    days = [d for w in weeks for d in weekdays_before(w, today or date.today())]
    out = []
    for exc, grades in groups:
        for grade, series, pair in grades:
            no_price, no_fx = missing_days(series, days, NO_PRICE), missing_days(series, days, NO_FX)
            if no_price or no_fx:
                out.append({"exchange": exc, "grade": grade, "fx_pair": pair, "days": days,
                            "no_price": list(no_price), "no_fx": list(no_fx)})
    return out


def _render_physical(_kind: str, es: list[Entry], when: str) -> str:
    names = ", ".join(e.label for e in es)
    return f"chưa có giá giao ngay {names} cả tuần" if when == "cả tuần" else f"giá giao ngay {names} không có giá {when}"


def physical_gap_lines(weeks: list[dict[str, Any]], grades: list[tuple[str, Series]],
                       today: date | None = None) -> list[str]:
    """`grades` = [(chủng loại, chuỗi ngày→USD/tấn)] theo thứ tự hiển thị."""
    def entries_for(days: list[str]) -> list[Entry]:
        return [Entry(NO_PRICE, g, miss, ()) for g, s in grades if (miss := missing_days(s, days))]

    return _lines(weeks, today or date.today(), entries_for, _render_physical)


def group_exchange_series(exchange_map: list[tuple[str, str, str]], series_by_key: dict[str, Series],
                          fx_pair_of: dict[str, str | None] | None = None) -> list[Group]:
    """Gom EXCHANGE_MAP phẳng thành [(sàn, [(chủng loại, chuỗi, cặp tỷ giá)])] giữ thứ tự."""
    groups: dict[str, list[tuple[str, Series, str | None]]] = {}
    for exc, grade, key in exchange_map:
        groups.setdefault(exc, []).append((grade, series_by_key.get(key, {}), (fx_pair_of or {}).get(key)))
    return list(groups.items())
