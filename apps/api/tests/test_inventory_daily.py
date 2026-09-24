"""Test tồn kho Tập đoàn THEO NGÀY cho Gợi ý giá sàn + Trợ lý AI (thay chuỗi tuần, chốt 24/09/2026).

Ràng buộc phải khoá lại:
1. Thay đổi giữa 2 mốc chỉ tính trên đơn vị có số ở CẢ HAI ngày — đơn vị nhập thêm/bớt không được
   biến thành "tồn kho tăng/giảm".
2. Mốc là ngày có số gần nhất ≤ ngày hỏi; trước ngày đầu tiên có số thì không có gì (không bù số tuần).
3. Mô hình "+ tồn kho" (v1i/v1f) thiếu tồn kho thì KHÔNG trả số của rổ futures mang tên khác.
4. Số thật cộng từ biểu Tồn kho đơn vị: cả khối đã nhập kho lẫn chưa nhập kho.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import floor_suggest as fs
from app.services import inventory_daily as idy
from app.services import unit_daily_repo

A, B = "_zz_invd_a", "_zz_invd_b"
D1, D2, D3 = "2026-08-01", "2026-08-05", "2026-08-09"
SNAPS: idy.Snapshots = {D1: {A: 100.0}, D2: {A: 110.0}, D3: {A: 120.0, B: 500.0}}

needs_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")


def test_day_at_picks_latest_day_not_after() -> None:
    assert idy.day_at(SNAPS, "2026-08-07") == D2
    assert idy.day_at(SNAPS, D3) == D3
    assert idy.day_at(SNAPS, "2026-07-31") is None          # trước ngày đầu có số → không bù
    assert idy.day_at(SNAPS, None) is None


def test_series_is_daily_total_in_date_order() -> None:
    assert idy.series(SNAPS) == [(D1, 100.0), (D2, 110.0), (D3, 620.0)]


@needs_db
def test_change_counts_only_units_present_on_both_days() -> None:
    """B mới nhập ở D3: tổng nhảy 110 → 620 nhưng tồn kho thật chỉ tăng 10 tấn (của A)."""
    inv = idy.at(SNAPS, D3, D2)
    assert inv["ton_kho"] == 620 and inv["units_counted"] == 2
    assert inv["base_day"] == D2 and inv["units_compared"] == 1
    assert inv["d_ton_kho"] == 10
    assert inv["d_ton_kho_pct"] == pytest.approx(9.09, abs=0.01)
    assert inv["ton_free"] == 620 and inv["ton_kho_hd"] == 0   # không có hợp đồng → toàn bộ tự do


@needs_db
def test_no_base_before_first_day_means_no_change() -> None:
    inv = idy.at(SNAPS, D2, "2026-07-20")
    assert inv["base_day"] is None and inv["d_ton_kho"] is None and inv["d_ton_kho_pct"] is None
    assert idy.at(SNAPS, "2026-07-20") is None


def test_inventory_model_without_inventory_returns_nothing() -> None:
    """v1i/v1f thiếu tồn kho thì trả None thay vì âm thầm chạy như v1."""
    train = [f"2025-{m:02d}-01" for m in range(1, 13)]
    target = "2026-01-01"
    idx = {k: [(d, 100.0 + i * (1 + j)) for i, d in enumerate(train + [target])]
           for j, k in enumerate(fs.FEATS[1:])}
    fmap = {(d, "G"): 1000.0 + i * 10 for i, d in enumerate(train)}
    assert fs._fit_at(train, target, "G", fmap, idx, "v1", 1.0) is not None
    assert fs._fit_at(train, target, "G", fmap, idx, "v1i", 1.0) is None
    assert fs._fit_at(train, target, "G", fmap, idx, "v1f", 1.0) is None


@needs_db
def test_load_sums_both_stock_blocks_from_unit_reports() -> None:
    day = (date.today() - timedelta(days=1)).isoformat()
    before = idy.load(day, day).get(day, {})
    try:
        unit_daily_repo.upsert("consumption", day, A, {
            "stock_warehoused": [{"grade": "SVR 10", "qty": 70.0}],
            "stock_not_warehoused": [{"grade": "SVR 10", "qty": 30.0}],
        }, "test")
        got = idy.load(day, day)
        assert A not in before
        assert got[day][A] == pytest.approx(100.0)
    finally:
        with session_scope() as db:
            db.execute(text("DELETE FROM unit_daily_report WHERE company = :c"), {"c": A})


def test_latex_price_drops_only_partial_tail_days() -> None:
    """Sáng mới 1/7 đơn vị nhập giá mủ nước → bỏ ngày đó; giữa chuỗi ít đơn vị (thật) thì giữ."""
    steady = [(f"2026-09-{d:02d}", 550.0, 7) for d in range(1, 24)]
    assert fs._drop_partial_tail(steady + [("2026-09-24", 495.0, 1)])[-1] == ("2026-09-23", 550.0)
    assert fs._drop_partial_tail(steady)[-1] == ("2026-09-23", 550.0)
    only_one = [(f"2026-03-{d:02d}", 500.0, 1) for d in range(1, 29)]   # 03/2026: cả tháng 1 đơn vị
    assert len(fs._drop_partial_tail(only_one)) == len(only_one)
    assert fs._drop_partial_tail([]) == []
