"""Báo cáo tuần v2 — bảng nhiều tuần, ghi chú thiếu giá, cao/thấp kỳ, III.3 mủ nước (hàm thuần)
+ 1 test tích hợp lưu/đọc payload (bỏ qua khi DB không chạy; tự dọn dữ liệu)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core.db import db_healthy
from app.services import weekly_period
from app.services import weekly_report_latex as latex
from app.services import weekly_report_tables as tables
from app.services.weekly_report_gaps import exchange_gap_lines, group_exchange_series, physical_gap_lines
from app.services.weekly_report_ranges import range_stat

TODAY = date(2026, 9, 13)


def _weeks(week_key: str, span: int) -> list[dict]:
    return weekly_period.period(week_key, span)["weeks"]


def _full(mon: str, price: float = 100.0, skip: tuple[str, ...] = ()) -> dict[str, float]:
    start = date.fromisoformat(mon)
    days = [(start + timedelta(days=i)).isoformat() for i in range(5)]
    return {d: price for d in days if d not in skip}


# ── TB tuần / +/- ──
def test_week_avgs_excludes_no_trading_and_missing():
    weeks = _weeks("2026-08-17", 1)  # [T33, T34]
    series = {"2026-08-10": 0.0, "2026-08-11": 2737.0, "2026-08-12": None, "2026-08-13": 2737.0,
              "2026-08-17": 2750.1, "2026-08-18": 2750.0}
    assert tables.week_avgs(series, weeks) == [2737.0, 2750.1]  # 2750,05 → nửa LÊN


def test_round_half_up_not_bankers():
    assert tables.round_half_up(2579.45, 1) == 2579.5
    assert tables.round_half_up(6.73165, 4) == 6.7317


def test_series_row_multi_week_changes_and_last_pair():
    row = tables.series_row("OSE", "RSS3", [2728.2, 2763.6, 2737.3])
    assert row["changes"] == [35.4, -26.3]
    assert row["changes_pct"] == [1.3, -0.95]
    assert (row["prev"], row["curr"], row["change_abs"], row["change_pct"]) == (2763.6, 2737.3, -26.3, -0.95)


def test_series_row_gaps_give_none():
    row = tables.series_row(None, "RSS3", [None, 2800.0, 2810.0])
    assert row["changes"] == [None, 10.0] and row["changes_pct"][0] is None


def test_native_of_sgx_cents_and_mre_none():
    assert tables.native_of("SGX:RSS3", {"usd": 2770.0}) == 277.0
    assert tables.native_of("OSE:RSS3", {"usd": 2761.4, "native": 439.0}) == 439.0
    assert tables.native_of("MRB:LATEX", {"usd": 1700.0, "native": 690.0}) is None
    assert tables.native_of("SGX:RSS3", {"usd": 0.0}) is None


# ── Ghi chú thiếu giá (văn mẫu tuần 35–36) ──
def _sample_groups(latex_zero: bool = False) -> list:
    w35, w36 = "2026-08-24", "2026-08-31"
    ose = {**_full(w35), **_full(w36, skip=("2026-09-03", "2026-09-04"))}
    mre = {**_full(w35, skip=("2026-08-25",)), **_full(w36, skip=("2026-08-31",))}
    sgx = {**_full(w35), **_full(w36)}
    series = {"OSE:RSS3": ose, "SHANGHAI:RSS3": dict(ose), "SGX:RSS3": sgx, "SGX:TSR20": sgx,
              "MRB:SMRCV": mre, "MRB:SMR20": mre,
              "MRB:LATEX": {**mre, "2026-08-26": 0.0} if latex_zero else mre}
    return group_exchange_series(tables.EXCHANGE_MAP, series)


def test_exchange_gaps_match_sample_wording():
    lines = exchange_gap_lines(_weeks("2026-08-24", 2)[1:], _sample_groups(), today=TODAY)
    assert lines == [
        "Tuần 24/8 - 28/8: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 25/8.",
        "Tuần 31/8 - 4/9: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 31/8; "
        "sàn OSE và SHANGHAI không có giá ngày 3/9 và 4/9.",
    ]


def test_exchange_gaps_partial_grades_and_zero_is_missing():
    lines = exchange_gap_lines(_weeks("2026-08-24", 1)[1:], _sample_groups(latex_zero=True), today=TODAY)
    assert lines == ["Tuần 24/8 - 28/8: sàn MRE (SMR CV, SMR20) không có giá ngày 25/8; "
                     "sàn MRE (LATEX) không có giá ngày 25/8 và 26/8."]


def test_gaps_ignore_today_and_future_days():
    groups = group_exchange_series(tables.EXCHANGE_MAP, {"OSE:RSS3": {"2026-09-07": 1.0}})
    # Hôm nay (9/9) có thể chưa quét giá → chỉ xét 7/9, 8/9.
    lines = exchange_gap_lines(_weeks("2026-09-07", 1)[1:], groups[:1], today=date(2026, 9, 9))
    assert lines == ["Tuần 7/9 - 11/9: sàn OSE không có giá ngày 8/9."]
    assert exchange_gap_lines(_weeks("2026-09-07", 1)[1:], groups[:1], today=date(2026, 9, 8)) == []
    assert exchange_gap_lines(_weeks("2026-09-14", 1)[1:], groups[:1], today=TODAY) == []


def test_physical_gaps_group_same_days():
    w = "2026-08-31"
    grades = [("RSS3", _full(w)), ("STR20", _full(w, skip=("2026-09-02",))),
              ("SMR20", _full(w, skip=("2026-09-02",))), ("LATEX", _full(w, skip=("2026-09-04",)))]
    assert physical_gap_lines(_weeks(w, 1)[1:], grades, today=TODAY) == [
        "Tuần 31/8 - 4/9: giá giao ngay STR20, SMR20 không có giá ngày 2/9; "
        "giá giao ngay LATEX không có giá ngày 4/9."
    ]


# ── Cao/thấp cả kỳ ──
def test_range_stat_whole_span_excludes_base_week_and_ties_earliest():
    weeks = _weeks("2026-08-24", 2)
    pts = {"2026-08-21": (9999.0, 1.0),            # tuần mốc → bỏ
           "2026-08-27": (2784.5, 448.2), "2026-08-31": (2784.5, 447.0),
           "2026-09-02": (2719.6, 438.5), "2026-09-03": (0.0, 0.0)}
    s = range_stat("OSE", "RSS3", pts, weeks[1:], "JPY/kg")
    assert (s["high"], s["high_date"], s["high_week_no"], s["high_native"]) == (2784.5, "27/08", 35, 448.2)
    assert (s["low"], s["low_date"], s["low_week_no"], s["low_native"]) == (2719.6, "02/09", 36, 438.5)
    assert s["native_unit"] == "JPY/kg"
    assert range_stat(None, "RSS3", {}, weeks[1:]) is None


# ── III.3 mủ nước ──
def test_latex_auto_bands_and_changes_v1_format():
    weeks = _weeks("2026-08-17", 1)
    values = {"A": {"2026-08-11": 515.0, "2026-08-18": 495.0},
              "B": {"2026-08-12": 540.0, "2026-08-19": 540.0, "2026-08-20": 0.0}}
    auto = latex.auto_bands(values, weeks)
    assert auto == [(515, 540), (495, 540)]
    assert latex.resolve(auto, None, None) == (["515 - 540", "495 - 540"], ["-20 /0"])


def test_latex_override_cell_wins_and_change_follows():
    auto = [(515, 540), (495, 540), (500, 545)]
    bands, changes = latex.resolve(auto, [None, "505 – 540", ""], [None, "+1 /+1"])
    assert bands == ["515 - 540", "505 – 540", "500 - 545"]
    assert changes == ["-10 /0", "+1 /+1"]


def test_latex_legacy_payload_maps_to_override_only_for_span_1():
    old = {"latex_prev": "515 – 540", "latex_curr": "480 - 530", "latex_change": "-35 /-10"}
    ov, cov = latex.overrides(old, 1)
    assert latex.resolve([(515, 540), (495, 540)], ov, cov) == (["515 – 540", "480 - 530"], ["-35 /-10"])
    assert latex.overrides(old, 2) == (None, None)
    assert latex.overrides({**old, "latex_override": [None, None]}, 1) == ([None, None], None)


def test_parse_band():
    assert latex.parse_band("515 – 540") == (515, 540)
    assert latex.parse_band("540") == (540, 540)
    assert latex.parse_band("không có") is None


def test_core_range_drops_outlier():
    assert latex.core_range([413, 538, 560, 580]) == (538, 580)


# ── PDF mapping (dataclass giả, đúng thứ tự tham số hợp đồng mục D) ──
def test_to_pdf_data_maps_contract_fields():
    from app.services import weekly_report_pdf

    models = SimpleNamespace(TableRow=lambda e, g, v: (e, g, v), WeekCol=lambda n, y, lb: (n, y, lb),
                             MacroSection=lambda t, b: (t, b), WeeklyReportData=lambda **kw: kw)
    per = weekly_period.period("2026-08-24", 2)
    rep = {**per, "exchange_rows": [tables.series_row("OSE", "RSS3", [1.0, 2.0, 3.0])],
           "physical_rows": [], "exchange_gaps": ["g"], "physical_gaps": [],
           "latex_bands": [None, None, None], "latex_changes": [None, None],
           "narrative": {"macro": [{"title": "T", "bullets": ["b"]}], "report_note": ["n"]}}
    data = weekly_report_pdf.to_pdf_data(rep, models)
    assert data["weeks"][2] == (36, 2026, "Tuần 36 (31/8 - 4/9)")
    assert data["exchange_rows"] == [("OSE", "RSS3", [1.0, 2.0, 3.0])]
    assert data["macro"] == [("T", ["b"])] and data["report_note"] == ["n"]
    assert weekly_report_pdf.pdf_filename(per["span_label"]) == "Bao-cao-tuan-35-36-2026.pdf"


def test_pdf_tables_one_week_use_35_36_layout():
    """Kỳ 1 tuần cũng bám mẫu 35–36: cột tuần + '+/- (T37/T36)' có dấu in đậm, không cột %, giá 1 số lẻ."""
    from app.services import weekly_report_pdf

    models, _ = weekly_report_pdf._pdf_pkg()
    from weekly import html_tables  # noqa: E402 - package nạp qua sys.path của _pdf_pkg

    d = models.WeeklyReportData(
        title_label="", date_range="", span_label="37/2026", prev_label="", movement_label="", next_label="",
        weeks=[models.WeekCol(36, 2026, "Tuần 36 (31/8 - 4/9)"), models.WeekCol(37, 2026, "Tuần 37 (7/9 - 11/9)")],
        exchange_rows=[models.TableRow("OSE", "RSS3", [2728.2, 2763.6]),
                       models.TableRow("SGX", "RSS3", [2760.0, 2733.7]),
                       models.TableRow("SGX", "TSR20", [2281.0, 2281.0])],
        physical_rows=[models.TableRow(None, "RSS3", [2798.34, 2810.26])],
        latex_bands=["515 - 540", "520 - 545"], latex_changes=["+5"])
    ex, ph, lx = html_tables.exchange_table(d), html_tables.physical_table(d), html_tables.latex_table(d)
    assert "%" not in ex + ph and "(" not in ex.split("<tbody>")[1]
    assert "+/-<br>(T37/T36)" in ex and "Tuần 37<br>(7/9 - 11/9)" in ex
    assert "<b>+35,4</b>" in ex and "<b>-26,3</b>" in ex and "<b>0</b>" in ex
    assert "2.798,3" in ph and "2.810,3" in ph and "<b>+11,9</b>" in ph
    assert "Biến động<br>(T37/T36)" in lx


# ── Tích hợp DB: lưu span + override, đọc lại, danh sách, xoá ──
@pytest.mark.skipif(not db_healthy(), reason="DB không chạy")
def test_save_span_and_override_roundtrip():
    from app.services import weekly_report_service as svc

    key = "2099-01-05"  # tuần giả, không có giá
    try:
        rep = svc.save_narrative(key, {"span_weeks": 2, "latex_override": [None, "500 - 510", None],
                                       "latex_prev": "1 - 2", "latex_curr": "3 - 4"})
        saved = svc.load_saved(key)
        assert saved["span_weeks"] == 2 and saved["latex_prev"] is None
        assert svc.saved_span(key) == 2
        assert len(rep["weeks"]) == 3 and rep["span_label"] == "2-3/2099"
        assert rep["latex_bands"] == [None, "500 - 510", None]
        assert rep["narrative"]["latex_override"] == [None, "500 - 510", None]
        assert rep["exchange_rows"][0]["values"] == [None, None, None]
        row = next(r for r in svc.list_reports() if r["week_key"] == key)
        assert row["span_weeks"] == 2 and row["label"].startswith("Tuần 2-3/2099")
    finally:
        svc.delete_report(key)
    assert svc.load_saved(key) == {}
