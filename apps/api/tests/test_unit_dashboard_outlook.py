"""Test thẻ "Tiến độ bán hàng năm" của Dashboard đơn vị (phản hồi khách 26/09/2026).

Một khu vực, ba đơn vị:
- A: KH khai thác 1.000 + thu mua 500 t (trong RỔ sản lượng), KH doanh thu 50 tỷ. Giao HĐ chuyến
  100 t @50 triệu; ký HĐ chuyến 200 t chưa giao; HĐ mẹ dài hạn cam kết 300 t — phụ lục 1 (100 t)
  đã giao @50, phụ lục 2 (50 t) chưa giao.
- B: chỉ có KH thu mua (CHƯA nhập KH khai thác) → ngoài rổ sản lượng; giao 50 t @60.
- C: chưa giao lần nào, ký HĐ chuyến 30 t chưa giao → 30 t CHƯA ĐỊNH GIÁ (không mượn giá A/B).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT_A, UNIT_B, UNIT_C = "_zz_ol_a", "_zz_ol_b", "_zz_ol_c"
UNITS = [UNIT_A, UNIT_B, UNIT_C]
REGION = "_zz_ol_region"
TODAY = date.today().isoformat()
YEAR = date.today().year
GRADE = "SVR 10 / CSR 10"
API = "/api/unit-dashboard/outlook"


def _h() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _customer(h: dict[str, str], company: str) -> int:
    made = client.put("/api/customers", json={"company": company, "name": f"KH {company}"},
                      headers=h).json().get("id")
    return made if made is not None else next(
        c["id"] for c in client.get(f"/api/customers?company={company}", headers=h).json()["items"]
        if c["company"] == company)


def _contract(h: dict[str, str], company: str, code: str, qty: float, price: float, *,
              delivered: bool, contract_type: str = "spot", master_id: int | None = None) -> None:
    body = {"company": company, "code": code, "customer_id": _customer(h, company),
            "delivery_type": "single", "contract_type": contract_type, "master_id": master_id,
            "sign_date": TODAY, "channel": "domestic",
            "lines": [{"grade": GRADE, "qty": qty, "price": price, "ccy": "VND"}]}
    if delivered:
        body["delivered_at"] = TODAY
    r = client.put("/api/sales-contracts", json=body, headers=h)
    assert r.status_code == 200, r.text


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "sales_contract", "master_contract",
                    "unit_customer"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": UNITS})
    for n in UNITS:
        client.delete(f"/api/member-units/{n}", headers=h)
    client.delete(f"/api/member-regions/{REGION}", headers=h)


@pytest.fixture()
def env():
    user_repo.seed_admin()
    h = _h()
    _cleanup(h)
    client.post("/api/member-regions", json={"name": REGION}, headers=h)
    for n in UNITS:
        client.post("/api/member-units", json={"name": n}, headers=h)
        client.put(f"/api/member-units/{n}", headers=h, json={"region": REGION, "set_region": True})
    for n, plan in ((UNIT_A, {"plan_exploit_tonnes": 1000, "plan_tonnes": 500, "plan_revenue_ty": 50}),
                    (UNIT_B, {"plan_tonnes": 800})):
        assert client.put("/api/unit-daily/plan", headers=h,
                          json={"year": YEAR, "company": n, **plan}).status_code == 200

    _contract(h, UNIT_A, "OL-A-SPOT-1", 100, 50, delivered=True)
    _contract(h, UNIT_A, "OL-A-SPOT-2", 200, 50, delivered=False)
    m = client.put("/api/master-contracts", headers=h, json={
        "company": UNIT_A, "code": "OL-A-HDDH", "master_type": "long_term",
        "customer_id": _customer(h, UNIT_A), "sign_date": TODAY,
        "lines": [{"grade": GRADE, "qty": 300.0}]})
    assert m.status_code == 200, m.text
    mid = m.json()["master"]["id"]
    _contract(h, UNIT_A, "OL-A-PL-1", 100, 50, delivered=True, contract_type="long_term",
              master_id=mid)
    _contract(h, UNIT_A, "OL-A-PL-2", 50, 50, delivered=False, contract_type="long_term",
              master_id=mid)
    _contract(h, UNIT_B, "OL-B-1", 50, 60, delivered=True)
    _contract(h, UNIT_C, "OL-C-1", 30, 55, delivered=False)
    yield h
    _cleanup(h)


def _get(h: dict[str, str], scope: str, key: str) -> dict:
    r = client.get(API, headers=h, params={"scope": scope, "key": key,
                                           "date_from": f"{YEAR}-01-01", "date_to": f"{YEAR}-12-31"})
    assert r.status_code == 200, r.text
    return r.json()


def test_region_outlook_splits_backlog_and_compares_plans(env):
    d = _get(env, "region", REGION)
    assert d["as_of"] == TODAY
    lt = d["lt"]
    # Cam kết 300 − đã giao 100 = 200 > phụ lục 2 còn 50 → còn phải giao theo HĐ mẹ 200 t.
    assert (lt["committed"], lt["delivered"], lt["remaining"], lt["masters"]) == (300, 100, 200, 1)
    assert lt["pct"] == pytest.approx(100 / 3)
    b = d["backlog"]
    # Phụ lục 2 đã nằm trong phần còn lại của HĐ mẹ — KHÔNG cộng lần nữa.
    assert (b["spot_undelivered"], b["lt_remaining"], b["to_deliver"]) == (230, 200, 430)

    v = d["volume"]
    assert v["delivered_ytd"] == pytest.approx(250)
    assert v["projected"] == pytest.approx(680)
    # Rổ = chỉ A (B chưa nhập KH khai thác): 600 / (1.000 + 500).
    assert (v["plan_exploit"], v["plan_purchase"], v["plan_total"]) == (1000, 500, 1500)
    assert v["basket_projected"] == pytest.approx(600)
    assert v["pct"] == pytest.approx(40)
    assert (v["units_planned"], v["units_missing_exploit"]) == (1, 1)
    assert v["note"] == ""                     # rổ/cả phạm vi là ô số riêng, không lặp thành câu

    rev = d["revenue"]
    # A: 10 tỷ đã thực hiện + 400 t × 50 triệu = 20 tỷ; B: 3 tỷ, không còn gì phải giao.
    assert rev["done_ytd"] == pytest.approx(13)
    assert rev["expected_rest"] == pytest.approx(20)
    assert rev["projected"] == pytest.approx(33)
    assert (rev["plan"], rev["units_planned"]) == (50, 1)
    assert rev["pct"] == pytest.approx(60)
    # C chưa có giá BQ → 30 t chưa định giá, nói rõ, không lấy giá đơn vị khác.
    assert "30,0 tấn" in rev["note"] and UNIT_C in rev["note"]

    rows = {r["label"]: r for r in d["breakdown"]}
    assert set(rows) >= set(UNITS)
    assert rows[UNIT_A]["qty_pct"] == pytest.approx(40)
    assert rows[UNIT_B]["qty_pct"] is None           # chưa nhập KH khai thác → không tính %
    assert rows[UNIT_C]["to_deliver"] == pytest.approx(30)


def test_unit_outlook_lists_master_contracts(env):
    d = _get(env, "unit", UNIT_A)
    assert d["breakdown"] == []
    (item,) = d["items"]
    assert (item["code"], item["committed"], item["delivered"], item["remaining"]) == \
        ("OL-A-HDDH", 300, 100, 200)
    assert item["expired"] is False


def test_bad_price_blocks_revenue_pct(env):
    # Nhập 56.200 ở ô triệu đ/tấn (gõ theo đồng/kg) — doanh thu đội lên 1.000 lần.
    _contract(env, UNIT_A, "OL-A-BAD", 10, 56200, delivered=True)
    d = _get(env, "region", REGION)
    rev = d["revenue"]
    assert rev["pct"] is None
    assert "sai đơn vị tính" in rev["note"] and UNIT_A in rev["note"]
    # Phần còn phải giao của A KHÔNG nhân với giá BQ đã bị đội lên; thẻ báo cảnh báo cho cả phạm vi.
    assert rev["expected_rest"] == pytest.approx(0)
    assert d["warnings"] and UNIT_A in d["warnings"][0]


def test_zero_exploit_plan_is_a_complete_plan(env):
    # Đơn vị không có vườn nhập KH khai thác = 0 → kế hoạch ĐỦ, vào rổ theo KH thu mua.
    assert client.put("/api/unit-daily/plan", headers=env,
                      json={"year": YEAR, "company": UNIT_B, "plan_exploit_tonnes": 0}).status_code == 200
    v = _get(env, "region", REGION)["volume"]
    assert (v["units_planned"], v["units_missing_exploit"]) == (2, 0)
    assert v["plan_total"] == pytest.approx(2300)
    assert v["pct"] == pytest.approx(650 / 2300 * 100)


def test_goods_plan_completes_sales_plan(env):
    """Tân Biên 29/09/2026: bán cả hàng hóa (thành phẩm mua ngoài) mà KH bán hàng chỉ có khai thác +
    thu mua → % ảo 226%. KH hàng hóa là ô riêng: vào KH bán hàng, KHÔNG vào chỉ tiêu thu mua."""
    r = client.put("/api/unit-daily/report", headers=env, json={
        "kind": "purchase", "company": UNIT_A, "as_of": TODAY,
        "fields": {"finished": [{"grade": "SVR 3L", "qty": 400, "price": 50}]}})
    assert r.status_code == 200, r.text
    # Có mua thành phẩm mà chưa nhập KH hàng hóa → nói rõ % đang cao hơn thực tế.
    v = _get(env, "region", REGION)["volume"]
    assert v["plan_total"] == pytest.approx(1500) and not v["plan_goods"]
    assert UNIT_A in v["note"] and "KH hàng hóa" in v["note"]

    assert client.put("/api/unit-daily/plan", headers=env, json={
        "year": YEAR, "company": UNIT_A, "plan_goods_tonnes": 400}).status_code == 200
    v = _get(env, "region", REGION)["volume"]
    assert (v["plan_exploit"], v["plan_purchase"], v["plan_goods"], v["plan_total"]) == \
        (1000, 500, 400, 1900)
    assert v["pct"] == pytest.approx(600 / 1900 * 100)
    assert v["note"] == ""

    items = {i["key"]: i for i in client.get(
        "/api/unit-dashboard/targets", headers=env,
        params={"scope": "unit", "key": UNIT_A, "date_from": f"{YEAR}-01-01",
                "date_to": f"{YEAR}-12-31"}).json()["items"]}
    assert (items["goods"]["done"], items["goods"]["plan"]) == (400, 400)
    # Chỉ tiêu thu mua giữ nguyên rổ mủ nguyên liệu — 400 t thành phẩm không vào tử số.
    assert items["purchase"]["plan"] == 500 and not items["purchase"]["done"]
