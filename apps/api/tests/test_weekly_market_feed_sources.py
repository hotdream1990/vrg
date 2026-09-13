"""Nguồn chỉ số Báo cáo tuần: đọc JSON CNBC · đổi mã Yahoo → CNBC · thứ tự CNBC trước, Yahoo dự phòng."""

from __future__ import annotations

from datetime import date

import pytest

from app.services import weekly_market_feed_sources as src


def test_parse_cnbc_uses_trade_date_and_skips_missing_close() -> None:
    payload = {"barData": {"priceBars": [
        {"tradeTime": "20260828000000", "close": "89.3100"},
        {"tradeTime": "20260824000000", "close": "92.1700"},
        {"tradeTime": "20260825000000", "close": None},
    ]}}
    assert src.parse_cnbc(payload) == [("2026-08-24", 92.17), ("2026-08-28", 89.31)]


def test_parse_cnbc_empty_raises() -> None:
    with pytest.raises(ValueError):
        src.parse_cnbc({"barData": {"priceBars": []}})


def test_symbol_mapping() -> None:
    assert src.cnbc_symbol("DX-Y.NYB") == ".DXY"
    assert src.cnbc_symbol("BZ=F") == "@LCO.1"
    assert src.cnbc_symbol("@CL.1") == "@CL.1"
    assert src.cnbc_symbol("JPY=X") is None


def test_fetch_any_prefers_cnbc_then_falls_back_to_yahoo(monkeypatch) -> None:
    calls: list[str] = []

    def cnbc_down(symbol, date_from, today=None):
        calls.append(f"cnbc:{symbol}")
        raise RuntimeError("429")

    def yahoo_ok(symbol, date_from, date_to):
        calls.append(f"yahoo:{symbol}")
        return [("2026-08-24", 92.17)]

    monkeypatch.setattr(src, "fetch_cnbc", cnbc_down)
    monkeypatch.setattr(src, "fetch_yahoo", yahoo_ok)
    assert src.fetch_any("BZ=F", date(2026, 8, 24), date(2026, 8, 28)) == [("2026-08-24", 92.17)]
    assert calls == ["cnbc:@LCO.1", "yahoo:BZ=F"]


def test_fetch_any_cnbc_native_symbol_has_no_yahoo_fallback(monkeypatch) -> None:
    monkeypatch.setattr(src, "fetch_cnbc", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(src, "fetch_yahoo", lambda *a, **k: pytest.fail("không được gọi Yahoo"))
    with pytest.raises(RuntimeError, match="CNBC"):
        src.fetch_any("@LCO.1", date(2026, 8, 24), date(2026, 8, 28))
