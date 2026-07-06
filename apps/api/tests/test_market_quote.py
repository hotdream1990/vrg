"""Test Báo giá mủ thị trường (market_quote): round-trip + đồng bộ Mục 4 + mirror chuỗi market.

Tự bỏ qua nếu DB không sẵn sàng (CI không có DB). Dùng ngày 2099-01-01 + đơn vị test để dọn sạch.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import market_quote_repo, price_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

_D = "2099-01-01"
_REGION = "__TESTREG__"


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    with session_scope() as db:
        db.execute(text("DELETE FROM market_quote WHERE as_of = CAST(:d AS date)"), {"d": _D})
        db.execute(text("DELETE FROM fact_price WHERE as_of = CAST(:d AS date)"), {"d": _D})
        db.execute(text("DELETE FROM member_unit WHERE name = :n"), {"n": _REGION})


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
        "regions": {_REGION: 549},
        "regions_cup": {_REGION: 21000},
        "footer": "f",
    }


def test_save_get_roundtrip_and_region_sync() -> None:
    """save → get đọc lại đúng; Mục 5 đồng bộ sang kho Giá mủ nguyên liệu (purchase + purchase_cup)."""
    saved = market_quote_repo.save_quote(_quote())
    assert saved is not None
    assert saved["fx"]["ban"] == 26400
    assert saved["domestic_vrg"]["status"]["SVR 10"] == "Có giao dịch"
    assert saved["domestic_private"]["packaging"]["SVR 10"] == "Pallet"
    assert saved["domestic_private"]["shipping"]["SVR 10"] == "Xe khách"
    assert saved["customer_proposal"]["qty"]["SVR 10"] == 100
    assert saved["regions"].get(_REGION) == 549
    assert saved["regions_cup"].get(_REGION) == 21000

    # Mục 5 (mủ nước + mủ chén) phải xuất hiện trong kho Giá mủ nguyên liệu đúng ngày.
    assert abs(price_repo.purchase_by_company_on_date(_D).get(_REGION, 0) - 549) < 1e-6
    assert abs(price_repo.purchase_by_company_on_date(_D, "purchase_cup").get(_REGION, 0) - 21000) < 1e-6

    got = market_quote_repo.get_quote(_D)
    assert got and got["domestic_private"]["prices"]["SVR 10"] == 57500000
    assert got["customer_proposal"]["prices"]["SVR 10"] == 57000000


def test_market_series_mirrored_then_delete_keeps_purchase() -> None:
    """Mục 1-3 mirror sang source=market; xoá phiếu → chuỗi market mất, giá mủ nước giữ nguyên."""
    market_quote_repo.save_quote(_quote())
    rows = price_repo.list_records(source="market", date_from=_D, date_to=_D, limit=50)
    ptypes = {r["price_type"] for r in rows["records"]}
    assert {"market_domestic_private", "market_export_vrg", "market_domestic_vrg"} <= ptypes

    assert market_quote_repo.delete_quote(_D) is True
    assert price_repo.list_records(source="market", date_from=_D, date_to=_D, limit=50)["total"] == 0
    # Giá mủ nước (đồng bộ sang kho chung) KHÔNG bị xoá theo phiếu.
    assert price_repo.purchase_by_company_on_date(_D).get(_REGION) == 549
