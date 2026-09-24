"""Test màn "Dashboard đơn vị" — một phạm vi (Tập đoàn / khu vực / đơn vị), nhiều khối số liệu.

Kiểm 3 thứ dễ sai nhất:
1. Phân quyền: tài khoản đơn vị chỉ xem ĐÚNG đơn vị được gán, dù web gửi phạm vi nào lên.
2. Số của dashboard KHỚP bảng thống kê gốc (không tự cộng lại) — giá khu vực là BQ GIA QUYỀN.
3. Chỉ tiêu là LŨY KẾ từ 01/01, khung dòng tiến độ là DANH SÁCH đơn vị (kể cả đơn vị chưa làm gì).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_UNIT
from app.main import app
from app.services import price_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT_A, UNIT_B, UNIT_C, UNIT_D, UNIT_E = "_zz_db_a", "_zz_db_b", "_zz_db_c", "_zz_db_d", "_zz_db_e"
UNITS = [UNIT_A, UNIT_B, UNIT_C, UNIT_D, UNIT_E]
REGION, REGION_2 = "_zz_db_region", "_zz_db_region_2"
ACCOUNTS = ("db_mem_a", "db_lead_a", "db_noperm")
D0 = (date.today() - timedelta(days=3)).isoformat()
D1 = (date.today() - timedelta(days=2)).isoformat()
YEAR = date.today().year
API = "/api/unit-dashboard"


def _bearer(username: str, password: str) -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": username, "password": password}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _price(unit: str, as_of: str, price: float) -> None:
    price_repo.upsert_record({"as_of": as_of, "source": PURCHASE_SOURCE_UNIT, "grade": unit,
                              "contract": "", "price_type": "purchase", "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


def _customer(h: dict[str, str], company: str) -> int:
    made = client.put("/api/customers", json={"company": company, "name": f"KH {company}"},
                      headers=h).json().get("id")
    return made if made is not None else next(
        c["id"] for c in client.get(f"/api/customers?company={company}", headers=h).json()["items"]
        if c["company"] == company)


def _deliver(h: dict[str, str], company: str, code: str, day: str, grade: str, qty: float,
             price: float) -> None:
    """1 hợp đồng CHUYẾN giao-1-lần đã giao trong ngày `day` (giá VND theo triệu đ/tấn)."""
    r = client.put("/api/sales-contracts", json={
        "company": company, "code": code, "customer_id": _customer(h, company),
        "delivery_type": "single", "contract_type": "spot", "sign_date": day, "start_date": day,
        "delivered_at": day, "channel": "domestic",
        "lines": [{"grade": grade, "qty": qty, "price": price, "ccy": "VND"}]}, headers=h)
    assert r.status_code == 200, r.text


def _cleanup(h: dict[str, str]) -> None:
    for u in ACCOUNTS:
        client.delete(f"/api/users/{u}", headers=h)
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "sales_contract", "master_contract",
                    "unit_customer"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM fact_price WHERE grade = ANY(:u)"), {"u": UNITS})
    for n in UNITS:
        client.delete(f"/api/member-units/{n}", headers=h)
    for r in (REGION, REGION_2):
        client.delete(f"/api/member-regions/{r}", headers=h)


@pytest.fixture()
def env():
    """Khu vực test: A, B có số, C được giao kế hoạch nhưng chưa làm gì.

    Khu vực 2: D mua 9.000 tấn nhưng CHƯA được giao kế hoạch, E được giao 1.000 tấn và mua 100 tấn.
    """
    user_repo.seed_admin()
    h = _bearer("admin", "admin")
    _cleanup(h)
    for r in (REGION, REGION_2):
        client.post("/api/member-regions", json={"name": r}, headers=h)
    for n in UNITS:
        client.post("/api/member-units", json={"name": n}, headers=h)
        client.put(f"/api/member-units/{n}", headers=h,
                   json={"region": REGION_2 if n in (UNIT_D, UNIT_E) else REGION,
                         "set_region": True})
    for n, plan in ((UNIT_A, {"plan_tonnes": 1000, "plan_sales_spot_tonnes": 100,
                              "plan_revenue_ty": 4}),
                    (UNIT_B, {"plan_tonnes": 1000}), (UNIT_C, {"plan_tonnes": 500}),
                    (UNIT_E, {"plan_tonnes": 1000})):
        assert client.put("/api/unit-daily/plan", headers=h,
                          json={"year": YEAR, "company": n, **plan}).status_code == 200

    put = lambda body: client.put("/api/unit-daily/report", json=body, headers=h)  # noqa: E731
    # A: 100t @400 + 300t @500; B: 100t @600 → khu vực 250.000/500 = 500 (TB cộng ra 537,5).
    _price(UNIT_A, D0, 400.0)
    _price(UNIT_A, D1, 500.0)
    _price(UNIT_B, D1, 600.0)
    put({"kind": "purchase", "company": UNIT_A, "as_of": D0,
         "fields": {"latex_wet": 100, "finished": [{"grade": "SVR 3L", "qty": 5, "price": 40}]}})
    put({"kind": "purchase", "company": UNIT_A, "as_of": D1, "fields": {"latex_wet": 300}})
    put({"kind": "purchase", "company": UNIT_B, "as_of": D1, "fields": {"latex_wet": 100}})
    put({"kind": "purchase", "company": UNIT_D, "as_of": D1, "fields": {"latex_wet": 9000}})
    put({"kind": "purchase", "company": UNIT_E, "as_of": D1, "fields": {"latex_wet": 100}})
    put({"kind": "consumption", "company": UNIT_A, "as_of": D1,
         "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 800}],
                    "stock_warehoused": [{"grade": "SVR 10", "qty": 200}], "stock_material": 60}})
    put({"kind": "consumption", "company": UNIT_B, "as_of": D1,
         "fields": {"stock_warehoused": [{"grade": "SVR 3L", "qty": 50}]}})
    _deliver(h, UNIT_A, "DB-A1", D0, "SVR 10 / CSR 10", 20, 20)    # 400 triệu
    _deliver(h, UNIT_A, "DB-A2", D1, "SVR 3L", 10, 30)             # 300 triệu

    client.post("/api/users", headers=h, json={"username": "db_mem_a", "password": "pass123",
                                               "role": "member", "member_units": [UNIT_A]})
    client.post("/api/users", headers=h, json={"username": "db_lead_a", "password": "pass123",
                                               "role": "leader", "member_units": [UNIT_A]})
    client.post("/api/users", headers=h, json={"username": "db_noperm", "password": "pass123",
                                               "role": "editor"})
    yield {"admin": h, "mem": _bearer("db_mem_a", "pass123"),
           "lead": _bearer("db_lead_a", "pass123"), "noperm": _bearer("db_noperm", "pass123")}
    _cleanup(h)


def _get(h: dict, path: str, scope: str = "region", key: str | None = REGION,
         expect: int = 200, **params) -> dict:
    params = {"scope": scope, "date_from": D0, "date_to": D1, **params}
    if key is not None:
        params["key"] = key
    res = client.get(f"{API}/{path}", headers=h, params=params)
    assert res.status_code == expect, res.text
    return res.json()


def test_admin_chon_duoc_moi_pham_vi(env):
    cat = _get(env["admin"], "scopes")
    assert cat["mode"] == "group" and cat["default"] == {"scope": "group", "key": None}
    assert {"name": REGION, "units": 3} in cat["regions"]
    assert {"name": UNIT_D, "region": REGION_2} in cat["units"]
    assert {"name": REGION_2, "units": 2} in cat["regions"]
    for scope, key in (("group", None), ("region", REGION), ("unit", UNIT_D)):
        assert _get(env["admin"], "purchase", scope, key)["scope"]["scope"] == scope


def test_tai_khoan_don_vi_chi_xem_don_vi_duoc_gan(env):
    for who in ("mem", "lead"):
        cat = _get(env[who], "scopes")
        assert cat["mode"] == "unit" and cat["regions"] == []
        assert cat["units"] == [{"name": UNIT_A, "region": REGION}]
        assert cat["default"] == {"scope": "unit", "key": UNIT_A}
        assert _get(env[who], "purchase", "unit", UNIT_A)["totals"]["qty_latex"] == 400
        # Phạm vi khác đơn vị được gán — kể cả khu vực CHỨA đơn vị đó — đều bị chặn ở server.
        _get(env[who], "purchase", "unit", UNIT_B, expect=403)
        _get(env[who], "stock", "region", REGION, expect=403)
        _get(env[who], "targets", "group", None, expect=403)


def test_khong_co_quyen_unit_daily_thi_bi_chan(env):
    _get(env["noperm"], "scopes", expect=403)
    _get(env["noperm"], "purchase", expect=403)
    assert client.get(f"{API}/scopes").status_code == 401


def test_pham_vi_khong_ton_tai_hoac_thieu_ten(env):
    _get(env["admin"], "purchase", "unit", "_zz_khong_co", expect=404)
    _get(env["admin"], "purchase", "region", "_zz_khong_co", expect=404)
    _get(env["admin"], "purchase", "region", None, expect=400)


def test_thu_mua_khu_vuc_khop_bang_thong_ke_va_la_bq_gia_quyen(env):
    rep = _get(env["admin"], "purchase")
    t = rep["totals"]
    assert t["qty_latex"] == 500 and t["qty_finished"] == 5            # D ở khu vực khác → loại
    assert t["price_latex_avg"] == pytest.approx(500.0)                 # ≠ 537,5 (TB cộng)
    stats = client.get("/api/unit-daily/analytics/purchase", headers=env["admin"], params={
        "date_from": D0, "date_to": D1, "regions": REGION, "group_by": "region"}).json()
    assert t["qty_total"] == stats["totals"]["qty_total"]
    assert t["price_latex_avg"] == pytest.approx(stats["totals"]["price_latex_avg"])
    # Theo đơn vị: đúng thứ tự danh mục, đơn vị chưa có số (C) không thành cột trống.
    assert [b["label"] for b in rep["breakdown"]] == [UNIT_A, UNIT_B]
    assert rep["finished_by_grade"] == [{"grade": "SVR 3L", "qty": 5, "price_avg": 40}]
    assert rep["bucket"] == "day" and [r["as_of"] for r in rep["trend"]] == [D0, D1]


def test_ky_dai_gop_dien_bien_theo_thang(env):
    rep = _get(env["admin"], "purchase", date_from=f"{YEAR}-01-01", date_to=D1)
    assert rep["bucket"] == "month"
    # ĐỦ mọi tháng từ đầu kỳ (tháng không mua giữ ô trống, không phải 0) — trục thời gian không dồn.
    months = [r["as_of"] for r in rep["trend"]]
    assert months == [f"{YEAR}-{m:02d}" for m in range(1, int(D1[5:7]) + 1)]
    assert sum(r["qty_latex"] or 0 for r in rep["trend"]) == 500
    assert all(r["qty_latex"] is None for r in rep["trend"] if r["as_of"] not in (D0[:7], D1[:7]))


def test_dien_bien_du_moc_ngay_trong(env):
    """Ngày không giao hàng vẫn là một mốc (ô trống) — nếu bỏ, hai ngày cách nhau thành liền kề."""
    start = (date.fromisoformat(D0) - timedelta(days=2)).isoformat()
    rep = _get(env["admin"], "consumption", "unit", UNIT_A, date_from=start, date_to=D1)
    assert [r["as_of"] for r in rep["trend"]][:3] == [start, (date.fromisoformat(start)
                                                             + timedelta(days=1)).isoformat(), D0]
    assert rep["trend"][0]["qty"] is None and rep["trend"][2]["qty"] == 20


def test_tieu_thu_theo_chung_loai(env):
    rep = _get(env["admin"], "consumption", "unit", UNIT_A)
    t = rep["totals"]
    assert t["qty"] == 30 and t["qty_spot"] == 30 and t["missing_fx_lines"] == 0
    assert t["revenue_ty"] == pytest.approx(0.7)
    assert [g["grade"] for g in rep["by_grade"]] == ["SVR 10 / CSR 10", "SVR 3L"]   # SL giảm dần
    assert rep["breakdown"] == []                                    # mức đơn vị: không có chiều con


def test_ton_kho_anh_chup_ngay_chot(env):
    rep = _get(env["admin"], "stock", as_of=D1)
    t = rep["totals"]
    assert t["total"] == 1050 and t["material"] == 60
    assert rep["by_grade"] == [{"grade": "SVR 3L", "qty": 850}, {"grade": "SVR 10", "qty": 200}]
    assert rep["coverage"]["units_counted"] == 2 and rep["latest_stock_day"] is None
    # Ngày chốt không ai khai → không mượn số ngày khác, chỉ GỢI Ý ngày gần nhất có số.
    empty = _get(env["admin"], "stock", "unit", UNIT_A, as_of=(date.today()).isoformat())
    assert empty["totals"]["total"] is None and empty["latest_stock_day"] == D1


def test_dien_bien_ton_kho_chi_trong_pham_vi(env):
    rep = _get(env["admin"], "stock-series", "unit", UNIT_B, view="grade")
    day = next(r for r in rep["rows"] if r["as_of"] == D1)
    assert day["total"] == 50 and day["units_counted"] == 1          # chỉ B, không lẫn A
    # Ngày B chưa khai: không có số — không được thành cột "0 tấn" ở cách xem đã/chưa nhập kho.
    wh = _get(env["admin"], "stock-series", "unit", UNIT_B, view="warehouse")
    before = next(r for r in wh["rows"] if r["as_of"] == D0)
    assert before["total"] is None and before["values"] == {}
    _get(env["admin"], "stock-series", view="khong-co", expect=422)


def test_chi_tieu_luy_ke_tu_dau_nam(env):
    rep = _get(env["admin"], "targets")
    assert rep["date_from"] == f"{YEAR}-01-01" and rep["year"] == YEAR
    assert 0 < rep["time_pct"] <= 100
    items = {i["key"]: i for i in rep["items"]}
    # Kế hoạch thu mua gồm cả C (500 tấn, chưa mua gì) — bỏ C ra là % tự đẹp lên.
    assert items["purchase"]["plan"] == 2500 and items["purchase"]["done"] == 500
    assert items["purchase"]["pct"] == pytest.approx(20)
    assert items["sales_spot"]["pct"] == pytest.approx(30)          # 30 tấn / KH 100 tấn
    assert items["revenue"]["pct"] == pytest.approx(0.7 / 4 * 100)
    rows = {r["label"]: r for r in rep["breakdown"]}
    assert list(rows) == [UNIT_A, UNIT_B, UNIT_C]                    # khung = danh sách đơn vị
    assert rows[UNIT_C]["purchase_pct"] == 0                         # có KH, chưa làm → 0 chứ không trống
    assert rows[UNIT_B]["sales_spot_pct"] is None                    # chưa giao KH → trống
    assert rows[UNIT_A]["purchase_pct"] == pytest.approx(40)


def test_chi_tieu_don_vi_khong_co_bang_con(env):
    rep = _get(env["mem"], "targets", "unit", UNIT_A)
    assert rep["breakdown"] == []
    assert {i["key"]: i["pct"] for i in rep["items"]}["purchase"] == pytest.approx(40)


def test_don_vi_chua_giao_ke_hoach_khong_vao_tu_so(env):
    """D mua 9.000 tấn mà chưa được giao kế hoạch: cộng vào tử số thì khu vực "đạt 910%".

    % chỉ tính trên rổ đơn vị được giao (E: 100 / 1.000 = 10%), tổng cả khu vực vẫn được nói ra.
    """
    rep = _get(env["admin"], "targets", "region", REGION_2)
    item = next(i for i in rep["items"] if i["key"] == "purchase")
    assert (item["done"], item["plan"], item["units_planned"]) == (100, 1000, 1)
    assert item["pct"] == pytest.approx(10)
    assert "9.100,0 tấn" in item["note"]
    rows = {r["label"]: r for r in rep["breakdown"]}
    assert rows[UNIT_D]["purchase_pct"] is None and rows[UNIT_E]["purchase_pct"] == pytest.approx(10)
