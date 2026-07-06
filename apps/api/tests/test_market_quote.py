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
        "domestic_private": {"prices": {"SVR 10": 57500000}, "note": "n1"},
        "export_vrg": {"prices": {"SVR 10": 2260}, "note": "n2"},
        "domestic_vrg": {"prices": {"SVR 10": 58200000},
                         "status": {"SVR 10": "Có giao dịch"}, "note": "n3"},
        "regions": {_REGION: 549},
        "footer": "f",
    }


def test_save_get_roundtrip_and_region_sync() -> None:
    """save → get đọc lại đúng; Mục 4 đồng bộ sang kho Giá mủ nguyên liệu (source=vrg purchase)."""
    saved = market_quote_repo.save_quote(_quote())
    assert saved is not None
    assert saved["fx"]["ban"] == 26400
    assert saved["domestic_vrg"]["status"]["SVR 10"] == "Có giao dịch"
    assert saved["regions"].get(_REGION) == 549

    # Mục 4 phải xuất hiện trong kho Giá mủ nguyên liệu đúng ngày.
    purchase = price_repo.purchase_by_company_on_date(_D)
    assert abs(purchase.get(_REGION, 0) - 549) < 1e-6

    got = market_quote_repo.get_quote(_D)
    assert got and got["domestic_private"]["prices"]["SVR 10"] == 57500000


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
