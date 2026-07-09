"""Test khối 'Giá vật chất' của bản tin: dùng đúng 2 phiên vật chất THẬT gần nhất,
không đắp giá cũ vào ngày báo cáo (nguồn physical giao dịch không hằng ngày)."""

from __future__ import annotations

from app.services import bulletin_service as bs


def _pm() -> dict:
    """price_map mẫu: reuters (RSS3 mới, SIR20 cũ hơn) + 1 sàn khác (bỏ qua)."""
    return {
        ("reuters", "RSS3"): {"2026-07-06": (2894, "USD/tonne"), "2026-07-07": (2922, "USD/tonne")},
        ("reuters", "SIR20"): {"2026-06-29": (2410, "USD/tonne"), "2026-07-02": (2260, "USD/tonne")},
        ("shfe", "RU"): {"2026-07-08": (13000, "CNY/tonne")},  # không phải physical → bỏ qua
    }


def test_physical_sessions_picks_two_latest_real_dates() -> None:
    # 08/07 không có phiên vật chất → lấy 2 phiên THẬT gần nhất = 06/07 & 07/07 (bỏ qua sàn SHFE).
    prev, curr = bs._physical_sessions(_pm(), "2026-07-08")
    assert (prev, curr) == ("2026-07-06", "2026-07-07")


def test_physical_sessions_ignores_dates_after_report() -> None:
    # Chốt tại 01/07: chỉ tính phiên <= ngày báo cáo → 29/06 & (không có ngày thứ 2 hợp lệ? có: chỉ 29/06).
    prev, curr = bs._physical_sessions(_pm(), "2026-07-01")
    assert curr == "2026-06-29" and prev is None  # trước 01/07 chỉ còn 29/06 của SIR20


def test_physical_sessions_empty_when_no_reuters() -> None:
    assert bs._physical_sessions({("shfe", "RU"): {"2026-07-08": (1, "CNY/tonne")}}, "2026-07-08") == (None, None)


# --- Section IV text (PDF): tiêu đề Giá Physical không được báo "không có" khi CÓ giá ---


def _bd(summary):
    from datetime import date

    from bulletin.models import BulletinData
    return BulletinData(report_date=date(2026, 7, 8), prev_date=date(2026, 7, 7),
                        physical_curr_date=date(2026, 7, 8), physical_prev_date=date(2026, 7, 7),
                        market_physical_summary=summary)


def _iv_html(summary) -> str:
    """HTML của nhóm Section IV (khối cuối trong content_groups)."""
    from bulletin.html_template import content_groups
    return "".join(content_groups(_bd(summary))[2])


def test_news_physical_header_shows_prices_when_present() -> None:
    html = _iv_html("RSS3 giao dịch ở mức 2.952 usd/tấn;")
    assert "không có giá giao dịch" not in html          # có giá → KHÔNG báo "không có"
    assert "2. Giá Physical 08/07:" in html and "RSS3 giao dịch" in html


def test_news_physical_header_empty_when_no_prices() -> None:
    assert "2. Giá Physical 08/07: không có giá giao dịch." in _iv_html(None)
