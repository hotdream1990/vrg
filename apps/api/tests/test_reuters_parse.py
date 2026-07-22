"""Test phân giải chuỗi giá physical Reuters (paste MarketScreener) → grade + USD/tấn."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.db import db_healthy
from app.schemas.price import ReutersParseResult
from app.services import reuters_physical_parse as R

_SAMPLE = """Grade: Thai RSS3 (August) - 97.39 baht/kg
Grade: Thai STR20 (August) - 78.88 baht/kg
Grade: Thai 60-percent latex (bulk/August) - 57.90 baht/kg
Grade: Malaysia SMR20 (August) - $2.21/kg
Grade: Indonesia SIR20 - NA"""

# Dạng bảng 2 cột (chủng loại / giá ngăn bằng khoảng trắng) + ghi chú sau dấu '*'
_SAMPLE_TABLE = """July 20 (Reuters) -
Grade Prices
RSS3        NA
STR20      NA
60% latex (bulk) NA
SMR20      $2.24/kg
SIR20         $2.34/kg * Prices as of July 16"""


def test_match_grade():
    assert R._match_grade("Thai RSS3 (August)") == "RSS3"
    assert R._match_grade("Thai STR20 (August)") == "STR20"
    assert R._match_grade("Thai 60-percent latex (bulk/August)") == "Thai Latex 60% (Bulk)"
    assert R._match_grade("Thai 60-percent latex (drums)") == "Thai Latex 60% (Drums)"
    assert R._match_grade("Malaysia SMR20 (August)") == "SMR20"
    assert R._match_grade("Indonesia SIR20") == "SIR20"
    assert R._match_grade("Some other index") is None


def test_is_na():
    assert R._is_na("Indonesia SIR20 - NA")
    assert R._is_na("RSS3        NA")          # dạng bảng: chỉ ngăn bằng khoảng trắng
    assert R._is_na("60% latex (bulk) NA")
    assert R._is_na("Thai RSS3 (August) - ")
    assert not R._is_na("SMR20      $2.24/kg")
    assert not R._is_na("Rubber prices in China")   # 'China' kết thúc bằng 'na' — không phải NA


def test_note_date():
    d = date(2026, 7, 20)
    assert R._note_date("Prices as of July 16", d) == date(2026, 7, 16)
    assert R._note_date("Prices as of December 30", d) == date(2025, 12, 30)  # vượt as_of → lùi 1 năm
    assert R._note_date("Prices as of Foo 16", d) is None
    assert R._note_date("Some other note", d) is None


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


def test_response_model_accepts_fractional_usd_tonne(monkeypatch):
    """Quy đổi baht/kg giữ 1 SỐ LẺ (vd 2980.9) → schema `usd_tonne` phải là float.
    Nếu để int, khi có tỷ giá USD/THB (baht/kg quy đổi ra số lẻ) `response_model` sẽ 500.
    Test cũ gọi thẳng parse() nên KHÔNG bắt được — đây là chốt chặn qua Pydantic."""
    monkeypatch.setattr(R, "_thb_at", lambda _d: 32.5)
    res = R.parse("Grade: Thai RSS3 (August) - 96.88 baht/kg\n", as_of=date(2026, 7, 20))
    rss = next(r for r in res["rows"] if r["grade"] == "RSS3")
    assert isinstance(rss["usd_tonne"], float) and rss["usd_tonne"] % 1 != 0   # có phần thập phân
    ReutersParseResult.model_validate(res)   # KHÔNG được ném ValidationError (int_from_float)


@pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
def test_parse_table_format():
    """Dạng bảng 2 cột: bỏ dòng tiêu đề, NA ngăn bằng khoảng trắng, giá vẫn đọc được khi có ghi chú '*'."""
    res = R.parse(_SAMPLE_TABLE, as_of=date(2026, 7, 20))
    by = {r["grade"]: r for r in res["rows"] if r["grade"]}
    assert set(by) == {"RSS3", "STR20", "Thai Latex 60% (Bulk)", "SMR20", "SIR20"}
    for g in ("RSS3", "STR20", "Thai Latex 60% (Bulk)"):
        assert by[g]["status"] == "na" and by[g]["usd_tonne"] is None
    assert by["SMR20"]["status"] == "ok" and by["SMR20"]["usd_tonne"] == 2240
    # ghi chú cuối dòng không được nuốt mất giá
    assert by["SIR20"]["status"] == "ok" and by["SIR20"]["usd_tonne"] == 2340
    # Bulk = NA → KHÔNG nội suy Drums
    assert "Thai Latex 60% (Drums)" not in by
    # ghi chú Reuters được nêu ra để cảnh báo lệch ngày
    assert res["note"] == "Prices as of July 16"
    assert res["note_as_of"] == date(2026, 7, 16)


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
