"""Test dựng phần số nhận định III.1/III.2 + parse nguyên nhân AI + parse khung nhãn (hàm thuần).

FIXTURE: dict mô phỏng `weekly_report_service.build_report` theo hợp đồng v2 cho kỳ Tuần 35–36/2026
(số bảng, gaps, range_stats khớp mẫu thật tuần 35–36; physical_range_stats lấy từ văn mẫu vì hệ thống
không có giá giao ngay sau 20/8). Không đọc DB.
"""

from __future__ import annotations

from app.services import weekly_ai
from app.services import weekly_ai_compose as compose


def _week(no: int, mon: str, fri: str) -> dict:
    return {"week_no": no, "year": 2026, "mon": mon, "fri": fri, "short": f"T{no}",
            "label": f"Tuần {no}"}


def _row(exc: str | None, grade: str, values: list, pcts: list) -> dict:
    return {"exchange": exc, "grade": grade, "values": values, "changes_pct": pcts,
            "changes": [round(b - a, 1) for a, b in zip(values, values[1:])]}


def _stat(exc, grade, hi, hd, hw, hn, lo, ld, lw, ln, unit) -> dict:
    return {"exchange": exc, "grade": grade, "high": hi, "high_date": hd, "high_week_no": hw,
            "high_native": hn, "low": lo, "low_date": ld, "low_week_no": lw, "low_native": ln,
            "native_unit": unit}


DAYS = ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
        "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]


def _gap(exc, grade, pair, no_price=(), no_fx=()) -> dict:
    return {"exchange": exc, "grade": grade, "fx_pair": pair, "days": DAYS,
            "no_price": list(no_price), "no_fx": list(no_fx)}


REP = {
    "weeks": [_week(34, "2026-08-17", "2026-08-21"), _week(35, "2026-08-24", "2026-08-28"),
              _week(36, "2026-08-31", "2026-09-04")],
    "exchange_rows": [
        _row("OSE", "RSS3", [2728.1, 2763.6, 2737.3], [1.3, -0.95]),
        _row("SGX", "RSS3", [2760.6, 2754.8, 2732.0], [-0.21, -0.83]),
        _row("SGX", "TSR20", [2281.0, 2374.0, 2356.0], [4.08, -0.76]),
        _row("MRE", "SMR CV", [2917.1, 2938.4, 2948.4], [0.73, 0.34]),
        _row("MRE", "SMR20", [2337.6, 2426.1, 2417.6], [3.79, -0.35]),
        _row("MRE", "LATEX", [1687.6, 1701.2, 1705.3], [0.81, 0.24]),
    ],
    "exchange_gaps": [
        "Tuần 24/8 - 28/8: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 25/8.",
        "Tuần 31/8 - 4/9: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 31/8; sàn OSE và SHANGHAI "
        "chưa quy đổi được USD ngày 3/9 và 4/9 (thiếu tỷ giá USD/JPY, USD/CNY).",
    ],
    # Ngày thiếu cả kỳ theo (sàn, chủng loại) — khớp dữ liệu thật kỳ 24/8: OSE 3/9, 4/9 có giá JPY nhưng
    # thiếu tỷ giá USD/JPY; MRE không có giá 25/8 và 31/8.
    "exchange_gap_days": [
        _gap("OSE", "RSS3", "USD/JPY", no_fx=["2026-09-03", "2026-09-04"]),
        *[_gap("MRE", g, None, no_price=["2026-08-25", "2026-08-31"]) for g in ("SMR CV", "SMR20", "LATEX")],
    ],
    "range_stats": [
        _stat("OSE", "RSS3", 2784.5, "27/08", 35, 443.6, 2719.6, "02/09", 36, 432.2, "JPY/kg"),
        _stat("SGX", "RSS3", 2780.0, "31/08", 36, 278.0, 2708.0, "03/09", 36, 270.8, "US cent/kg"),
        _stat("SGX", "TSR20", 2430.0, "31/08", 36, 243.0, 2327.0, "03/09", 36, 232.7, "US cent/kg"),
        _stat("MRE", "SMR20", 2440.0, "28/08", 35, None, 2407.5, "02/09", 36, None, None),
    ],
    "physical_range_stats": [
        _stat(None, "RSS3", 2829.4, "25/08", 35, None, 2749.1, "03/09", 36, None, None),
    ],
}


def test_vn_number_format() -> None:
    assert compose.vn(2763.6) == "2.763,6"
    assert compose.vn(-26.3) == "-26,3"
    assert compose.pct(-0.95) == "-1,0%" and compose.pct(1.3) == "+1,3%"
    assert compose.vn(2829.4, 2) == "2.829,40"
    assert compose.vn_native(18960.0, "CNY/tấn") == "18.960"
    assert compose.vn_native(223.85, "US cent/kg") == "223,85"


def test_parse_causes() -> None:
    causes = compose.parse_causes([
        "OSE | T35/T34 | Được nâng đỡ bởi đồng Yên yếu.",
        "- SGX | T36/T35 | do tâm lý chốt lời ngắn hạn",
        "không đúng nhãn",
    ])
    assert causes == {("OSE", 35, 34): "được nâng đỡ bởi đồng Yên yếu",
                      ("SGX", 36, 35): "do tâm lý chốt lời ngắn hạn"}


def test_exchange_notes_single_grade_matches_sample_format() -> None:
    lines = compose.exchange_notes(REP, {("OSE", 35, 34): "được nâng đỡ bởi đồng Yên (JPY) yếu"})
    ose = lines[:4]
    assert ose[0] == "**Sàn OSE (Nhật Bản):**"
    assert ose[1] == ("> *Tuần 35 vs Tuần 34:* Giá trung bình tăng lên **2.763,6 USD/tấn** (+1,3%), "
                      "được nâng đỡ bởi đồng Yên (JPY) yếu.")
    assert ose[2] == "> *Tuần 36 vs Tuần 35:* Giá trung bình điều chỉnh giảm xuống **2.737,3 USD/tấn** (-1,0%)."
    assert ose[3] == ("> *Mức giá biến động (24/8 – 4/9):* **Cao nhất** đạt **2.784,5 USD/tấn** "
                      "(~**443,6 JPY/kg**) vào ngày 27/08; **Thấp nhất** ghi nhận **2.719,6 USD/tấn** "
                      "(~**432,2 JPY/kg**) vào ngày 02/09. *(Chưa quy đổi được USD ngày 3/9 và 4/9 do thiếu tỷ giá "
                      "USD/JPY)*")


def test_exchange_notes_multi_grade_uses_level3_lines() -> None:
    lines = compose.exchange_notes(REP, {("SGX", 35, 34): "nhờ lực cầu cao su khối tích cực"})
    i = lines.index("**Sàn SGX (Singapore):**")
    assert lines[i + 1] == ("> *Tuần 35 vs Tuần 34:* RSS3 điều chỉnh nhẹ xuống **2.754,8 USD/tấn** (-0,2%); "
                            "TSR20 tăng mạnh lên **2.374,0 USD/tấn** (+4,1%), nhờ lực cầu cao su khối tích cực.")
    assert lines[i + 3] == "> *Mức giá biến động (24/8 – 4/9):*"
    assert lines[i + 4] == (">> **RSS3:** Cao nhất **2.780,0 USD/tấn** (~**278,0 US cent/kg**) ngày 31/08; "
                            "Thấp nhất **2.708,0 USD/tấn** (~**270,8 US cent/kg**) ngày 03/09.")
    j = lines.index("**Sàn MRE (Malaysia):**")
    assert lines[j + 3] == "> *Mức giá biến động (24/8 – 4/9):* *(Không có giá ngày 25/8 và 31/8)*"
    assert lines[j + 4].startswith(">> **SMR20:** Cao nhất **2.440,0 USD/tấn** ngày 28/08;")


def test_physical_lines_two_decimals_with_week() -> None:
    assert compose.physical_lines(REP) == [
        "**RSS3:** Cao nhất 2.829,40 USD/tấn (25/08 – Tuần 35), Thấp nhất 2.749,10 USD/tấn (03/09 – Tuần 36)."]
    assert compose.physical_lines({"physical_range_stats": []}) == []


def test_numbers_in_composed_notes_are_grounded() -> None:
    from app.services.weekly_ai_context import _tables_block
    from app.services.weekly_number_check import unverified_numbers

    rep = {**REP, "physical_rows": [], "physical_gaps": [], "latex_bands": [], "latex_changes": []}
    for r in rep["exchange_rows"]:
        r.setdefault("changes", [])
    ctx = "\n".join(_tables_block(rep))
    assert unverified_numbers(compose.exchange_notes(REP, {}) + compose.physical_lines(REP), ctx) == []


def test_parse_sections_keeps_levels_and_bold() -> None:
    out = ("### I\nTuần 34 ghi nhận…\n### IV.1\n- Theo ANRPC…\n**Sản lượng sản xuất toàn cầu:** 15,279 triệu tấn\n"
           "> Thái Lan +2,1%\n* gạch sao\n### V\nMở đầu\n- Hỗ trợ giá: El Niño\n### III.2\nBỎ TRỐNG")
    p = weekly_ai._parse_sections(out)
    assert p["I"] == ["Tuần 34 ghi nhận…"]
    assert weekly_ai._strip_lead_dash(p["IV.1"]) == [
        "Theo ANRPC…", "**Sản lượng sản xuất toàn cầu:** 15,279 triệu tấn", "> Thái Lan +2,1%", "gạch sao"]
    assert p["V"] == ["Mở đầu", "- Hỗ trợ giá: El Niño"]
    assert p["III.2"] == []


def test_finalize_splits_weeks_and_drops_macro_title() -> None:
    line = ("Kỳ này thị trường chuyển từ tăng sang giằng co. Trong Tuần 35 (24/8 – 28/8), giá tăng nhẹ. "
            "Sang Tuần 36 (31/8 – 4/9), áp lực chốt lời gia tăng.")
    assert weekly_ai._finalize("movement", [line], REP) == [
        "Kỳ này thị trường chuyển từ tăng sang giằng co.", "Trong Tuần 35 (24/8 – 28/8), giá tăng nhẹ.",
        "Sang Tuần 36 (31/8 – 4/9), áp lực chốt lời gia tăng."]
    title = "1. Cung – Cầu cơ bản (Cán cân ANRPC):"
    assert weekly_ai._macro_bullets(["**1. Cung – Cầu cơ bản (Cán cân ANRPC):**", "- Đoạn mở"], title) == ["Đoạn mở"]


def test_forecast_keeps_opener_and_dash_bullets_only() -> None:
    lines = ["**Tuần 34/2026**, giá tăng…", "Sang Tuần 35–36…", "> Thị trường Tuần 37 dự kiến giằng co.",
             "- Áp lực giảm: chốt lời", "- Yếu tố hỗ trợ: El Niño", "Đoạn thừa sau cùng"]
    assert weekly_ai._finalize("forecast", lines, REP) == [
        "Thị trường Tuần 37 dự kiến giằng co.", "- Áp lực giảm: chốt lời", "- Yếu tố hỗ trợ: El Niño"]
    assert weekly_ai._finalize("forecast", ["Chỉ một đoạn.", "Đoạn hai."], REP) == ["Chỉ một đoạn."]


def test_verb_and_sign_follow_printed_one_decimal_pct() -> None:
    # % lưu 2 số lẻ nhưng in 1 số lẻ → chữ chọn theo số IN RA, không lệch "nhẹ xuống … (+0,0%)".
    assert (compose.pct(-0.04), compose.signed(-0.04), compose.vn(-0.04)) == ("0,0%", "0,0", "0,0")
    assert compose.pct(0.04) == "0,0%" and compose.pct(-0.05) == "-0,1%" and compose.pct(0.05) == "+0,1%"
    assert compose.direction(-0.04) == "đi ngang" and compose.direction(-0.05) == "giảm"

    def move(p: float) -> str:
        return compose._grade_move({"values": [2728.1, 2728.0], "changes_pct": [p]}, 0)

    assert move(-0.04) == "đi ngang ở mức **2.728,0 USD/tấn** (0,0%)"
    assert move(0.45) == "tăng lên **2.728,0 USD/tấn** (+0,5%)"            # 0,45 → 0,5: không còn "nhẹ"
    assert move(-1.96) == "điều chỉnh giảm mạnh xuống **2.728,0 USD/tấn** (-2,0%)"
    assert move(0.44) == "nhích nhẹ lên **2.728,0 USD/tấn** (+0,4%)"
