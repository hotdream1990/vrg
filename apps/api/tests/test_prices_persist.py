"""Test ghi/đọc giá vào DB (TimescaleDB). Tự bỏ qua nếu DB không sẵn sàng (CI không có DB)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import price_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")


@pytest.fixture(autouse=True)
def _cleanup_test_rows():
    """Dọn dữ liệu test sau mỗi test — KHÔNG để rác lọt vào DB dev (grade `__…__`)."""
    yield
    with session_scope() as db:
        db.execute(text(r"DELETE FROM fact_price WHERE grade LIKE '\_\_%' ESCAPE '\'"))
        db.execute(text("DELETE FROM meta_crawl_run WHERE sources = 'test'"))


def test_upsert_and_latest_roundtrip() -> None:
    """create_run → upsert → latest đọc lại đúng giá; upsert lần 2 cập nhật (không trùng)."""
    run_id = price_repo.create_run("test")
    assert run_id > 0

    rec = {
        "as_of": "2026-06-16",
        "source": "anrpc",
        "grade": "__TEST__",
        "contract": None,
        "price_type": "physical",
        "price": 1.2345,
        "currency": "USD",
        "unit": "US$/kg",
        "source_ts": None,
    }
    assert price_repo.upsert_prices([rec], run_id) == 1

    rows = price_repo.latest()
    mine = [r for r in rows if r["grade"] == "__TEST__"]
    assert mine and abs(mine[0]["price"] - 1.2345) < 1e-6

    # Upsert cùng khóa, giá mới → cập nhật, không tạo bản ghi mới.
    rec["price"] = 9.9
    price_repo.upsert_prices([rec], run_id)
    rows2 = [r for r in price_repo.latest() if r["grade"] == "__TEST__"]
    assert len(rows2) == 1 and abs(rows2[0]["price"] - 9.9) < 1e-6

    price_repo.finish_run(run_id, "ok", 1)


def test_history_returns_points() -> None:
    run_id = price_repo.create_run("test")
    price_repo.upsert_prices(
        [{
            "as_of": "2026-06-16", "source": "anrpc", "grade": "__TESTH__",
            "contract": None, "price_type": "physical", "price": 2.0,
            "currency": "USD", "unit": "US$/kg", "source_ts": None,
        }],
        run_id,
    )
    series = price_repo.history("anrpc", "__TESTH__", days=30)
    assert any(abs(p["price"] - 2.0) < 1e-6 for p in series)
