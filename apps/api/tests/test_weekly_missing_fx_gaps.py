"""Báo cáo tuần — phân biệt ngày KHÔNG CÓ GIÁ với ngày CÓ GIÁ NỘI TỆ nhưng THIẾU TỶ GIÁ (hàm thuần).

Bối cảnh thật kỳ 24/8/2026 (gộp 2 tuần): OSE & SHANGHAI ngày 3/9, 4/9 có giá JPY/CNY nhưng chưa có
tỷ giá USD/JPY, USD/CNY đúng ngày → trước đây bị ghi nhầm "không có giá". Cả hai loại vẫn KHÔNG vào
TB/cao-thấp USD (không đắp tỷ giá ngày khác).
"""

from __future__ import annotations

from datetime import date, timedelta

from app.services import weekly_ai_compose as compose
from app.services import weekly_period
from app.services import weekly_report_tables as tables
from app.services.weekly_ai_context import _session
from app.services.weekly_report_gaps import (
    NO_FX,
    NO_PRICE,
    day_state,
    exchange_day_gaps,
    exchange_gap_lines,
    group_exchange_series,
    physical_gap_lines,
)
from app.services.weekly_report_ranges import range_stat

TODAY = date(2026, 9, 13)
W35, W36 = "2026-08-24", "2026-08-31"


def _in_span(key: str, span: int) -> list[dict]:
    return weekly_period.period(key, span)["weeks"][1:]


def _cells(mon: str, usd: float = 2700.0, native: float | None = None, skip=(), no_fx=()) -> dict:
    """Ô lưới sàn 5 ngày: `skip` = không có ô; `no_fx` = có nội tệ, usd None."""
    out = {}
    for i in range(5):
        d = (date.fromisoformat(mon) + timedelta(days=i)).isoformat()
        if d in skip:
            continue
        out[d] = {"usd": None, "native": 430.0} if d in no_fx else {"usd": usd, "native": native}
    return out


def _real_like_groups() -> list:
    ose = {**_cells(W35, native=440.0), **_cells(W36, native=430.0, no_fx=("2026-09-03", "2026-09-04"))}
    mre = {**_cells(W35, skip=("2026-08-25",)), **_cells(W36, skip=("2026-08-31",))}
    series = {"OSE:RSS3": ose, "SHANGHAI:RSS3": dict(ose), "SGX:RSS3": _cells(W35) | _cells(W36),
              "SGX:TSR20": _cells(W35) | _cells(W36), "MRB:SMRCV": mre, "MRB:SMR20": mre, "MRB:LATEX": mre}
    return group_exchange_series(tables.EXCHANGE_MAP, series, tables.FX_PAIR_OF)


def test_day_state_three_states() -> None:
    assert day_state({"usd": 2719.6, "native": 432.2}) is None
    assert day_state({"usd": None, "native": 428.7}) == NO_FX
    assert day_state({"usd": None, "native": None}) == NO_PRICE
    assert day_state({"usd": 0.0}) == NO_PRICE and day_state({"usd": None, "native": 0.0}) == NO_PRICE
    assert day_state(None) == NO_PRICE and day_state(2750.0) is None   # chuỗi giao ngay = số USD


def test_fx_pair_comes_from_market_meta() -> None:
    assert tables.FX_PAIR_OF["OSE:RSS3"] == "USD/JPY" and tables.FX_PAIR_OF["SHANGHAI:RSS3"] == "USD/CNY"
    assert tables.FX_PAIR_OF["MRB:LATEX"] == "USD/MYR" and tables.FX_PAIR_OF["SGX:RSS3"] is None


def test_gap_lines_separate_missing_fx_from_no_price() -> None:
    assert exchange_gap_lines(_in_span(W35, 2), _real_like_groups(), today=TODAY) == [
        "Tuần 24/8 - 28/8: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 25/8.",
        "Tuần 31/8 - 4/9: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 31/8; "
        "sàn OSE và SHANGHAI chưa quy đổi được USD ngày 3/9 và 4/9 (thiếu tỷ giá USD/JPY, USD/CNY).",
    ]


def test_gap_lines_mixed_same_grade_and_same_days_orders_no_price_first() -> None:
    latex = _cells(W36, skip=("2026-09-01",), no_fx=("2026-09-01", "2026-09-03"))  # 1/9 bỏ ô → không có giá
    ose = _cells(W36, no_fx=("2026-09-01",))
    series = {"MRB:SMRCV": _cells(W36), "MRB:SMR20": _cells(W36), "MRB:LATEX": latex, "OSE:RSS3": ose}
    groups = group_exchange_series(tables.EXCHANGE_MAP, series, tables.FX_PAIR_OF)
    groups = [g for g in groups if g[0] in ("OSE", "MRE")]
    assert exchange_gap_lines(_in_span(W36, 1), groups, today=TODAY) == [
        "Tuần 31/8 - 4/9: sàn MRE (LATEX) không có giá ngày 1/9; sàn OSE chưa quy đổi được USD ngày 1/9 "
        "(thiếu tỷ giá USD/JPY); sàn MRE (LATEX) chưa quy đổi được USD ngày 3/9 (thiếu tỷ giá USD/MYR)."]


def test_whole_week_missing_says_ca_tuan() -> None:
    weeks = _in_span(W35, 1)
    grades = [(g, {}) for g in ("RSS3", "STR20", "SMR20", "LATEX")]
    assert physical_gap_lines(weeks, grades, today=TODAY) == [
        "Tuần 24/8 - 28/8: chưa có giá giao ngay RSS3, STR20, SMR20, LATEX cả tuần."]
    groups = group_exchange_series(tables.EXCHANGE_MAP, {"OSE:RSS3": {}, "SHANGHAI:RSS3": _cells(W35, no_fx=(
        "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"))}, tables.FX_PAIR_OF)
    assert exchange_gap_lines(weeks, groups[:2], today=TODAY) == [
        "Tuần 24/8 - 28/8: sàn OSE chưa có giá cả tuần; sàn SHANGHAI chưa quy đổi được USD cả tuần "
        "(thiếu tỷ giá USD/CNY)."]
    # Tuần đang dở (mới qua 2 ngày) thì liệt kê ngày, không nói "cả tuần".
    assert physical_gap_lines(weeks, grades[:1], today=date(2026, 8, 26)) == [
        "Tuần 24/8 - 28/8: giá giao ngay RSS3 không có giá ngày 24/8 và 25/8."]


def test_exchange_day_gaps_and_range_stat_no_fx_flag() -> None:
    weeks = _in_span(W35, 2)
    items = exchange_day_gaps(weeks, _real_like_groups(), today=TODAY)
    ose = next(i for i in items if i["exchange"] == "OSE")
    assert ose["no_fx"] == ["2026-09-03", "2026-09-04"] and ose["no_price"] == [] and ose["fx_pair"] == "USD/JPY"
    assert len(ose["days"]) == 10 and not any(i["exchange"] == "SGX" for i in items)
    cells = _real_like_groups()[0][1][0][1]
    pts = {d: (c["usd"], c["native"]) for d, c in cells.items()}
    pts["2026-08-29"] = (9999.0, 1.0)                                  # Thứ 7 → không xét (khớp TB tuần)
    s = range_stat("OSE", "RSS3", pts, weeks, "JPY/kg", ose["no_fx"])
    assert s["high"] == 2700.0 and s["high_date"] == "24/08"          # USD chỉ từ ngày quy đổi được
    assert s["no_fx_dates"] == ["03/09", "04/09"]
    assert range_stat(None, "RSS3", {"2026-08-24": (2700.0, None)}, weeks)["no_fx_dates"] == []


def test_compose_notes_by_kind_and_empty_exchange() -> None:
    weeks = weekly_period.period(W35, 2)["weeks"]
    days = [d for w in weeks[1:] for d in (w["mon"],)]
    base = {"exchange": "SHANGHAI", "grade": "RSS3", "fx_pair": "USD/CNY", "days": days}
    rep = {"weeks": weeks, "range_stats": [],
           "exchange_rows": [{"exchange": "SHANGHAI", "grade": "RSS3", "values": [2750.0, None, None],
                              "changes_pct": [None, None]}],
           "exchange_gap_days": [{**base, "no_price": days, "no_fx": []}]}
    assert compose.exchange_notes(rep, {}) == ["**Sàn SHANGHAI (Trung Quốc):**", "> *Không có giá trong kỳ*"]
    rep["exchange_gap_days"] = [{**base, "no_price": [], "no_fx": days}]
    assert compose.exchange_notes(rep, {})[1] == "> *Chưa quy đổi được USD trong kỳ do thiếu tỷ giá USD/CNY*"
    rep["exchange_gap_days"] = []                                       # kỳ chưa tới ngày nào để xét
    assert compose.exchange_notes(rep, {})[1] == "> *Không có giá trong kỳ*"


def test_compose_gap_parts_mixed_grades() -> None:
    items = [{"grade": "SMR20", "days": ["a"] * 10, "no_price": ["2026-08-25"], "no_fx": []},
             {"grade": "LATEX", "fx_pair": "USD/MYR", "days": ["a"] * 10, "no_price": ["2026-08-25"],
              "no_fx": ["2026-09-03"]}]
    assert compose.gap_parts(items, ["SMR CV", "SMR20", "LATEX"]) == [
        "SMR20, LATEX không có giá ngày 25/8", "LATEX chưa quy đổi được USD ngày 3/9 do thiếu tỷ giá USD/MYR"]


def test_daily_block_session_label() -> None:
    assert _session({"usd": 2719.6, "native": 432.2}) == "2.719,6"
    assert _session({"usd": None, "native": 428.7}) == "thiếu tỷ giá"
    assert _session({"usd": None}) == "nghỉ" and _session({"usd": 0.0}) == "nghỉ"
