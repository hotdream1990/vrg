"""Test bộ soát "chữ nhận định lệch dữ liệu hiện tại" của Báo cáo tuần — hàm thuần, không DB/mạng.

Mọi `rep` dưới đây là FIXTURE mô phỏng kết quả `weekly_report_service.build_report` (chỉ các field bộ
soát đọc). Số lấy theo ca thật tuần 37/2026 trên bản sao prod: AI viết giữa tuần khi mới có ngày 7/9.
"""

from __future__ import annotations

import copy

from app.services.weekly_ai_compose import exchange_notes as compose_v2
from app.services.weekly_consistency_check import check_latex, check_report

W35 = {"week_no": 35, "year": 2026, "mon": "2026-08-24", "fri": "2026-08-28"}
W36 = {"week_no": 36, "year": 2026, "mon": "2026-08-31", "fri": "2026-09-04"}
W37 = {"week_no": 37, "year": 2026, "mon": "2026-09-07", "fri": "2026-09-11"}


def _row(exc, grade, values, pcts):
    return {"exchange": exc, "grade": grade, "values": values, "changes_pct": pcts}


def _stat(exc, grade, high, hd, low, ld):
    return {"exchange": exc, "grade": grade, "high": high, "high_date": hd, "high_week_no": 37,
            "low": low, "low_date": ld, "low_week_no": 37, "native_unit": None}


def _rep(**narrative) -> dict:
    """Fixture 1 tuần (T37 so T36): OSE/SHANGHAI N/A tuần 37 (thiếu tỷ giá), SGX + MRE có giá."""
    nar = {"exchange_notes": [], "movement": [], "summary_prev": [], "macro": []}
    nar.update(narrative)
    return {
        "weeks": [W36, W37],
        "exchange_rows": [
            _row("OSE", "RSS3", [2737.3, None], [None]),
            _row("SHANGHAI", "RSS3", [2801.4, None], [None]),
            _row("SGX", "RSS3", [2732.0, 2767.6], [1.3]),
            _row("SGX", "TSR20", [2356.0, 2460.0], [4.41]),
            _row("MRE", "SMR CV", [2948.4, 3013.6], [2.21]),
            _row("MRE", "SMR20", [2417.6, 2523.8], [4.39]),
            _row("MRE", "LATEX", [1705.3, 1743.8], [2.26]),
        ],
        "range_stats": [
            _stat("SGX", "RSS3", 2788.0, "10/09", 2707.0, "07/09"),
            _stat("SGX", "TSR20", 2499.0, "09/09", 2419.0, "07/09"),
            _stat("MRE", "SMR CV", 3023.0, "11/09", 2995.0, "07/09"),
            _stat("MRE", "SMR20", 2562.0, "09/09", 2485.5, "07/09"),
            _stat("MRE", "LATEX", 1750.9, "10/09", 1730.9, "07/09"),
        ],
        "latex_bands": ["495 – 559", "495 - 564"], "latex_auto_bands": ["495 - 559", "495 - 564"],
        "latex_changes": ["0 /+5"], "latex_auto_changes": ["0 /+5"],
        "narrative": nar,
    }


def _all_mentioned(*lines: str) -> list[str]:
    """Nhắc đủ SGX + MRE để khỏi dính cảnh báo "chưa nhắc tới sàn" khi test ca khác."""
    return [*lines, "Sàn MRE SMR CV (+2,21%): ổn định."]


def _warn(rep, key="exchange_notes", prev=None):
    return check_report(rep, prev)["warnings"].get(key, [])


# ── a. % trong nhận định III.1 ──
def test_v1_pct_written_midweek_is_reported():
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX RSS3 (-0,92%): Giá suy yếu nhẹ."))
    assert "Nhận định ghi SGX RSS3 -0,92% nhưng bảng hiện +1,30% (Tuần 37 so Tuần 36)." in _warn(rep)


def test_v1_pct_rounded_to_written_decimals_is_not_reported():
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX TSR20 (+4,4%): tăng.", "Sàn SGX RSS3 (+1,30%): tăng.",
                                             "Sàn MRE SMR20 ( +4,39%): tăng.", "Sàn MRE LATEX (+2,3%): tăng."))
    assert _warn(rep) == []


def test_v1_na_pct_vs_table_value_and_table_na():
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX RSS3 (N/A%): …", "Sàn OSE (N/A%): …", "Sàn SGX TSR20 (+4,41%)"))
    w = _warn(rep)
    assert "Nhận định ghi SGX RSS3 N/A nhưng bảng hiện +1,30% (Tuần 37 so Tuần 36)." in w
    assert not any("OSE RSS3 N/A" in s for s in w)          # bảng cũng N/A → khớp


def test_word_import_free_form_pct():
    rep = _rep(exchange_notes=_all_mentioned(
        "Sàn SGX: Duy trì xu hướng điều chỉnh giảm nhẹ với RSS3 giảm 1,24% và TSR20 tăng 4,41%."))
    assert _warn(rep) == ["Nhận định ghi SGX RSS3 -1,24% nhưng bảng hiện +1,30% (Tuần 37 so Tuần 36)."]


def test_v1_style_is_skipped_for_multi_week_period():
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX RSS3 (-0,92%): …"))
    rep["weeks"] = [W35, W36, W37]
    assert not any("-0,92%" in s for s in _warn(rep))


# ── b. Cao/thấp ──
def test_v1_high_low_lines_use_header_grade():
    rep = _rep(exchange_notes=_all_mentioned(
        "Sàn SGX RSS3 (+1,30%): tăng.",
        "> Cao nhất tuần: Đạt 2.707,0 USD/tấn (ngày 7/9)",
        "> Thấp nhất tuần: 2.707,0 USD/tấn (ngày 7/9)"))
    assert _warn(rep) == [
        "Nhận định ghi SGX RSS3 cao nhất 2.707,0 USD/tấn (7/9) nhưng bảng hiện 2.788,0 USD/tấn (10/9)."]


def test_same_price_tie_date_later_is_not_reported_but_earlier_is():
    later = _rep(exchange_notes=_all_mentioned("Sàn SGX TSR20 (+4,41%): …", "> Thấp nhất tuần: 2.419,0 USD/tấn (8/9)"))
    assert _warn(later) == []   # 2 ngày bằng giá → bảng lấy ngày sớm hơn (7/9)
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX TSR20 (+4,41%): …", "> Cao nhất tuần: 2.499 USD/tấn (8/9)"))
    assert len(_warn(rep)) == 1


def test_approximate_or_native_prices_are_ignored():
    rep = _rep(exchange_notes=_all_mentioned(
        "Sàn SGX: o RSS3 (+1,30%): Đạt cao nhất tuần ở mức 232,4 US cent/kg (16/6); "
        "Mức thấp nhất tuần vào ngày 7/9 tại 270,7 US cent/kg (~2.100 USD/tấn)."))
    assert _warn(rep) == []


# ── v2: phần số do code dựng → không bao giờ lệch; đổi dữ liệu → bắt đúng ô ──
def _rep_v2() -> dict:
    rep = _rep()
    rep["weeks"] = [W35, W36, W37]
    for r in rep["exchange_rows"]:
        r["values"] = [r["values"][0] - 20, *r["values"]]
        r["changes_pct"] = [None if r["values"][1] is None else 0.73, *r["changes_pct"]]
    rep["narrative"]["exchange_notes"] = compose_v2(rep, {("SGX", 37, 36): "do Baht mạnh lên"})
    return rep


def test_v2_composed_notes_have_no_warning():
    assert _warn(_rep_v2()) == []


def test_v2_multi_grade_segment_attributes_the_right_grade():
    rep = _rep_v2()
    changed = copy.deepcopy(rep)
    sgx_rss3 = changed["exchange_rows"][2]
    sgx_rss3["values"][2], sgx_rss3["changes_pct"][1] = 2787.6, 2.03
    changed["range_stats"][1]["low"] = 2400.0
    w = _warn(changed)
    assert w == [
        "Nhận định ghi giá TB SGX RSS3 Tuần 37 2.767,6 USD/tấn nhưng bảng hiện 2.787,6 USD/tấn.",
        "Nhận định ghi SGX RSS3 +1,3% nhưng bảng hiện +2,03% (Tuần 37 so Tuần 36).",
        "Nhận định ghi SGX TSR20 thấp nhất 2.419,0 USD/tấn (7/9) nhưng bảng hiện 2.400,0 USD/tấn (7/9).",
    ]


# ── e. Sàn thiếu / thừa ──
def test_exchange_in_table_but_not_mentioned():
    rep = _rep(exchange_notes=["Sàn SGX RSS3 (+1,30%): tăng."])
    assert _warn(rep) == ["Nhận định III.1 chưa nhắc tới sàn MRE (bảng có giá trong kỳ)."]


def test_exchange_mentioned_but_table_na_unless_explained():
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX RSS3 (+1,30%): tăng.", "Sàn OSE: giá neo cao."))
    assert "Nhận định III.1 nhắc tới sàn OSE nhưng bảng không có giá cả kỳ." in _warn(rep)
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX RSS3 (+1,30%): tăng.", "**Sàn OSE (Nhật Bản):**",
                                             "> *Chưa quy đổi được USD trong kỳ do thiếu tỷ giá USD/JPY*"))
    assert _warn(rep) == []


# ── c. Chiều tăng/giảm ở I, II, IV ──
MOVEMENT_T37 = ("Sang tuần báo cáo, diễn biến giá phân hóa: SGX RSS3 hạ nhiệt nhẹ, trong khi SGX TSR20, "
                "MRE SMR CV, MRE SMR20 và MRE LATEX đều giữ vững sắc xanh.")


def test_movement_direction_conflict_and_subject_list():
    w = _warn(_rep(movement=[MOVEMENT_T37]), "movement")
    assert w == ["Có thể lệch chiều: “SGX RSS3 hạ nhiệt” nhưng bảng SGX RSS3 +1,30% (Tuần 37 so Tuần 36)."]


def test_direction_no_false_alarm_cases():
    lines = [
        "Trên sàn Osaka (SGX), đồng Yên tiếp tục suy yếu so với USD.",      # chủ ngữ thật là đồng Yên
        "Sàn SGX chịu sức ép giảm từ tồn kho.",                               # sức ép, không phải giá
        "Tồn kho giám sát tại SGX tăng 1%.",                                  # tồn kho
        "SGX RSS3 giảm mạnh trong phiên 8/9.",                                # nói về 1 phiên
        "SGX RSS3 chưa giảm.",                                                # phủ định
        "SGX TSR20 tăng 0,5 USD.",                                            # cùng chiều
        "OSE giảm.",                                                          # bảng N/A
    ]
    rep = _rep(movement=lines, macro=[{"title": "4.", "bullets": ["SGX RSS3 giảm do dầu."]}])
    res = check_report(rep)
    assert res["warnings"].get("movement") is None
    assert res["warnings"]["macro:0"][0].startswith("Có thể lệch chiều: “SGX RSS3 giảm”")


def test_exchange_without_grade_needs_all_grades_same_sign():
    rep = _rep(movement=["MRE giảm.", "SGX giảm."])
    rep["exchange_rows"][3]["changes_pct"] = [-0.5]     # SGX: RSS3 +1,3 / TSR20 -0,5 → trái chiều, bỏ
    w = _warn(rep, "movement")
    assert len(w) == 1 and "MRE" in w[0]


def test_summary_prev_uses_benchmark_week_pair():
    prev = {"weeks": [W35, W36], "exchange_rows": [_row("SGX", "RSS3", [2754.8, 2732.0], [-0.83])]}
    rep = _rep(summary_prev=["Tuần trước SGX RSS3 đi lên."])
    assert _warn(rep, "summary_prev", prev) == [
        "Có thể lệch chiều: “SGX RSS3 đi lên” nhưng bảng SGX RSS3 -0,83% (Tuần 36 so Tuần 35)."]
    assert _warn(rep, "summary_prev") == []      # không có bảng tuần mốc → không soát


# ── d. III.3 mủ nước ──
def test_latex_saved_band_differs_from_auto():
    rep = _rep()
    rep["latex_bands"], rep["latex_changes"] = ["495 – 559", "495 - 557"], ["0 /-2"]
    assert check_latex(rep) == [
        "Biên độ mủ nước Tuần 37 đang dùng số đã lưu 495 - 557; số tự tính theo dữ liệu hiện tại 495 - 564."]


def test_latex_equal_dash_styles_missing_auto_and_change_override():
    rep = _rep()
    assert check_latex(rep) == []                          # '495 – 559' = '495 - 559'
    rep["latex_auto_bands"], rep["latex_bands"] = ["495 - 559", None], ["495 - 559", "500 - 560"]
    assert check_latex(rep) == []                          # chưa có số tự tính → ô ghi đè lấp chỗ trống
    rep = _rep()
    rep["latex_changes"] = ["0 /+9"]
    assert check_latex(rep) == [
        "Biến động mủ nước Tuần 37 đang dùng số đã lưu 0 /+9; số tự tính theo dữ liệu hiện tại 0 /+5."]


def test_summary_and_count():
    res = check_report(_rep())
    assert res == {"warnings": {}, "count": 0,
                   "summary": "Không thấy chỗ lệch giữa nhận định và dữ liệu hiện tại."}
    rep = _rep(exchange_notes=_all_mentioned("Sàn SGX RSS3 (-0,92%): …"), movement=[MOVEMENT_T37])
    rep["latex_bands"] = ["495 - 559", "495 - 557"]
    res = check_report(rep)
    assert res["count"] == 3
    assert res["summary"] == "Có 3 chỗ cần soát (III.1: 1, II: 1, III.3: 1)."
