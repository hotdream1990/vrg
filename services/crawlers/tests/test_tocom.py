"""Test offline cho parser TOCOM/OSE (cdf_dyr PDF) — dòng dữ liệu + chọn kỳ hạn.

Không cần PDF thật: test trực tiếp _parse_row (1 dòng văn bản) và _pick (chọn max Trading Value).
"""

from crawlers.exchanges import tocom

# Dòng thật từ cdf_dyr trang RSS3 (OSE)
RSS3_TRADED = (
    "202611 11.24 1611100AK 431.1 431.4 425.0 426.9 427.0 428.4 424.8 426.1 "
    "- 2.8 244 66 521,536,500 141,527,500 426.1 2,744 …"
)
RSS3_UNTRADED = "202612 12.22 1611200AK … … … … … … … … … … … … … 428.0 10 …"


def test_parse_row_traded() -> None:
    r = tocom._parse_row(RSS3_TRADED)
    assert r is not None
    assert r["contract"] == "202611"
    assert r["settle"] == 426.1                 # số thập phân cuối dòng = settlement
    assert r["trading_value"] == 521_536_500     # comma-number lớn nhất


def test_parse_row_untraded() -> None:
    r = tocom._parse_row(RSS3_UNTRADED)
    assert r is not None
    assert r["settle"] == 428.0
    assert r["trading_value"] == 0


def test_pick_max_trading_value() -> None:
    rows = [
        {"contract": "202606", "settle": 418.9, "trading_value": 135_099_000},
        {"contract": "202611", "settle": 426.1, "trading_value": 521_536_500},
        {"contract": "202612", "settle": 428.0, "trading_value": 0},
    ]
    assert tocom._pick(rows)["contract"] == "202611"


def test_pick_fallback_front_when_untraded() -> None:
    rows = [{"contract": "202607", "settle": 360.0, "trading_value": 0}]
    assert tocom._pick(rows)["contract"] == "202607"
