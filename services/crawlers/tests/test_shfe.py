"""Test offline SHFE — chọn kỳ hạn MAX VOLUME → settlement (cấu trúc kx .dat)."""

from crawlers.exchanges import shfe

# Trích thật từ kx{date}.dat (o_curinstrument), thêm dòng nhiễu để khoá logic lọc.
SAMPLE = [
    {"PRODUCTID": "ru_f", "DELIVERYMONTH": "2607", "SETTLEMENTPRICE": "17715", "VOLUME": "977", "OPENINTEREST": "849"},
    {"PRODUCTID": "ru_f", "DELIVERYMONTH": "2609", "SETTLEMENTPRICE": "17760", "VOLUME": "315546", "OPENINTEREST": "163214"},
    {"PRODUCTID": "ru_f", "DELIVERYMONTH": "2701", "SETTLEMENTPRICE": "18530", "VOLUME": "31504", "OPENINTEREST": "30431"},
    {"PRODUCTID": "ru_f", "DELIVERYMONTH": "小计", "SETTLEMENTPRICE": "", "VOLUME": "352515", "OPENINTEREST": "199352"},
    {"PRODUCTID": "cu_f", "DELIVERYMONTH": "2609", "SETTLEMENTPRICE": "70000", "VOLUME": "999999", "OPENINTEREST": "1"},
]


def test_pick_ru_max_volume() -> None:
    best = shfe._pick_ru(SAMPLE)
    assert best is not None
    # 2609 thắng (volume lớn nhất); bỏ dòng 小计 (không phải số) và cu_f (đồng, không phải RU).
    assert best["month"] == "2609"
    assert best["settle"] == 17760.0
    assert best["volume"] == 315546.0


def test_pick_ru_none_when_no_rubber() -> None:
    rows = [{"PRODUCTID": "cu_f", "DELIVERYMONTH": "2609", "SETTLEMENTPRICE": "70000", "VOLUME": "1"}]
    assert shfe._pick_ru(rows) is None
