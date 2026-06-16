"""Test offline parser LGM (currentprice API) — đơn vị theo grade."""

from datetime import date

from crawlers.exchanges import lgm

SAMPLE = [
    {"grade": "SMR CV", "tarikh": "2026-06-15T00:00:00", "sellers": 1330, "sellersUs": 335.1, "tone": "Very Firm"},
    {"grade": "SMR 20", "tarikh": "2026-06-15T00:00:00", "sellers": 936.5, "sellersUs": 235.95},
    {"grade": "Latex in Bulk", "tarikh": "2026-06-15T00:00:00", "sellers": 786, "sellersUs": 786},
]


def test_parse_units_per_grade() -> None:
    recs = {r.grade: r for r in lgm._parse(SAMPLE)}
    # SMR yết US cents/kg (field sellersUs)
    assert recs["SMRCV"].price == 335.1 and recs["SMRCV"].unit == "US cents/kg"
    assert recs["SMR20"].price == 235.95
    # Latex: API trả sellersUs CHƯA quy đổi (=sellers) → tự quy đổi sang US cents/kg
    # bằng tỷ giá MYR/USD nội tại suy từ SMR (1330/335.1). Giữ Sen/kg gốc ở extra.
    rate = 1330 / 335.1
    assert recs["LATEX"].unit == "US cents/kg"
    assert recs["LATEX"].price == round(786 / rate, 2)
    assert recs["LATEX"].extra["local_sen_kg"] == 786
    assert recs["SMRCV"].as_of == date(2026, 6, 15)
    assert recs["SMRCV"].source.value == "lgm"
