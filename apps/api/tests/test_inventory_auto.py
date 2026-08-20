"""Test tự tính TỒN KHO TẬP ĐOÀN từ biểu Tồn kho của đơn vị thành viên.

Ràng buộc phải khoá lại:
1. Công tắc TẮT (mặc định) → đơn vị nộp số không được đụng vào chuỗi tuần (hành vi cũ).
2. Công tắc BẬT → đơn vị nộp là tuần tương ứng có số, `source='auto'`.
3. Tuần chuyên viên đã nhập TAY thì đường tự động KHÔNG bao giờ đè.
4. Nút "Đồng bộ tuần này" chạy được cả khi TẮT và ĐƯỢC đè số tay (thao tác cố ý).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import inventory_auto, inventory_repo, unit_daily_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_inv_unit"

#: Ngày chốt tuần dùng cho test — thứ Sáu ĐÃ QUA gần nhất (tuần chưa tới thì không được ghi).
ANCHOR = inventory_auto.last_anchor()
DAY = ANCHOR.isoformat()

#: Số tồn của riêng đơn vị test (chỉ khối "Đã nhập kho" mới được cộng vào tồn kho Tập đoàn).
STOCK = {"stock_warehoused": [{"grade": "SVR 10", "qty": 120.0}],
         "stock_not_warehoused": [{"grade": "SVR 10", "qty": 55.0}]}


@pytest.fixture()
def seeded():
    """1 đơn vị thành viên + header admin; dọn sạch chuỗi tuần test sau khi chạy."""
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    _clear()
    yield h
    inventory_auto.save_config(False, by="test")
    _clear()
    client.delete(f"/api/member-units/{UNIT}", headers=h)


def _clear() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c"), {"c": UNIT})
        db.execute(text("DELETE FROM fact_inventory WHERE as_of = CAST(:a AS date)"), {"a": DAY})
        # Nhật ký chạy của job tuần (test có gọi job) — không để lại rác ở trang Lịch chạy.
        db.execute(text("DELETE FROM meta_crawl_run WHERE sources = :s"),
                   {"s": inventory_auto.WEEKLY_JOB_SOURCE})


def _save_stock(as_of: str = DAY) -> None:
    unit_daily_repo.upsert("consumption", as_of, UNIT, dict(STOCK), "test")


def _week() -> dict | None:
    return inventory_repo.get(DAY)


def test_anchors_stay_on_friday_and_never_run_ahead():
    """Ngày chốt = thứ Sáu; bản ghi ảnh hưởng tối đa 2 tuần và không lấn sang tuần chưa tới."""
    assert ANCHOR.weekday() == inventory_auto.ANCHOR_WEEKDAY
    thu = (ANCHOR - timedelta(days=1)).isoformat()
    assert inventory_auto.anchors_for(thu) == [DAY]          # thứ Năm → chốt vào thứ Sáu cùng tuần
    # Chính ngày chốt: vẫn còn là số mới nhất của tuần sau nếu đơn vị không nộp thêm.
    assert inventory_auto.anchors_for(DAY)[0] == DAY
    # Ngày mai không thuộc tuần nào đã chốt xong.
    assert inventory_auto.anchors_for((date.today() + timedelta(days=1)).isoformat()) == []


def test_off_by_default_keeps_series_untouched(seeded):
    """Mặc định TẮT: đơn vị nộp số cũng không sinh dòng tuần nào."""
    assert inventory_auto.enabled() is False
    _save_stock()
    assert _week() is None


def test_on_writes_week_from_unit_stock(seeded):
    """BẬT: đơn vị nộp → tuần có số, lấy khối "Đã nhập kho" (KHÔNG cộng khối chưa nhập kho)."""
    inventory_auto.save_config(True, by="test")
    _save_stock()
    w = _week()
    assert w is not None and w["source"] == inventory_auto.AUTO_SOURCE
    # Các đơn vị khác trong DB cũng được cộng → chỉ kiểm phần đóng góp của đơn vị test.
    only = inventory_auto.compute(DAY)
    assert w["ton_kho"] == only["ton_kho"]
    assert "đơn vị thành viên" in (w["note"] or "")


def test_auto_never_overwrites_manual_week(seeded):
    """Tuần chuyên viên đã gõ tay: đường tự động giữ nguyên, không đè."""
    inventory_repo.upsert(DAY, 111.0, 22.0, "số của Ban TTKD")
    inventory_auto.save_config(True, by="test")
    _save_stock()
    w = _week()
    assert (w["ton_kho"], w["source"]) == (111.0, "manual")
    assert inventory_auto.apply_week(DAY)["reason"] == "manual"


def test_manual_sync_button_works_while_off_and_overwrites(seeded):
    """Nút "Đồng bộ tuần này": chạy cả khi TẮT và ghi đè số tay (chuyên viên chủ động bấm)."""
    inventory_repo.upsert(DAY, 111.0, 22.0, "số của Ban TTKD")
    _save_stock()
    assert inventory_auto.enabled() is False
    res = inventory_auto.apply_week(DAY, force=True, by="test")
    assert res["written"] is True
    w = _week()
    assert w["source"] == inventory_auto.AUTO_SOURCE and w["ton_kho"] != 111.0


def test_api_endpoints(seeded):
    """API: xem trước không ghi gì · apply ghi · recompute giữ tuần nhập tay."""
    h = seeded
    _save_stock()
    pre = client.get(f"/api/inventory/auto/preview?as_of={DAY}", headers=h)
    assert pre.status_code == 200 and pre.json()["units_counted"] >= 1
    assert _week() is None                       # xem trước KHÔNG được ghi gì

    assert client.post(f"/api/inventory/auto/apply?as_of={DAY}", headers=h).status_code == 200
    assert _week()["source"] == inventory_auto.AUTO_SOURCE

    inventory_repo.upsert(DAY, 111.0, 22.0, "số của Ban TTKD")
    res = client.post("/api/inventory/auto/recompute?weeks=1", headers=h)
    assert res.status_code == 200 and DAY in res.json()["kept_manual"]
    assert _week()["ton_kho"] == 111.0


def test_weekly_job_writes_when_on_and_skips_when_off(seeded):
    """Job tối thứ Sáu: TẮT → không ghi tuần nào (vẫn ghi nhật ký chạy); BẬT → ghi tuần chốt."""
    _save_stock()
    off = inventory_auto.run_weekly_job()
    assert off["persisted"] == 0 and _week() is None
    assert "TẮT" in off["sources"][0]["note"]

    inventory_auto.save_config(True, by="test")
    on = inventory_auto.run_weekly_job()
    assert on["persisted"] >= 1
    assert _week()["source"] == inventory_auto.AUTO_SOURCE
