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
        "delivered_at": day, "channel": "domestic", "source": "exploit",
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
    assert t["qty"] == 30 and t["qty_spot"] == 30 and t["no_revenue_lines"] == 0
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

    % chỉ tính trên rổ đơn vị được giao (E: 100 / 1.000 = 10%), tổng cả khu vực trả ở `scope_done`.
    """
    rep = _get(env["admin"], "targets", "region", REGION_2)
    item = next(i for i in rep["items"] if i["key"] == "purchase")
    assert (item["done"], item["plan"], item["units_planned"]) == (100, 1000, 1)
    assert item["pct"] == pytest.approx(10)
    assert item["scope_done"] == pytest.approx(9100)
    rows = {r["label"]: r for r in rep["breakdown"]}
    assert rows[UNIT_D]["purchase_pct"] is None and rows[UNIT_E]["purchase_pct"] == pytest.approx(10)


def test_lan_giao_thieu_don_gia_thi_de_trong_phan_tram_doanh_thu(env):
    """Giống Báo cáo tổng hợp: lần giao chưa tính được doanh thu (thiếu tỷ giá HOẶC đơn giá) thì
    doanh thu đang thiếu → % kế hoạch doanh thu để trống, không báo một tỷ lệ thấp hơn thực tế."""
    r = client.put("/api/sales-contracts", headers=env["admin"], json={
        "company": UNIT_A, "code": "DB-A3", "customer_id": _customer(env["admin"], UNIT_A),
        "delivery_type": "single", "contract_type": "spot", "sign_date": D1, "start_date": D1,
        "delivered_at": D1, "channel": "domestic", "source": "exploit",
        "lines": [{"grade": "SVR 3L", "qty": 5, "price": None, "ccy": "VND"}]})
    assert r.status_code == 200, r.text
    con = _get(env["admin"], "consumption", "unit", UNIT_A)
    assert con["totals"]["no_revenue_lines"] == 1
    assert any("chưa có đơn giá" in w for w in con["warnings"])
    rev = next(i for i in _get(env["admin"], "targets", "unit", UNIT_A)["items"]
               if i["key"] == "revenue")
    assert rev["pct"] is None and "đơn giá" in rev["note"]


def test_don_gia_sai_don_vi_tinh_thi_canh_bao_va_de_trong_phan_tram_doanh_thu(env):
    """Phản hồi 26/09/2026: một đợt giao nhập 56.200 (đồng/kg) vào ô triệu đ/tấn đẩy doanh thu cả
    Tập đoàn lên 129%. Dashboard phải nêu tên đơn vị, để trống % doanh thu (cả dòng khu vực chứa
    đơn vị đó) và vẫn cho biết tổng cả phạm vi qua `scope_done`."""
    _deliver(env["admin"], UNIT_A, "DB-A9", D1, "SVR 3L", 1, 56200)
    con = _get(env["admin"], "consumption", "unit", UNIT_A)
    assert con["totals"]["bad_price_lines"] == 1
    assert any("triệu đ/tấn" in w and UNIT_A in w for w in con["warnings"])   # trần: cấu hình admin
    rev = next(i for i in _get(env["admin"], "targets", "unit", UNIT_A)["items"]
               if i["key"] == "revenue")
    assert rev["pct"] is None and UNIT_A in rev["note"] and "sai đơn vị tính" in rev["note"]
    assert rev["scope_done"] == pytest.approx(0.7 + 56.2)
    region = _get(env["admin"], "targets")
    assert next(i for i in region["items"] if i["key"] == "revenue")["pct"] is None
    assert {r["label"]: r for r in region["breakdown"]}[UNIT_A]["revenue_pct"] is None
    # Dòng giá đúng (40 triệu đ/tấn) không bị nêu oan.
    assert _get(env["admin"], "consumption", "unit", UNIT_B)["totals"]["bad_price_lines"] == 0


def test_ngay_sai_dinh_dang_va_ky_qua_dai_bi_tu_choi(env):
    _get(env["admin"], "purchase", date_to="20260805", expect=422)      # không đoán định dạng
    _get(env["admin"], "stock", as_of="2026-W01-1", expect=422)
    _get(env["admin"], "purchase", date_from="2000-01-01", expect=400)  # kỳ dài hơn 3 năm


def test_don_vi_co_ke_hoach_ngoai_khung_van_co_dong_tien_do(env):
    """Đơn vị có kế hoạch nhưng chưa gán khu vực: tổng Tập đoàn có phần của họ → bảng phải có dòng."""
    h = env["admin"]
    client.post("/api/member-units", json={"name": "_zz_db_f"}, headers=h)
    try:
        client.put("/api/unit-daily/plan", headers=h,
                   json={"year": YEAR, "company": "_zz_db_f", "plan_tonnes": 700})
        rep = _get(h, "targets", "group", None)
        rows = {r["label"]: r for r in rep["breakdown"]}
        assert "(Chưa gán khu vực)" in rows and rows["(Chưa gán khu vực)"]["purchase_pct"] is not None
    finally:
        with session_scope() as db:
            db.execute(text("DELETE FROM unit_purchase_plan WHERE company = '_zz_db_f'"))
        client.delete("/api/member-units/_zz_db_f", headers=h)


# ── Rà chéo 29/09/2026 — nhánh tồn kho (A1 · A2 · A6 · C2) ─────────────────────
def _stock_day(h: dict, company: str, day: str, fields: dict) -> None:
    r = client.put("/api/unit-daily/report", headers=h,
                   json={"kind": "consumption", "company": company, "as_of": day, "fields": fields})
    assert r.status_code == 200, r.text


def test_ngay_chot_tu_dong_la_ngay_cuoi_du_do_phu_cua_bieu_do(env):
    """A1: để "Tự động" thì KHÔNG lấy hôm nay (đơn vị được nhập tới 11:00 hôm sau → sáng nào KPI
    cũng tụt) mà lấy ngày cuối của biểu đồ diễn biến — cùng luật cắt đuôi chưa đủ đơn vị khai."""
    h, today = env["admin"], date.today().isoformat()
    _stock_day(h, UNIT_A, today, {"stock_warehoused": [{"grade": "SVR 10", "qty": 5}]})  # 1/2 đơn vị
    auto = _get(h, "stock", date_to=today)
    series = _get(h, "stock-series", date_to=today, view="warehouse")
    assert auto["auto_as_of"] is True and auto["as_of"] == D1 == series["rows"][-1]["as_of"]
    assert auto["totals"]["total"] == 1050 and auto["coverage"]["units_counted"] == 2
    # Chọn tay thì giữ đúng ngày đã chọn, kể cả khi ngày đó mới 1 đơn vị khai.
    picked = _get(h, "stock", date_to=today, as_of=today)
    assert picked["auto_as_of"] is False and picked["as_of"] == today
    assert picked["totals"]["total"] == 5
    # Một đơn vị: ngày khai gần nhất của chính nó.
    assert _get(h, "stock", "unit", UNIT_A, date_to=today)["as_of"] == today


def test_da_ky_chua_giao_gom_hop_dong_cua_don_vi_da_sap_nhap(env):
    """A2: đơn vị cũ thôi khai tồn sau sáp nhập nên hợp đồng dở của họ từng rơi mất khỏi "Đã ký HĐ
    chưa giao" của đơn vị nhận (Lộc Ninh 28/09/2026 thiếu 196,9 t của Bình Long)."""
    from app.services import member_unit_merge

    h = env["admin"]
    r = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT_C, "code": "DB-C1", "customer_id": _customer(h, UNIT_C),
        "delivery_type": "single", "contract_type": "spot", "sign_date": D0, "start_date": D0,
        "channel": "domestic", "lines": [{"grade": "SVR 3L", "qty": 120, "price": 40, "ccy": "VND"}]})
    assert r.status_code == 200, r.text
    member_unit_merge.merge(UNIT_C, UNIT_A, D0)
    try:
        t = _get(h, "stock", "unit", UNIT_A, as_of=D1)["totals"]
        assert t["signed_undelivered"] == 120 and t["tradable"] == 1000 - 120
        region = _get(h, "stock", as_of=D1)
        assert {b["label"]: b for b in region["breakdown"]}[UNIT_A]["signed_undelivered"] == 120
        # Xem TÁCH: hợp đồng của đơn vị cũ không cộng vào đơn vị nhận.
        split = client.get("/api/unit-daily/analytics/stock", headers=h, params={
            "as_of": D1, "companies": UNIT_A, "group_by": "company", "split_merged": True}).json()
        assert split["totals"]["signed_undelivered"] == 0
    finally:
        member_unit_merge.unmerge(UNIT_C)


def test_khai_0_hien_0_con_chua_khai_moi_la_trong(env):
    """C2: khối ĐÃ KHAI bằng 0 phải hiện 0 — trang ghi "— là chưa có số"; khối không khai → None."""
    h = env["admin"]
    _stock_day(h, UNIT_C, D1, {"stock_warehoused": [{"grade": "SVR 10", "qty": 0}],
                               "stock_material": 0})
    rows = {b["label"]: b for b in _get(h, "stock", as_of=D1)["breakdown"]}
    assert (rows[UNIT_C]["total"], rows[UNIT_C]["material"], rows[UNIT_C]["tradable"]) == (0, 0, 0)
    assert rows[UNIT_C]["signed_undelivered"] == 0
    assert rows[UNIT_B]["material"] is None                        # B không khai tồn nguyên liệu
    b = next(r for r in client.get("/api/unit-daily/analytics/stock", headers=h, params={
        "as_of": D1, "companies": UNIT_B, "group_by": "company"}).json()["rows"])
    assert b["not_warehoused"] is None and b["warehoused"] == 50   # khối trống = chưa khai


def test_so_giu_theo_khong_phat_sinh_hien_ngay_khai_that(env):
    """A6: số giữ theo cờ "không phát sinh" phải mang NGÀY KHAI thật + số ngày cũ, không phải ngày
    chốt (Dầu Tiếng Lai Châu 28/09/2026 dùng số khai 30/08 mà vẫn hiện "28/09")."""
    h = env["admin"]
    _stock_day(h, UNIT_E, D0, {"stock_warehoused": [{"grade": "SVR 10", "qty": 70}]})
    _stock_day(h, UNIT_E, D1, {"no_stock": True})
    unit = _get(h, "stock", "unit", UNIT_E, as_of=D1)
    assert unit["totals"]["total"] == 70
    assert unit["totals"]["dates"] == [D0] and unit["totals"]["age_days"] == 1
    region = _get(h, "stock", "region", REGION_2, as_of=D1)
    assert {b["label"]: b for b in region["breakdown"]}[UNIT_E]["as_of"] == D0
    assert region["coverage"]["stale"] == [{"company": UNIT_E, "as_of": D0, "age_days": 1}]
