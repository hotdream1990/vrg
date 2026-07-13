"""Test phân giải chuỗi giá physical Reuters (paste MarketScreener) → grade + USD/tấn."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.db import db_healthy
from app.services import reuters_physical_parse as R

_SAMPLE = """Grade: Thai RSS3 (August) - 97.39 baht/kg
Grade: Thai STR20 (August) - 78.88 baht/kg
Grade: Thai 60-percent latex (bulk/August) - 57.90 baht/kg
Grade: Malaysia SMR20 (August) - $2.21/kg
Grade: Indonesia SIR20 - NA"""


def test_match_grade():
    assert R._match_grade("Thai RSS3 (August)") == "RSS3"
    assert R._match_grade("Thai STR20 (August)") == "STR20"
    assert R._match_grade("Thai 60-percent latex (bulk/August)") == "Thai Latex 60% (Bulk)"
    assert R._match_grade("Thai 60-percent latex (drums)") == "Thai Latex 60% (Drums)"
    assert R._match_grade("Malaysia SMR20 (August)") == "SMR20"
    assert R._match_grade("Indonesia SIR20") == "SIR20"
    assert R._match_grade("Some other index") is None


def test_native():
    assert R._native("100.83 baht/kg") == (100.83, "baht/kg")
    assert R._native("$2.21/kg") == (2.21, "US$/kg")
    assert R._native("US$2.21/kg") == (2.21, "US$/kg")
    assert R._native("NA") == (None, None)
    assert R._native(" - ") == (None, None)


def test_contract():
    assert R._contract("Thai RSS3 (August)") == "August"
    assert R._contract("Thai 60-percent latex (bulk/August)") == "August"
    assert R._contract("Indonesia SIR20") == ""


def test_add_drums():
    # Reuters chỉ có Bulk → nội suy Drums = Bulk + 100
    rows = [{"grade": "Thai Latex 60% (Bulk)", "status": "ok", "usd_tonne": 1737, "contract": "August"}]
    R._add_drums(rows)
    assert len(rows) == 2
    d = rows[1]
    assert d["grade"] == "Thai Latex 60% (Drums)" and d["status"] == "derived" and d["usd_tonne"] == 1837
    # Không nội suy nếu Bulk chưa quy đổi được (no_fx) hoặc đã có sẵn Drums
    rows_nofx = [{"grade": "Thai Latex 60% (Bulk)", "status": "no_fx", "usd_tonne": None, "contract": ""}]
    R._add_drums(rows_nofx)
    assert len(rows_nofx) == 1


@pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
def test_parse_full_conversion():
    res = R.parse(_SAMPLE, as_of=date(2026, 7, 7))
    assert res["as_of"] == date(2026, 7, 7)
    by = {r["grade"]: r for r in res["rows"] if r["grade"]}
    # SMR20 $/kg ×1000 = 2210 (không phụ thuộc tỷ giá)
    assert by["SMR20"]["usd_tonne"] == 2210
    assert by["SMR20"]["status"] == "ok"
    # SIR20 = NA → bỏ
    assert by["SIR20"]["status"] == "na" and by["SIR20"]["usd_tonne"] is None
    # Latex Drums nội suy = Bulk + 100 (Reuters chỉ báo Bulk)
    bulk = by["Thai Latex 60% (Bulk)"]
    if bulk["status"] == "ok":
        drums = by.get("Thai Latex 60% (Drums)")
        assert drums and drums["status"] == "derived"
        assert drums["usd_tonne"] == bulk["usd_tonne"] + 100
    # baht/kg quy đổi ra khoảng hợp lý (>1000) nếu có USD/THB
    rss = by["RSS3"]
    if rss["status"] == "ok":
        assert rss["usd_tonne"] > 1000
