"""Test offline cho parser FX (exchangerates.org.uk) — không cần trình duyệt/mạng.

Test trực tiếp _parse_latest (trích dòng Close mới nhất từ text bảng lịch sử) + _rec.
"""

from datetime import date

from crawlers.base.models import Source
from crawlers.macro import fx

# Mẫu text như inner_text trang conversion (newest-first), kèm dòng spot KHÔNG có ngày.
SAMPLE_CNY = (
    "Today's Live US Dollar to Chinese Yuan Spot Rate:\n"
    "1 USD = 6.801 CNY\n"
    "US Dollar to Chinese Yuan Exchange Rate History\n"
    "Tuesday 23 June 2026\t1 USD = 6.7908 CNY\n"
    "Monday 22 June 2026\t1 USD = 6.7746 CNY\n"
    "Sunday 21 June 2026\t1 USD = 6.7693 CNY\n"
)


def test_parse_latest_picks_newest_dated_close() -> None:
    # Lấy dòng CÓ NGÀY mới nhất (23/06), KHÔNG lấy dòng spot 6.801 (không có ngày).
    assert fx._parse_latest(SAMPLE_CNY, "CNY") == (date(2026, 6, 23), 6.7908)


def test_parse_latest_currency_filter() -> None:
    # Sai mã tiền → không khớp.
    assert fx._parse_latest(SAMPLE_CNY, "JPY") is None


def test_parse_latest_jpy_format() -> None:
    text = "Friday 20 June 2026\t1 USD = 161.5621 JPY\n"
    assert fx._parse_latest(text, "JPY") == (date(2026, 6, 20), 161.5621)


def test_parse_latest_empty_or_blocked() -> None:
    # Trang bị Cloudflare chặn (không có bảng) → None.
    assert fx._parse_latest("Attention Required! Cloudflare", "THB") is None


def test_rec_shape() -> None:
    r = fx._rec("MYR", date(2026, 6, 23), 4.1402)
    assert r.source is Source.FX
    assert r.grade == "USD/MYR"
    assert r.price == 4.1402
    assert r.price_type == "fx"
    assert r.as_of == date(2026, 6, 23)
