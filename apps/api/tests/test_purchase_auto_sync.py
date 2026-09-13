"""Test cầu MỘT CHIỀU: giá đơn vị tự khai (`vrg_unit`) → lớp chuyên viên (`vrg`).

Chuyên viên bật công tắc tổng + chọn đơn vị nào được lấy số tự động; đơn vị nhập là số chảy sang
lưới "Giá mủ nguyên liệu". Mặc định TẮT → hành vi cũ (hai lớp tách hẳn) phải giữ nguyên.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_HQ, PURCHASE_SOURCE_UNIT
from app.main import app
from app.services import price_repo, purchase_price_sync, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_sync_unit"
OTHER = "_zz_sync_other"
DAY = (date.today() - timedelta(days=1)).isoformat()


def _hq(price_type: str = "purchase") -> float | None:
    return price_repo.purchase_by_company_on_date(DAY, price_type, PURCHASE_SOURCE_HQ).get(UNIT)


def _unit_layer(price_type: str = "purchase") -> float | None:
    return price_repo.purchase_by_company_on_date(DAY, price_type, PURCHASE_SOURCE_UNIT).get(UNIT)


@pytest.fixture()
def seeded():
    """2 đơn vị + 1 tài khoản đơn vị thành viên giữ cả hai; trả (header admin, header đơn vị)."""
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.delete("/api/users/zz_sync_mem", headers=h)
    for u in (UNIT, OTHER):
        client.post("/api/member-units", json={"name": u}, headers=h)
    client.post("/api/users", json={"username": "zz_sync_mem", "password": "pass123",
                                    "role": "member", "member_units": [UNIT, OTHER]}, headers=h)
    mtok = client.post("/api/auth/login",
                       json={"username": "zz_sync_mem", "password": "pass123"}).json()
    yield h, {"Authorization": f"Bearer {mtok['access_token']}"}
    purchase_price_sync.save_config(False, [], by="test")
    with session_scope() as db:
        db.execute(text("DELETE FROM fact_price WHERE grade = ANY(:g)"), {"g": [UNIT, OTHER]})
    client.delete("/api/users/zz_sync_mem", headers=h)
    for u in (UNIT, OTHER):
        client.delete(f"/api/member-units/{u}", headers=h)


def _member_price(mh: dict, price: float, company: str = UNIT,
                  price_type: str = "purchase") -> None:
    res = client.put("/api/member/prices", headers=mh,
                     json={"company": company, "as_of": DAY, "price_type": price_type,
                           "price": price})
    assert res.status_code == 200, res.text


def test_off_by_default_keeps_layers_separate(seeded) -> None:
    """Chưa bật gì → số đơn vị KHÔNG được chạm vào lưới chuyên viên (hành vi cũ)."""
    _, mh = seeded
    _member_price(mh, 505)
    assert _unit_layer() == 505
    assert _hq() is None


def test_enabled_unit_flows_to_hq_layer(seeded) -> None:
    """Bật công tắc + chọn đơn vị → đơn vị nhập là lưới chuyên viên có số ngay."""
    h, mh = seeded
    res = client.put("/api/prices/purchase-auto-sync", headers=h,
                     json={"enabled": True, "companies": [UNIT]})
    assert res.status_code == 200, res.text
    _member_price(mh, 512)
    assert _hq() == 512

    _member_price(mh, 520)          # cập nhật cũng phải chảy theo
    assert _hq() == 520
    assert _unit_layer() == 520     # lớp đơn vị vẫn giữ số của mình


def test_cup_price_flows_too(seeded) -> None:
    """Mủ chén đi cùng đường với mủ nước (cùng kho Giá mủ nguyên liệu)."""
    h, mh = seeded
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": [UNIT]})
    _member_price(mh, 480, price_type="purchase_cup")
    assert _hq("purchase_cup") == 480


def test_unselected_unit_is_untouched(seeded) -> None:
    """Đơn vị KHÔNG được chọn thì vẫn phải nhập tay như cũ."""
    h, mh = seeded
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": [UNIT]})
    _member_price(mh, 499, company=OTHER)
    assert price_repo.purchase_by_company_on_date(
        DAY, "purchase", PURCHASE_SOURCE_HQ).get(OTHER) is None


def test_master_switch_off_stops_everything(seeded) -> None:
    """Tắt công tắc tổng → dừng chảy, nhưng danh sách đơn vị đã chọn vẫn còn."""
    h, mh = seeded
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": [UNIT]})
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": False, "companies": [UNIT]})
    _member_price(mh, 530)
    assert _hq() is None
    cfg = client.get("/api/prices/purchase-auto-sync", headers=h).json()
    assert cfg["enabled"] is False
    assert {u["name"] for u in cfg["units"] if u["auto"]} >= {UNIT}


def test_member_clearing_price_clears_hq_cell(seeded) -> None:
    """Đơn vị rút số (nhập 0 / xoá ô) → ô bên chuyên viên cũng phải rỗng, không để lại số ma."""
    h, mh = seeded
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": [UNIT]})
    _member_price(mh, 515)
    assert _hq() == 515
    _member_price(mh, 0)            # 0 = "không có giá" → xoá bản ghi
    assert _unit_layer() is None
    assert _hq() is None


def test_hq_edit_never_writes_back_to_member(seeded) -> None:
    """Chiều ngược lại KHÔNG tồn tại: chuyên viên sửa lưới của mình không đụng số đơn vị."""
    h, mh = seeded
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": [UNIT]})
    _member_price(mh, 500)
    price_repo.upsert_record({"as_of": DAY, "source": PURCHASE_SOURCE_HQ, "grade": UNIT,
                              "contract": "", "price_type": "purchase", "price": 540,
                              "currency": "VND", "unit": "đồng/độ TSC"})
    assert _unit_layer() == 500
    assert _hq() == 540


def test_backfill_copies_prices_entered_before_switch(seeded) -> None:
    """Bật cầu sau khi đơn vị đã nộp → nút "Lấy số đã có" kéo các ngày cũ sang."""
    h, mh = seeded
    _member_price(mh, 507)                       # nộp khi cầu còn TẮT
    assert _hq() is None
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": [UNIT]})
    res = client.post("/api/prices/purchase-auto-sync/backfill?days=7", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["copied"] >= 1
    assert _hq() == 507


# ── Khoá sửa tay: đơn vị đang bật cầu thì ô bên lưới chuyên viên CHỈ XEM ──────────────────────
def _turn_on(h: dict, companies: list[str] | None = None) -> None:
    res = client.put("/api/prices/purchase-auto-sync", headers=h,
                     json={"enabled": True, "companies": companies or [UNIT]})
    assert res.status_code == 200, res.text


def _upsert_hq(h: dict, company: str, price: float, price_type: str = "purchase"):
    return client.put("/api/prices/records", headers=h,
                      json={"as_of": DAY, "source": PURCHASE_SOURCE_HQ, "grade": company,
                            "contract": "", "price_type": price_type, "price": price,
                            "currency": "VND", "unit": "đồng/độ TSC"})


def test_hq_cannot_edit_cell_of_auto_unit(seeded) -> None:
    """Đơn vị đang lấy số tự động → chuyên viên gõ đè bị chặn 409, số của đơn vị giữ nguyên."""
    h, mh = seeded
    _turn_on(h)
    _member_price(mh, 500)
    res = _upsert_hq(h, UNIT, 540)
    assert res.status_code == 409, res.text
    assert "chỉ xem" in res.json()["detail"]
    assert _hq() == 500


def test_hq_cannot_delete_cell_of_auto_unit(seeded) -> None:
    """Xoá 1 ô của đơn vị đang bật cầu cũng bị chặn — số đó thuộc quyền đơn vị."""
    h, mh = seeded
    _turn_on(h)
    _member_price(mh, 501)
    res = client.delete("/api/prices/records", headers=h,
                        params={"as_of": DAY, "source": PURCHASE_SOURCE_HQ, "grade": UNIT,
                                "contract": "", "price_type": "purchase"})
    assert res.status_code == 409, res.text
    assert _hq() == 501


def test_hq_still_edits_units_not_in_list(seeded) -> None:
    """Đơn vị KHÔNG chọn vẫn nhập tay như cũ (không được siết nhầm cả lưới)."""
    h, _ = seeded
    _turn_on(h)
    assert _upsert_hq(h, OTHER, 480).status_code == 200
    assert price_repo.purchase_by_company_on_date(DAY, "purchase", PURCHASE_SOURCE_HQ)[OTHER] == 480


def test_switch_off_unlocks_manual_edit(seeded) -> None:
    """Bỏ đơn vị khỏi danh sách → mở khoá, chuyên viên nhập tay lại được."""
    h, mh = seeded
    _turn_on(h)
    _member_price(mh, 502)
    assert _upsert_hq(h, UNIT, 545).status_code == 409
    client.put("/api/prices/purchase-auto-sync", headers=h,
               json={"enabled": True, "companies": []})
    assert _upsert_hq(h, UNIT, 545).status_code == 200
    assert _hq() == 545


def test_delete_whole_day_keeps_auto_units(seeded) -> None:
    """Xoá cả ngày chỉ dọn ô mình nhập tay, giữ nguyên số của đơn vị đang lấy tự động."""
    h, mh = seeded
    _turn_on(h)
    _member_price(mh, 503)
    assert _upsert_hq(h, OTHER, 470).status_code == 200
    res = client.delete("/api/prices/purchase", headers=h, params={"as_of": DAY})
    assert res.status_code == 200, res.text
    assert res.json()["deleted"] == 1                      # chỉ đơn vị nhập tay bị xoá
    assert _hq() == 503                                    # đơn vị auto còn nguyên
    assert price_repo.purchase_by_company_on_date(DAY, "purchase",
                                                  PURCHASE_SOURCE_HQ).get(OTHER) is None
