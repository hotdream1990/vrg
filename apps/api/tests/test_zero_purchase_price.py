"""Test quy ước: **ĐƠN GIÁ THU MUA = 0 NGHĨA LÀ "KHÔNG CÓ GIÁ"** (chốt 11/08/2026).

Người nhập được phép gõ 0 (ngày đó đơn vị không công bố giá / không mua) — không báo lỗi —
nhưng số 0 KHÔNG được lưu thành một mức giá. Nếu lọt vào kho giá thì:
  - bản tin in ra khoảng "0-550 đồng/độ" cho cả khu vực,
  - gợi ý giá sàn hồi quy trên một cú rơi về 0 không có thật,
  - giá bình quân gia quyền của kỳ bị kéo tụt.

Khác hẳn GIÁ SÀN: ở đó 0 = phiên No Trading, là dữ liệu thật và phải giữ (xem `test_no_trading`).
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
UNIT = "_zz_zero_price_unit"
DAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture()
def seeded():
    """1 đơn vị + 1 tài khoản đơn vị thành viên được gán đơn vị đó."""
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.delete("/api/users/zz_zero_mem", headers=h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    client.post("/api/users", json={"username": "zz_zero_mem", "password": "pass123",
                                    "role": "member", "member_units": [UNIT]}, headers=h)
    mtok = client.post("/api/auth/login",
                       json={"username": "zz_zero_mem", "password": "pass123"}).json()
    yield h, {"Authorization": f"Bearer {mtok['access_token']}"}
    with session_scope() as db:
        db.execute(text("DELETE FROM fact_price WHERE grade = :g"), {"g": UNIT})
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :g"), {"g": UNIT})
    client.delete("/api/users/zz_zero_mem", headers=h)
    client.delete(f"/api/member-units/{UNIT}", headers=h)


def _unit_price(price_type: str = "purchase") -> dict[str, float]:
    return price_repo.purchase_by_company_on_date(DAY, price_type, PURCHASE_SOURCE_UNIT)


def test_member_may_submit_zero_without_error(seeded) -> None:
    """Đơn vị gõ 0: nhận 200 (không còn 422), và kho giá KHÔNG có bản ghi nào cho ngày đó."""
    _, mh = seeded
    res = client.put("/api/member/prices", headers=mh,
                     json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 0})
    assert res.status_code == 200, res.text
    assert res.json()["cleared"] is True
    assert UNIT not in _unit_price()


def test_zero_clears_a_price_entered_earlier(seeded) -> None:
    """Đã lỡ khai giá rồi sửa về 0 → xoá hẳn ô giá, không để lại mức giá 0."""
    _, mh = seeded
    body = {"company": UNIT, "as_of": DAY, "price_type": "purchase_cup"}
    client.put("/api/member/prices", headers=mh, json={**body, "price": 300})
    assert _unit_price("purchase_cup")[UNIT] == 300

    client.put("/api/member/prices", headers=mh, json={**body, "price": 0})
    assert UNIT not in _unit_price("purchase_cup")


def test_negative_price_still_rejected(seeded) -> None:
    """Chỉ mở cho 0 — số âm vẫn là nhập sai."""
    _, mh = seeded
    res = client.put("/api/member/prices", headers=mh,
                     json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": -5})
    assert res.status_code == 422


def test_hq_grid_zero_does_not_store_a_price(seeded) -> None:
    """Lưới Giá mủ nguyên liệu của chuyên viên cũng theo cùng quy ước (chặn ở tầng repo)."""
    h, _ = seeded
    rec = {"as_of": DAY, "source": PURCHASE_SOURCE_HQ, "grade": UNIT, "contract": "",
           "price_type": "purchase", "currency": "VND", "unit": "đồng/độ TSC"}
    assert client.put("/api/prices/records", headers=h, json={**rec, "price": 520}).status_code == 200
    assert client.put("/api/prices/records", headers=h, json={**rec, "price": 0}).status_code == 200
    assert UNIT not in price_repo.purchase_by_company_on_date(DAY, "purchase", PURCHASE_SOURCE_HQ)


def test_settlement_zero_is_kept_as_no_trading(seeded) -> None:
    """Giá SÀN bằng 0 vẫn phải lưu: đó là phiên No Trading, không phải 'không có giá'."""
    price_repo.upsert_record({"as_of": DAY, "source": "sgx", "grade": UNIT, "contract": "",
                              "price_type": "settlement", "price": 0,
                              "currency": "USD", "unit": "USD/tonne"})
    with session_scope() as db:
        got = db.execute(text("SELECT price FROM fact_price WHERE grade = :g "
                              "AND price_type = 'settlement' AND as_of = CAST(:d AS date)"),
                         {"g": UNIT, "d": DAY}).scalar()
    assert got == 0


def test_bulletin_range_skips_a_zero_written_straight_to_db(seeded) -> None:
    """Bản ghi 0 lọt vào bằng đường khác (script import lịch sử ghi thẳng SQL) vẫn không được đọc.

    Đây là hàng rào cuối trước mục 'Giá mủ nguyên liệu' của bản tin — nơi khoảng giá khu vực
    lấy min/max, chỉ cần một số 0 là in ra "0-550 đồng/độ".
    """
    with session_scope() as db:
        db.execute(text(
            "INSERT INTO fact_price (as_of, source, grade, contract, price_type, price, currency, unit) "
            "VALUES (CAST(:d AS date), :s, :g, '', 'purchase', 0, 'VND', 'đồng/độ TSC') "
            "ON CONFLICT (as_of, source, grade, price_type) DO UPDATE SET price = 0"),
            {"d": DAY, "s": PURCHASE_SOURCE_HQ, "g": UNIT})
    assert UNIT not in price_repo.purchase_by_company_on_date(DAY)
    assert (UNIT, DAY) not in price_repo.purchase_prices_in_range(DAY, DAY)


def test_stats_treat_zero_unit_price_as_missing(seeded) -> None:
    """Thống kê Thu mua: đơn giá 0 không kéo tụt bình quân, mà bị đếm là THIẾU giá.

    Mủ nước có sản lượng nhưng giá khai 0 → không có mức giá nào để bình quân (`None`, hiện "—")
    và dòng đó phải rơi vào cảnh báo, thay vì lặng lẽ kéo giá bình quân của kỳ về gần 0.
    """
    h, mh = seeded
    client.put("/api/member/prices", headers=mh,
               json={"company": UNIT, "as_of": DAY, "price_type": "purchase", "price": 0})
    client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": UNIT, "as_of": DAY,
        "fields": {"latex_wet": 10, "coagulum": 5},
    })
    client.put("/api/member/prices", headers=mh,
               json={"company": UNIT, "as_of": DAY, "price_type": "purchase_cup", "price": 300})
    rep = client.get("/api/unit-daily/analytics/purchase", headers=h,
                     params={"date_from": DAY, "date_to": DAY, "companies": UNIT}).json()
    row = next(r for r in rep["rows"] if r["key"] == UNIT)
    assert row["price_latex_avg"] is None                  # 0 KHÔNG phải một mức giá
    assert row["price_cup_avg"] == pytest.approx(300)      # loại kia vẫn tính bình thường
    assert any("chưa có đơn giá" in w for w in rep["warnings"])
