"""Test TÁCH LỚP kho "Giá mủ nguyên liệu": giá chuyên viên chốt vs giá đơn vị thành viên tự khai.

Trước đây hai bên ghi chung một ô nên đơn vị lưu biểu Thu mua là đè mất số chuyên viên đã chốt
(và ngược lại). Nay `source='vrg'` (chuyên viên) và `source='vrg_unit'` (đơn vị) nằm riêng:
- Bản tin / báo cáo tuần / gợi ý giá sàn đọc lớp CHUYÊN VIÊN.
- Biểu Thu mua + các bảng thống kê của đơn vị đọc lớp ĐƠN VỊ.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_HQ, PURCHASE_SOURCE_UNIT
from app.main import app
from app.services import price_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_layer_unit"
DAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture()
def seeded():
    """1 đơn vị + 1 tài khoản đơn vị thành viên được gán đơn vị đó."""
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.delete("/api/users/zz_layer_mem", headers=h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    client.post("/api/users", json={"username": "zz_layer_mem", "password": "pass123",
                                    "role": "member", "member_units": [UNIT]}, headers=h)
    mtok = client.post("/api/auth/login", json={"username": "zz_layer_mem", "password": "pass123"}).json()
    yield h, {"Authorization": f"Bearer {mtok['access_token']}"}
    with session_scope() as db:
        db.execute(text("DELETE FROM fact_price WHERE grade = :g"), {"g": UNIT})
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :g"), {"g": UNIT})
    client.delete("/api/users/zz_layer_mem", headers=h)
    client.delete(f"/api/member-units/{UNIT}", headers=h)


def _hq_price(price: float) -> None:
    price_repo.upsert_record({"as_of": DAY, "source": PURCHASE_SOURCE_HQ, "grade": UNIT,
                              "contract": "", "price_type": "purchase", "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


def test_member_write_does_not_overwrite_hq(seeded) -> None:
    """Đơn vị nhập giá của mình KHÔNG được đè lên ô giá chuyên viên đã chốt."""
    _, mh = seeded
    _hq_price(535)
    res = client.put("/api/member/prices", headers=mh,
                     json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 53500})
    assert res.status_code == 200, res.text

    hq = price_repo.purchase_by_company_on_date(DAY, "purchase", PURCHASE_SOURCE_HQ)
    unit = price_repo.purchase_by_company_on_date(DAY, "purchase", PURCHASE_SOURCE_UNIT)
    assert hq[UNIT] == 535        # số chuyên viên còn nguyên
    assert unit[UNIT] == 53500    # số đơn vị nằm ở lớp riêng


def test_hq_write_does_not_overwrite_member(seeded) -> None:
    """Chiều ngược lại: chuyên viên sửa lưới của mình không đụng số đơn vị đã khai."""
    _, mh = seeded
    client.put("/api/member/prices", headers=mh,
               json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 500})
    _hq_price(540)
    assert price_repo.purchase_by_company_on_date(DAY, "purchase", PURCHASE_SOURCE_UNIT)[UNIT] == 500
    assert price_repo.purchase_by_company_on_date(DAY, "purchase", PURCHASE_SOURCE_HQ)[UNIT] == 540


def test_hq_grid_and_member_screen_read_their_own_layer(seeded) -> None:
    """Lưới chuyên viên chỉ thấy số chuyên viên; màn của đơn vị chỉ thấy số đơn vị."""
    h, mh = seeded
    _hq_price(535)
    client.put("/api/member/prices", headers=mh,
               json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 501})

    grid = client.get(f"/api/prices/purchase-sheet?date_from={DAY}&date_to={DAY}", headers=h).json()
    assert grid["values"].get(UNIT, {}).get(DAY) == 535

    mine = client.get("/api/member/prices?days=7", headers=mh).json()
    assert mine["sheets"][UNIT]["purchase"][DAY] == 501


def test_unit_stats_use_member_declared_price(seeded) -> None:
    """Thống kê thu mua tính giá BQ theo số ĐƠN VỊ tự khai (khớp sản lượng do đơn vị nhập)."""
    h, mh = seeded
    _hq_price(535)
    client.put("/api/member/prices", headers=mh,
               json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 600})
    client.put("/api/member/daily-report", headers=mh,
               json={"kind": "purchase", "company": UNIT, "as_of": DAY, "fields": {"latex_wet": 10}})

    rep = client.get("/api/unit-daily/analytics/purchase", headers=h,
                     params={"date_from": DAY, "date_to": DAY, "companies": UNIT}).json()
    row = next(r for r in rep["rows"] if r["key"] == UNIT)
    assert row["price_latex_avg"] == pytest.approx(600)     # KHÔNG phải 535 của chuyên viên


def test_bulletin_layer_reads_hq_price(seeded) -> None:
    """Bản tin/báo cáo lấy lớp chuyên viên — đơn vị khai sai không lọt vào."""
    _, mh = seeded
    _hq_price(535)
    client.put("/api/member/prices", headers=mh,
               json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 53500})
    assert price_repo.purchase_by_company_on_date(DAY)[UNIT] == 535   # mặc định = lớp chuyên viên
