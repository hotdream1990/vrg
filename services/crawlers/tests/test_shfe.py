"""Test offline parser SHFE/Sina — khoá vị trí cột để không sai khi refactor."""

from datetime import date

from crawlers.exchanges import shfe

# Chuỗi thật từ hq.sinajs.cn/list=nf_RU0 (rút gọn đuôi)
SAMPLE = (
    'var hq_str_nf_RU0="天然橡胶连续,150000,17615.000,17865.000,17585.000,'
    "17760.000,17750.000,17760.000,17760.000,17760.000,17565.000,71,92,"
    '163214.000,315546,沪,天然橡胶,2026-06-15,1,";'
)


def test_parse_maps_fields_correctly() -> None:
    rec = shfe._parse(SAMPLE)
    assert rec is not None
    assert rec.grade == "RU"
    assert rec.price == 17760.0          # last (cột 7)
    assert rec.currency == "CNY"
    assert rec.as_of == date(2026, 6, 15)
    assert rec.extra["open"] == 17615.0
    assert rec.extra["high"] == 17865.0
    assert rec.extra["low"] == 17585.0
    assert rec.extra["volume"] == 163214.0
    assert rec.extra["open_interest"] == 315546.0


def test_parse_empty_returns_none() -> None:
    assert shfe._parse('var hq_str_nf_RU0="";') is None
