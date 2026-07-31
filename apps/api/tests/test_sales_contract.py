"""Test HỢP ĐỒNG BÁN HÀNG 2 CẤP + danh mục khách hàng + tiêu thụ/khối 3 tính từ hợp đồng."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

UNIT = "_zz_sc_unit"
UNIT2 = "_zz_sc_unit2"
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = ANY(:u) OR to_company = ANY(:u)"),
                   {"u": [UNIT, UNIT2]})
        db.execute(text("DELETE FROM unit_customer WHERE company = ANY(:u)"), {"u": [UNIT, UNIT2]})
    for n in (UNIT, UNIT2):
        client.delete(f"/api/member-units/{n}", headers=h)


def _line(grade="SVR 10 / CSR 10", qty=100.0, **kw) -> dict:
    return {"grade": grade, "qty": qty, "price": 40.0, "ccy": "VND", **kw}


@pytest.fixture()
def env():
    h = _admin()
    _cleanup(h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    client.post("/api/member-units", json={"name": UNIT2}, headers=h)
    yield h
    _cleanup(h)


def test_customer_is_per_unit_and_unique(env) -> None:
    h = env
    r = client.put("/api/customers", json={"company": UNIT, "name": "Khách A", "code": "KA"}, headers=h)
    assert r.status_code == 200, r.text
    # Cùng đơn vị, trùng tên → chặn.
    dup = client.put("/api/customers", json={"company": UNIT, "name": "Khách A"}, headers=h)
    assert dup.status_code == 400 and "đã có khách hàng" in dup.json()["detail"]
    # Đơn vị KHÁC trùng tên → cho phép (danh mục tách riêng theo đơn vị).
    assert client.put("/api/customers", json={"company": UNIT2, "name": "Khách A"},
                      headers=h).status_code == 200

    names = {(c["company"], c["name"]) for c in client.get("/api/customers", headers=h).json()}
    assert (UNIT, "Khách A") in names and (UNIT2, "Khách A") in names


def test_contract_rejects_customer_of_another_unit(env) -> None:
    h = env
    cid = client.put("/api/customers", json={"company": UNIT2, "name": "Khách B"},
                     headers=h).json()["id"]
    r = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-X", "customer_id": cid, "delivery_type": "single",
        "sign_date": TODAY, "lines": [_line()]}, headers=h)
    assert r.status_code == 400 and "đơn vị khác" in r.json()["detail"]


def test_multi_contract_children_cannot_exceed_parent(env) -> None:
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-M1", "delivery_type": "multi", "sign_date": YESTERDAY,
        "lines": [_line(qty=100.0)]}, headers=h).json()["contract"]

    ok = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-01", "delivered_at": TODAY,
        "channel": "export", "lines": [_line(qty=60.0)]}, headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract"]["delivered"] is True   # phụ lục tự chuyển ĐÃ GIAO

    over = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-02", "delivered_at": TODAY,
        "channel": "domestic", "lines": [_line(qty=50.0)]}, headers=h)
    assert over.status_code == 400 and "vượt sản lượng còn lại" in over.json()["detail"]

    detail = client.get(f"/api/sales-contracts/{parent['id']}", headers=h).json()
    assert detail["delivered_qty"] == pytest.approx(60.0)
    assert detail["remaining_qty"] == pytest.approx(40.0)


def test_dry_weight_required_on_delivery_only(env) -> None:
    h = env
    # Hợp đồng mẹ giao-nhiều-lần chỉ là cam kết → KHÔNG ép quy khô.
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-L", "delivery_type": "multi", "sign_date": YESTERDAY,
        "lines": [_line(grade="LATEX", qty=50.0)]}, headers=h)
    assert parent.status_code == 200, parent.text

    # Phụ lục = lần giao thật → bán LATEX bắt buộc quy khô.
    bad = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent.json()["contract"]["id"], "code": "PL-L1",
        "delivered_at": TODAY, "channel": "export",
        "lines": [_line(grade="LATEX", qty=10.0)]}, headers=h)
    assert bad.status_code == 400 and "quy khô" in bad.json()["detail"]

    good = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent.json()["contract"]["id"], "code": "PL-L1",
        "delivered_at": TODAY, "channel": "export",
        "lines": [_line(grade="LATEX", qty=10.0, qty_dry=3.5)]}, headers=h)
    assert good.status_code == 200, good.text


def test_foreign_currency_needs_fx(env) -> None:
    h = env
    bad = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-LAK", "delivery_type": "single", "sign_date": TODAY,
        "lines": [_line(qty=5.0, ccy="LAK")]}, headers=h)
    assert bad.status_code == 400 and "tỷ giá" in bad.json()["detail"]

    ok = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-LAK", "delivery_type": "single", "sign_date": TODAY,
        "lines": [_line(qty=5.0, ccy="LAK", price=900_000.0, fx=1.24)]}, headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract"]["revenue"] == pytest.approx(5.0 * 900_000.0 * 1.24)


def test_consumption_and_block3_computed_from_contracts(env) -> None:
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-M2", "delivery_type": "multi", "sign_date": YESTERDAY,
        "lines": [_line(qty=100.0)]}, headers=h).json()["contract"]
    client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-A", "delivered_at": TODAY,
        "channel": "internal", "to_company": UNIT2,
        "lines": [_line(qty=30.0, cost=12.0)]}, headers=h)

    cons = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert cons["qty"] == pytest.approx(30.0)
    assert cons["by_channel"]["internal"] == pytest.approx(30.0)
    assert cons["cost"] == pytest.approx(12.0)
    assert cons["revenue"] == pytest.approx(30.0 * 40.0 * 1_000_000)

    und = client.get(f"/api/sales-contracts/undelivered?as_of={TODAY}&company={UNIT}",
                     headers=h).json()["by_company"][UNIT]
    assert und["qty"] == pytest.approx(70.0)

    # Tại NGÀY HÔM QUA lần giao chưa xảy ra → khối 3 vẫn là toàn bộ 100 tấn (không lấy số ngày khác).
    und_y = client.get(f"/api/sales-contracts/undelivered?as_of={YESTERDAY}&company={UNIT}",
                       headers=h).json()["by_company"][UNIT]
    assert und_y["qty"] == pytest.approx(100.0)


def test_revenue_unknown_when_fx_missing_is_not_zero(env) -> None:
    """Thiếu tỷ giá → doanh thu là KHÔNG BIẾT (None), tuyệt đối không quy về 0."""
    h = env
    c = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-USD", "delivery_type": "single", "sign_date": YESTERDAY,
        "delivered": True, "delivered_at": TODAY, "channel": "export",
        "lines": [_line(qty=10.0, ccy="USD", price=1800.0, fx=26000.0)]}, headers=h)
    assert c.status_code == 200, c.text
    # Gỡ tỷ giá thẳng dưới DB (mô phỏng bản ghi cũ thiếu tỷ giá) rồi kiểm tổng hợp.
    with session_scope() as db:
        db.execute(text("UPDATE sales_contract SET lines = jsonb_set(lines, '{0,fx}', 'null') "
                        "WHERE id = :i"), {"i": c.json()["contract"]["id"]})
    cons = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert cons["revenue"] is None
    assert cons["qty"] == pytest.approx(10.0)


def test_delete_parent_blocked_while_children_exist(env) -> None:
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-M3", "delivery_type": "multi", "sign_date": YESTERDAY,
        "lines": [_line(qty=20.0)]}, headers=h).json()["contract"]
    child = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-Z", "delivered_at": TODAY,
        "channel": "export", "lines": [_line(qty=5.0)]}, headers=h).json()["contract"]

    blocked = client.delete(f"/api/sales-contracts/{parent['id']}", headers=h)
    assert blocked.status_code == 400 and "phụ lục" in blocked.json()["detail"]
    assert client.delete(f"/api/sales-contracts/{child['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/sales-contracts/{parent['id']}", headers=h).status_code == 200


def test_migrated_day_is_not_counted_twice(env) -> None:
    """Ngày đã chuyển sang hợp đồng: mảng `sales` cũ vẫn còn nhưng KHÔNG được cộng lần nữa."""
    from app.services import unit_daily_repo, unit_period_report

    line = {"code": "X1", "contract": "long_term", "channel": "export",
            "grade": "SVR 10 / CSR 10", "qty": 40.0, "price": 45.0, "ccy": "VND"}
    unit_daily_repo.upsert("consumption", TODAY, UNIT, {"sales": [line], "revenue": 40 * 45e6}, "admin")
    before = unit_period_report.period_report("consumption", TODAY, TODAY, [UNIT])
    assert before["rows"][0]["total_consumption"] == pytest.approx(40.0)

    # Bật cờ như script chuyển đổi làm — mảng cũ giữ nguyên, báo cáo phải bỏ qua.
    unit_daily_repo.upsert("consumption", TODAY, UNIT,
                           {"sales": [line], "revenue": 40 * 45e6, "sales_migrated": True}, "admin")
    after = unit_period_report.period_report("consumption", TODAY, TODAY, [UNIT])
    rows = after["rows"]
    assert not rows or rows[0]["total_consumption"] in (0, 0.0, None)

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c AND as_of = :d"),
                   {"c": UNIT, "d": TODAY})


def test_migrated_flag_survives_a_normal_edit(env) -> None:
    """Form Tồn kho không gửi `sales_migrated` — repo phải tự giữ, nếu không mảng cũ sống lại."""
    from app.services import unit_daily_repo

    unit_daily_repo.upsert("consumption", TODAY, UNIT,
                           {"sales": [{"grade": "SVR 3L", "qty": 5.0}], "sales_migrated": True}, "admin")
    unit_daily_repo.upsert("consumption", TODAY, UNIT,           # lưu lại như form Tồn kho vẫn làm
                           {"stock_warehoused": [{"grade": "SVR 3L", "qty": 9.0}]}, "admin")
    got = unit_daily_repo.entries_on("consumption", TODAY)[UNIT]["fields"]
    assert got.get("sales_migrated") is True

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c AND as_of = :d"),
                   {"c": UNIT, "d": TODAY})


def test_file_download_blocked_across_units(env) -> None:
    from app.services import sales_contract_repo

    c = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-F", "delivery_type": "single", "sign_date": TODAY,
        "files": [{"file": "abc123.pdf", "filename": "hd.pdf"}],
        "lines": [_line()]}, headers=env)
    assert c.status_code == 200, c.text
    assert sales_contract_repo.companies_of_file("abc123.pdf") == {UNIT}
    assert sales_contract_repo.companies_of_file("khong-co.pdf") == set()


def test_parent_cycle_of_any_depth_is_rejected(env) -> None:
    """A→B→C→A: vòng lặp sâu 3 mắt cũng phải bị chặn, không chỉ vòng 2 mắt."""
    from app.services import member_unit_repo

    third = "_zz_sc_unit3"
    client.post("/api/member-units", json={"name": third}, headers=env)
    try:
        member_unit_repo.set_parent(UNIT2, UNIT)     # UNIT2 → UNIT
        member_unit_repo.set_parent(third, UNIT2)    # third  → UNIT2 → UNIT
        with pytest.raises(ValueError, match="vòng lặp"):
            member_unit_repo.set_parent(UNIT, third)  # UNIT → third ⇒ vòng
    finally:
        for u in (third, UNIT2, UNIT):
            member_unit_repo.set_parent(u, None)
        client.delete(f"/api/member-units/{third}", headers=env)


def test_member_scope_is_enforced(env) -> None:
    h = env
    client.delete("/api/users/sc_mem", headers=h)
    assert client.post("/api/users", json={"username": "sc_mem", "password": "pass123",
                                           "role": "member", "member_units": [UNIT]},
                       headers=h).status_code == 200
    tok = client.post("/api/auth/login",
                      json={"username": "sc_mem", "password": "pass123"}).json()["access_token"]
    mh = {"Authorization": f"Bearer {tok}"}
    try:
        # Đơn vị chỉ thấy đơn vị của mình trong meta.
        assert client.get("/api/sales-contracts/meta", headers=mh).json()["units"] == [UNIT]
        # Ghi sang đơn vị khác → 403.
        r = client.put("/api/sales-contracts", json={
            "company": UNIT2, "code": "HD-NO", "delivery_type": "single", "sign_date": TODAY,
            "lines": [_line()]}, headers=mh)
        assert r.status_code == 403
    finally:
        client.delete("/api/users/sc_mem", headers=h)
