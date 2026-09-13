"""Test kiểm tra số AI viết trong Báo cáo tuần có căn cứ trong ngữ cảnh + từ ngữ tuyệt đối.

Hàm thuần — không cần DB/mạng. Ngữ cảnh dưới đây là FIXTURE mô phỏng khối số liệu (định dạng VN)
và trích đoạn tài liệu ANRPC (định dạng EN) mà weekly_ai_context dựng ra.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.weekly_number_check import (
    ABSOLUTE_WORDS,
    absolute_words,
    readings,
    unverified_numbers,
)

CTX = """
- Sàn OSE RSS3 (USD/tấn): Tuần 34 (17/8 - 21/8) 2.728,2 · Tuần 35 (24/8 - 28/8) 2.763,6 · Tuần 36 2.737,3
  T35/T34: +35,4 (+1,30%) · T36/T35: -26,3 (-0,95%)
- OSE RSS3: Cao nhất 2.784,5 USD/tấn (~448,2 JPY/kg) ngày 27/08 (Tuần 35)
- USD/JPY: TB Tuần 35 147,28 (+0,35%)
TÀI LIỆU ĐÍNH KÈM #3 — ANRPC.pdf — anrpc
ANRPC estimates that global natural rubber production will increase by around 2.1% y-o-y to
15.279 million tonnes in 2026 ... consumption 15.356 million tonnes ... deficit 77,000 tonnes.
STR20 FOB Bangkok ($/100 kg) 199.7 249.0 255.5 235.5 -7.8% 238.6 1.4%
Mủ nước nội địa: Tuần 35: 515 – 540
"""


def test_readings_vn_and_en() -> None:
    assert readings("2.763,6") == [(Decimal("2763.6"), 1)]
    assert readings("2,728.2") == [(Decimal("2728.2"), 1)]
    # Mơ hồ: '15.279' = 15279 (VN) hoặc 15,279 (EN)
    assert (Decimal("15279"), 0) in readings("15.279")
    assert (Decimal("15.279"), 3) in readings("15.279")


def test_exact_vn_numbers_are_verified() -> None:
    lines = ["*Tuần 35 vs Tuần 34:* Giá trung bình đạt **2.763,6 USD/tấn** (+35,4)"]
    assert unverified_numbers(lines, CTX) == []


def test_rounding_to_written_decimals() -> None:
    # 1,30 → '1,3%'; -0,95 → '1,0%' (làm tròn nửa lên); 147,28 → '147,3'
    lines = ["tăng 1,3%, rồi giảm 1,0%; USD/JPY quanh 147,3"]
    assert unverified_numbers(lines, CTX) == []


def test_absolute_value_matching() -> None:
    assert unverified_numbers(["Tuần 36 giảm 26,3 USD/tấn"], CTX) == []


def test_mismatch_is_reported_once() -> None:
    lines = ["Cao nhất 2.790,0 USD/tấn", "vẫn là 2.790,0 USD/tấn", "tăng 4,2%"]
    assert unverified_numbers(lines, CTX) == ["2.790,0", "4,2"]


def test_dates_weeks_years_ordinals_are_ignored() -> None:
    lines = [
        "1. Cung – Cầu cơ bản (IV.1) năm 2026",
        "> *Mức giá biến động (24/8 – 04/9):* ngày 27/08; *(Nghỉ giao dịch ngày 03–04/9)*",
        "Tuần 35 và 36 (T36/T35), tháng 7/2026, kỳ 35-36/2026, ngày 24/8/2026, tháng 9",
        "a) Năng lượng",
    ]
    assert unverified_numbers(lines, CTX) == []


def test_grade_codes_are_ignored() -> None:
    assert unverified_numbers(["SMR20, RSS3, TSR20 và SVR 3L"], CTX) == []


def test_en_numbers_from_attachment() -> None:
    lines = [
        "**Sản lượng sản xuất toàn cầu:** Dự báo đạt **15,279 triệu tấn**, tăng 2,1%",
        "Nhu cầu 15,356 triệu tấn; thâm hụt khoảng **77.000 tấn**",
        "STR20 FOB Bangkok bình quân 238,6 US cent/kg (+1,4%), tháng trước -7,8%",
    ]
    assert unverified_numbers(lines, CTX) == []


def test_en_mismatch_reported() -> None:
    assert unverified_numbers(["sản lượng 15,300 triệu tấn"], CTX) == ["15,300"]


def test_ranges_of_latex_prices() -> None:
    assert unverified_numbers(["biên độ 515 – 540 đ/độ"], CTX) == []
    assert unverified_numbers(["biên độ 500 – 540 đ/độ"], CTX) == ["500"]


def test_very_long_digit_strings_in_context_do_not_crash() -> None:
    ctx = CTX + "\nISSN 00000000000000000000000000000012345 và 1.234.567.890.123.456.789.012.345.678,5"
    assert unverified_numbers(["tăng 1,3%", "mã 99"], ctx) == ["99"]


def test_empty_inputs() -> None:
    assert unverified_numbers([], CTX) == []
    assert unverified_numbers(["tăng 5%"], "") == ["5"]


def test_absolute_words() -> None:
    lines = ["Thị trường Hoàn toàn đảo chiều", "chắc chắn tăng 100%.", "không 1100% nào"]
    assert absolute_words(lines) == ["hoàn toàn", "100%", "chắc chắn"]
    assert absolute_words(["tuyệt đối không", "ĐƯƠNG NHIÊN"]) == ["đương nhiên", "tuyệt đối"]
    assert absolute_words(["điều chỉnh giảm, xu hướng đi xuống"]) == []
    assert set(ABSOLUTE_WORDS) >= {"hoàn toàn", "100%", "đương nhiên", "chắc chắn"}


def test_absolute_words_boundary() -> None:
    # 'hoàn toànn' không phải từ tuyệt đối; '100%' dính số phía trước không tính
    assert absolute_words(["hoàn toànn", "2100%"]) == []


def test_ai_prose_reads_vietnamese_style_only() -> None:
    # Văn báo cáo (locale vi): '2,728.2' / '15.2' kiểu Anh → không đối chiếu; tóm tắt đính kèm (any) thì được.
    lines = ["giá 2,728.2 USD/tấn", "sản lượng 2.1%"]
    assert unverified_numbers(lines, CTX) == ["2,728.2", "2.1"]
    assert unverified_numbers(lines, CTX, locale="any") == []
    assert readings("2,728.2", "vi") == [] and readings("15.279", "vi") == [(Decimal("15279"), 0)]


def test_small_integers_need_exact_token() -> None:
    ctx = "tăng 4,6% · giảm 1,30% · 12 tấn · 515 – 540"
    assert unverified_numbers(["tăng 5%", "giảm 1%", "12 tấn"], ctx) == ["5", "1"]   # không khớp nhờ làm tròn
    assert unverified_numbers(["tăng 4,6%", "khoảng 540"], ctx) == []


def test_grade_code_tails_do_not_make_numbers() -> None:
    assert unverified_numbers(["SMR20 và TSR20 giữ giá, SVR 10, CSR 20, RSS 3, SVR CV 50, Latex 60%"], CTX) == []


def test_year_like_numbers_next_to_units_are_checked() -> None:
    assert unverified_numbers(["năm 2026, kỳ 2027", "giá 2030 USD/tấn", "2045 tấn", "2099%"], CTX) == [
        "2030", "2045", "2099"]
