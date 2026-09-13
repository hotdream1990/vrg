"""Test Báo giá mủ thị trường (market_quote): round-trip + giá mủ tư nhân + mirror chuỗi market.

Tự bỏ qua nếu DB không sẵn sàng (CI không có DB). Dùng ngày 2099-01-01 + đơn vị test để dọn sạch.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import market_private_unit_repo, market_quote_repo, price_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

_D = "2099-01-01"
_PRIVATE = "__TEST Long Hòa, Phú Bình__"


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    with session_scope() as db:
        db.execute(text("DELETE FROM market_quote WHERE as_of >= CAST(:d AS date)"), {"d": _D})
        db.execute(text("DELETE FROM fact_price WHERE as_of = CAST(:d AS date)"), {"d": _D})
        db.execute(text("DELETE FROM market_private_unit WHERE name LIKE '__TEST%'"))


def _quote() -> dict:
    return {
        "as_of": _D,
        "fx": {"mua_tm": 26000, "mua_ck": 26010, "ban": 26400},
        "domestic_private": {"prices": {"SVR 10": 57500000},
                             "packaging": {"SVR 10": "Pallet"},
                             "shipping": {"SVR 10": "Xe khách"}, "note": "n1"},
        "export_vrg": {"prices": {"SVR 10": 2260}, "note": "n2"},
        "domestic_vrg": {"prices": {"SVR 10": 58200000},
                         "status": {"SVR 10": "Có giao dịch"}, "note": "n3"},
        "customer_proposal": {"qty": {"SVR 10": 100}, "prices": {"SVR 10": 57000000}, "note": "kh"},
        "private_prices": {_PRIVATE: {"price": 557, "price_max": None},
                           "__TEST Minh Thạnh Phát__": {"price": 560, "price_max": 563},
                           "__TEST dòng trống__": {"price": None, "price_max": None}},
        "private_processing_cost": 2100000,
        "footer": "f",
    }


def test_save_get_roundtrip_and_private_prices() -> None:
    """save → get đọc lại đúng; Mục 6 giữ một giá / khoảng giá, bỏ dòng trống."""
    saved = market_quote_repo.save_quote(_quote())
    assert saved is not None
    assert saved["fx"]["ban"] == 26400
    assert saved["domestic_vrg"]["status"]["SVR 10"] == "Có giao dịch"
    assert saved["domestic_private"]["packaging"]["SVR 10"] == "Pallet"
    assert saved["domestic_private"]["shipping"]["SVR 10"] == "Xe khách"
    assert saved["customer_proposal"]["qty"]["SVR 10"] == 100
    assert saved["private_prices"][_PRIVATE] == {"price": 557, "price_max": None}
    assert saved["private_prices"]["__TEST Minh Thạnh Phát__"] == {"price": 560, "price_max": 563}
    assert "__TEST dòng trống__" not in saved["private_prices"]
    assert saved["private_processing_cost"] == 2100000
    assert "regions" not in saved  # mục Giá mủ khu vực đã bỏ khỏi phiếu

    got = market_quote_repo.get_quote(_D)
    assert got and got["domestic_private"]["prices"]["SVR 10"] == 57500000
    assert got["customer_proposal"]["prices"]["SVR 10"] == 57000000


def test_private_price_normalised_and_range_check() -> None:
    """Chỉ nhập Giá max → coi là một giá; Giá max = Giá → một giá; Giá max < Giá → báo sai."""
    rows = {"a": {"price": None, "price_max": 560}, "b": {"price": 560, "price_max": 560},
            "c": {"price": 563, "price_max": 560}}
    assert market_quote_repo.invalid_private_rows(rows) == ["c"]
    saved = market_quote_repo.save_quote({"as_of": _D, "private_prices": {k: rows[k] for k in ("a", "b")}})
    assert saved["private_prices"] == {"a": {"price": 560, "price_max": None},
                                       "b": {"price": 560, "price_max": None}}


def test_private_prices_latest_per_unit_with_own_date() -> None:
    """Mỗi đơn vị lấy giá MỚI NHẤT của chính nó (ngày giá riêng) + lần báo liền trước; quá cửa sổ thì bỏ."""
    market_quote_repo.save_quote(_quote())                                   # 01/01: 2 đơn vị
    market_quote_repo.save_quote({"as_of": "2099-01-03",
                                  "private_prices": {_PRIVATE: {"price": 558, "price_max": None}}})
    rows = {r["name"]: r for r in market_quote_repo.private_prices_by_unit("2099-01-05")}
    assert rows[_PRIVATE]["price"] == 558 and rows[_PRIVATE]["as_of"] == "2099-01-03"
    assert rows[_PRIVATE]["prev"] == {"price": 557, "price_max": None, "as_of": _D}
    mtp = rows["__TEST Minh Thạnh Phát__"]
    assert (mtp["price"], mtp["price_max"], mtp["as_of"], mtp["prev"]) == (560, 563, _D, None)
    assert mtp["processing_cost"] == 2100000
    assert market_quote_repo.private_prices_by_unit("2099-02-01") == []      # quá 14 ngày


def test_private_unit_catalog_dedupes_names() -> None:
    """Danh mục đơn vị tư nhân: gộp khoảng trắng thừa, trùng tên (không phân biệt hoa/thường) → báo lỗi."""
    unit = market_private_unit_repo.add_unit("  __TEST  Bến   Súc ", "tester")
    assert unit["name"] == "__TEST Bến Súc"
    with pytest.raises(ValueError):
        market_private_unit_repo.add_unit("__test bến súc", "tester")
    assert market_private_unit_repo.delete_unit(unit["id"]) is True
    assert all(u["id"] != unit["id"] for u in market_private_unit_repo.list_units())


def test_market_series_mirrored_then_delete() -> None:
    """Mục 1-4 mirror sang source=market; xoá phiếu → chuỗi market mất theo."""
    market_quote_repo.save_quote(_quote())
    rows = price_repo.list_records(source="market", date_from=_D, date_to=_D, limit=50)
    ptypes = {r["price_type"] for r in rows["records"]}
    assert {"market_domestic_private", "market_export_vrg", "market_domestic_vrg"} <= ptypes

    assert market_quote_repo.delete_quote(_D) is True
    assert price_repo.list_records(source="market", date_from=_D, date_to=_D, limit=50)["total"] == 0
    assert market_quote_repo.get_quote(_D) is None
