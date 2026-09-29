"""Chỉ tiêu năm — màn Thống kê tiêu thụ và thẻ Chỉ tiêu năm của Dashboard (rà soát 29/09/2026).

A5: cột "KH doanh thu" + "% thực hiện KH doanh thu" của Thống kê tiêu thụ luôn trống vì API không trả.
    % KH doanh thu theo RỔ đơn vị được giao KH, như Dashboard (Σ/Σ cả nhóm ra 213% thay vì 80,6%).
C1: xem MỘT đơn vị chưa được giao KH thì web lấy `scope_done` làm số chính — API phải trả đủ.

Một khu vực, ba đơn vị (giao hàng HĐ chuyến hôm nay, giá VND theo triệu đ/tấn):
- A: KH chuyến 100 t, KH doanh thu 10 tỷ; giao 20 t @50 = 1 tỷ.
- B: KH doanh thu 5 tỷ; giao 10 t @60 = 0,6 tỷ + 5 t CHƯA có đơn giá → doanh thu đang thiếu.
- C: chưa giao KH; giao 10 t @40 = 0,4 tỷ.
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
UNIT_A, UNIT_B, UNIT_C = "_zz_tc_a", "_zz_tc_b", "_zz_tc_c"
UNITS = [UNIT_A, UNIT_B, UNIT_C]
REGION = "_zz_tc_region"
TODAY = date.today().isoformat()
YEAR = date.today().year
GRADE = "SVR 10 / CSR 10"
PERIOD = {"date_from": f"{YEAR}-01-01", "date_to": TODAY}


def _h() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _customer(h: dict[str, str], company: str) -> int:
    made = client.put("/api/customers", json={"company": company, "name": f"KH {company}"},
                      headers=h).json().get("id")
    return made if made is not None else next(
        c["id"] for c in client.get(f"/api/customers?company={company}", headers=h).json()["items"]
        if c["company"] == company)


def _deliver(h: dict[str, str], company: str, code: str, qty: float, price: float | None) -> None:
    r = client.put("/api/sales-contracts", headers=h, json={
        "company": company, "code": code, "customer_id": _customer(h, company),
        "delivery_type": "single", "contract_type": "spot", "sign_date": TODAY,
        "delivered_at": TODAY, "channel": "domestic",
        "lines": [{"grade": GRADE, "qty": qty, "price": price, "ccy": "VND"}]})
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
    for n, plan in ((UNIT_A, {"plan_sales_spot_tonnes": 100, "plan_revenue_ty": 10}),
                    (UNIT_B, {"plan_revenue_ty": 5})):
        assert client.put("/api/unit-daily/plan", headers=h,
                          json={"year": YEAR, "company": n, **plan}).status_code == 200
    _deliver(h, UNIT_A, "TC-A-1", 20, 50)
    _deliver(h, UNIT_B, "TC-B-1", 10, 60)
    _deliver(h, UNIT_B, "TC-B-2", 5, None)
    _deliver(h, UNIT_C, "TC-C-1", 10, 40)
    yield h
    _cleanup(h)


def _stats(h: dict[str, str], group_by: str, companies: list[str] = UNITS) -> dict:
    r = client.get("/api/unit-daily/analytics/consumption", headers=h,
                   params={**PERIOD, "group_by": group_by, "companies": ",".join(companies)})
    assert r.status_code == 200, r.text
    return r.json()


def _targets(h: dict[str, str], unit: str) -> dict[str, dict]:
    r = client.get("/api/unit-dashboard/targets", headers=h,
                   params={"scope": "unit", "key": unit, **PERIOD})
    assert r.status_code == 200, r.text
    return {i["key"]: i for i in r.json()["items"]}


def test_consumption_stats_returns_revenue_plan_and_pct(env):
    rows = {r["key"]: r for r in _stats(env, "company")["rows"]}
    a, b, c = rows[UNIT_A], rows[UNIT_B], rows[UNIT_C]
    assert (a["plan_revenue_ty"], a["revenue_ty"]) == (10, pytest.approx(1))
    assert a["pct_plan_revenue"] == pytest.approx(10)
    assert a["pct_plan_sales_spot"] == pytest.approx(20)          # luật KH chuyến giữ nguyên
    # B có lần giao chưa có đơn giá → doanh thu đang THIẾU: vẫn hiện KH, % để trống (không phải 6%).
    assert (b["plan_revenue_ty"], b["no_revenue_lines"]) == (5, 1)
    assert b["pct_plan_revenue"] is None
    # C chưa giao KH → cả hai ô trống, không ghi 0%.
    assert c["plan_revenue_ty"] is None and c["pct_plan_revenue"] is None


def test_group_level_revenue_pct_uses_planned_units_like_dashboard(env):
    # Khu vực chứa B (được giao KH, thiếu đơn giá) → % của cả nhóm và dòng Tổng cộng để trống.
    rep = _stats(env, "region")
    (region,) = [r for r in rep["rows"] if r["key"] == REGION]
    assert region["plan_revenue_ty"] == 15 and region["pct_plan_revenue"] is None
    assert rep["totals"]["plan_revenue_ty"] == 15 and rep["totals"]["pct_plan_revenue"] is None
    # Bỏ B ra: doanh thu của C (chưa giao KH) KHÔNG vào tử số — 1 ÷ 10, không phải (1 + 0,4) ÷ 10.
    # Cột Doanh thu vẫn là tổng cả nhóm; % KH chuyến giữ Σ/Σ cả nhóm (luật cũ, chờ chốt).
    rep = _stats(env, "region", [UNIT_A, UNIT_C])
    (region,) = rep["rows"]
    assert region["revenue_ty"] == pytest.approx(1.4)
    assert region["pct_plan_revenue"] == pytest.approx(10)
    assert rep["totals"]["pct_plan_revenue"] == pytest.approx(10)
    assert region["pct_plan_sales_spot"] == pytest.approx(30)       # (20 + 10) ÷ 100


def test_bad_price_blocks_revenue_pct(env):
    # Nhập 56.200 vào ô triệu đ/tấn (gõ theo đồng/kg) → doanh thu đội lên, % phải để trống.
    _deliver(env, UNIT_A, "TC-A-BAD", 1, 56200)
    a = next(r for r in _stats(env, "company")["rows"] if r["key"] == UNIT_A)
    assert a["bad_price_lines"] == 1 and a["pct_plan_revenue"] is None


def test_revenue_pct_matches_dashboard(env):
    stats = next(r for r in _stats(env, "company", [UNIT_A])["rows"] if r["key"] == UNIT_A)
    dash = _targets(env, UNIT_A)["revenue"]
    assert stats["pct_plan_revenue"] == pytest.approx(dash["pct"]) == pytest.approx(10)
    # Cấp khu vực: B sửa đơn giá xong → hai màn cùng một số (rổ A + B: 1,6 ÷ 15).
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = :c AND code = 'TC-B-2'"),
                   {"c": UNIT_B})
    stats = _stats(env, "region")["totals"]["pct_plan_revenue"]
    r = client.get("/api/unit-dashboard/targets", headers=env,
                   params={"scope": "region", "key": REGION, **PERIOD})
    dash = next(i for i in r.json()["items"] if i["key"] == "revenue")["pct"]
    assert stats == pytest.approx(dash) == pytest.approx(1.6 / 15 * 100)


def test_unit_without_plan_still_reports_its_own_numbers(env):
    # Web hiện `scope_done` làm số chính khi xem MỘT đơn vị (C1) — rổ rỗng nên `done` vẫn None.
    items = _targets(env, UNIT_C)
    rev, spot = items["revenue"], items["sales_spot"]
    assert (rev["plan"], rev["done"], rev["pct"]) == (None, None, None)
    assert rev["scope_done"] == pytest.approx(0.4)
    assert spot["plan"] is None and spot["scope_done"] == pytest.approx(10)
