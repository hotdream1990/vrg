"""Test Mục IV (Section IV) của bản tin — tiêu đề Giá Physical không báo 'không có'
khi CÓ giá, và báo 'không có giá giao dịch' khi thiếu."""

from __future__ import annotations


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
