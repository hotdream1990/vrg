"""Trợ lý AI · kế hoạch năm & thu mua — phải ra ĐÚNG số của Dashboard đơn vị (rà chéo 29/09/2026).

Khoá lại 3 lỗi đã đo trên bản sao prod:
1. % KH thu mua theo đơn vị lấy từ hàm vẽ biểu đồ (giữ 8 nhóm lớn, còn lại dồn "Khác", không gộp
   đơn vị sáp nhập) → đơn vị nhỏ bị 0% (Phú Thịnh 0% thay vì 52,7%).
2. % doanh thu = doanh thu CẢ Tập đoàn ÷ kế hoạch của riêng các đơn vị có kế hoạch → 213% (80,6%).
3. Giá thu mua "bình quân" là trung bình cộng giá các đơn vị, không phải BQ gia quyền theo sản lượng.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import edit_window
from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_UNIT
from app.main import app
from app.services import member_region_repo, member_unit_merge, member_unit_repo, price_repo, user_repo
from app.services import unit_daily_repo as udr
from app.services import unit_dashboard_scope as scope_svc
from app.services import unit_dashboard_targets as targets_svc
from app.services import unit_report_purchase as pur
from app.services.assistant_tools import unit_plan_progress as upp
from app.services.assistant_tools import unit_tools as ut

client = TestClient(app)
TODAY = edit_window.today()
YEAR = TODAY.year
BIG = [f"_zz_ap_big{i}" for i in range(9)]            # 9 đơn vị lớn → đẩy đơn vị nhỏ ra ngoài top 8
SMALL, OLD, NEW, NOPLAN, PRICED = "_zz_ap_small", "_zz_ap_old", "_zz_ap_new", "_zz_ap_noplan", "_zz_ap_px"
UNITS = [*BIG, SMALL, OLD, NEW, NOPLAN, PRICED]
REGION = "_zz_ap_region"
D_BEFORE, D_MERGE, D_AFTER = (TODAY - timedelta(days=n) for n in (20, 10, 3))
D0, D1 = (TODAY - timedelta(days=n) for n in (3, 2))

pytestmark = [
    pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng"),
    # Các mốc ngày phải cùng năm với kế hoạch.
    pytest.mark.skipif(TODAY.timetuple().tm_yday <= 21, reason="đầu năm — mốc ngày rơi sang năm trước"),
]


def _iso(d: date) -> str:
    return d.isoformat()


def _cleanup() -> None:
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "sales_contract", "master_contract",
                    "unit_customer"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM fact_price WHERE grade = ANY(:u)"), {"u": UNITS})
        db.execute(text("UPDATE member_unit SET merged_into = NULL, merged_at = NULL "
                        "WHERE merged_into = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM member_unit WHERE name = ANY(:u)"), {"u": UNITS})
    member_region_repo.delete_region(REGION)


def _admin() -> dict[str, str]:
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _customer(h: dict[str, str], company: str) -> int:
    made = client.put("/api/customers", json={"company": company, "name": f"KH {company}"},
                      headers=h).json().get("id")
    return made if made is not None else next(
        c["id"] for c in client.get(f"/api/customers?company={company}", headers=h).json()["items"]
        if c["company"] == company)


def _deliver(h: dict[str, str], company: str, code: str, qty: float, price: float | None) -> None:
    """1 HĐ chuyến giao-1-lần đã giao (giá VND theo triệu đ/tấn; None = chưa có đơn giá)."""
    r = client.put("/api/sales-contracts", headers=h, json={
        "company": company, "code": code, "customer_id": _customer(h, company),
        "delivery_type": "single",
        "contract_type": "spot", "sign_date": _iso(D1), "start_date": _iso(D1),
        "delivered_at": _iso(D1), "channel": "domestic", "source": "exploit",
        "lines": [{"grade": "SVR 3L", "qty": qty, "price": price, "ccy": "VND"}]})
    assert r.status_code == 200, r.text


def _plan(company: str, tonnes: float | None, revenue_ty: float | None = None) -> None:
    udr.set_year_plan(YEAR, company, tonnes, None, None, None, None, revenue_ty, "test")


def _buy(company: str, day: date, qty: float) -> None:
    udr.upsert("purchase", _iso(day), company, {"latex_wet": qty}, "test")


def _px(company: str, day: date, price: float) -> None:
    price_repo.upsert_record({"as_of": _iso(day), "source": PURCHASE_SOURCE_UNIT, "grade": company,
                              "contract": "", "price_type": "purchase", "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


@pytest.fixture()
def env():
    """9 đơn vị lớn (100 t / KH 1.000 t) · SMALL 1 t / KH 10 t · OLD (50 t, KH 100 t) sáp nhập vào
    NEW (20 t, KH 200 t) · NOPLAN mua 500 t và bán 2 tỷ nhưng CHƯA giao kế hoạch nào ·
    NEW có KH doanh thu 1 tỷ, bán 0,5 tỷ."""
    _cleanup()
    h = _admin()
    member_region_repo.add_region(REGION)
    for n in UNITS:
        member_unit_repo.add_unit(n)
        member_unit_repo.set_region(n, REGION)
    for n in BIG:
        _plan(n, 1000)
        _buy(n, D_AFTER, 100)
    _plan(SMALL, 10)
    _buy(SMALL, D_AFTER, 1)
    _plan(OLD, 100)
    _buy(OLD, D_BEFORE, 50)
    member_unit_merge.merge(OLD, NEW, _iso(D_MERGE))
    _plan(NEW, 200, revenue_ty=1)
    _buy(NEW, D_AFTER, 20)
    _buy(NOPLAN, D_AFTER, 500)
    _deliver(h, NEW, "AP-NEW", 10, 50)          # 500 triệu = 0,5 tỷ
    _deliver(h, NOPLAN, "AP-NOPLAN", 40, 50)    # 2 tỷ — KHÔNG được vào tử số % doanh thu
    yield h
    _cleanup()


def _dash_items(scope: str = "group", key: str | None = None) -> dict[str, dict]:
    b = targets_svc.targets_block(scope_svc.resolve(scope, key, None), _iso(TODAY), _iso(TODAY))
    return {i["key"]: i for i in b["items"]}


def test_pct_ke_hoach_tung_don_vi_khop_dashboard_ke_ca_don_vi_nho(env):
    rows = {r["nhom"]: r for r in upp.run({"group_by": "company"})["summary"]["cac_nhom"]}
    assert "Khác" not in rows, "không được dồn đơn vị ngoài top vào nhóm 'Khác'"
    assert rows[SMALL]["thuc_hien_tan"] == 1 and rows[SMALL]["pct_thuc_hien"] == pytest.approx(10)
    # Đơn vị nhận sáp nhập: cả sản lượng lẫn kế hoạch của đơn vị cũ cộng vào — không có dòng OLD.
    assert OLD not in rows
    assert (rows[NEW]["ke_hoach_tan"], rows[NEW]["thuc_hien_tan"]) == (300, 70)
    # Chưa giao kế hoạch: vẫn hiện sản lượng, % để trống (không ghi 0%).
    assert rows[NOPLAN]["thuc_hien_tan"] == 500 and rows[NOPLAN]["pct_thuc_hien"] is None
    for c in (SMALL, NEW, BIG[0]):
        assert rows[c]["pct_thuc_hien"] == pytest.approx(round(_dash_items("unit", c)["purchase"]["pct"], 1))


def test_pct_ke_hoach_khu_vuc_theo_ro_don_vi_duoc_giao(env):
    rows = {r["nhom"]: r for r in upp.run({"group_by": "region"})["summary"]["cac_nhom"]}
    r = rows[REGION]
    assert r["ke_hoach_tan"] == 9000 + 10 + 300
    assert r["thuc_hien_tan"] == 900 + 1 + 70          # NOPLAN không vào tử số…
    assert r["ngoai_ro_tan"] == 500                     # …nhưng vẫn được nói ra riêng
    dash = targets_svc.targets_block(scope_svc.resolve("group", None, None), _iso(TODAY), _iso(TODAY))
    pct = next(b["purchase_pct"] for b in dash["breakdown"] if b["label"] == REGION)
    assert r["pct_thuc_hien"] == pytest.approx(round(pct, 1))


def test_pct_doanh_thu_tu_va_mau_cung_ro_nhu_dashboard(env):
    s = upp.run({})["summary"]
    rev, dash = s["doanh_thu"], _dash_items()
    assert rev["pct_thuc_hien"] == pytest.approx(round(dash["revenue"]["pct"], 1))
    assert rev["thuc_hien_trong_ro"] == pytest.approx(round(dash["revenue"]["done"], 2))
    # 2 tỷ của đơn vị chưa giao kế hoạch chỉ nằm ở tổng cả Tập đoàn, không vào tử số.
    assert rev["thuc_hien_ca_tap_doan"] - rev["thuc_hien_trong_ro"] >= 2 - 0.011
    assert s["san_luong_thu_mua"]["pct_thuc_hien"] == pytest.approx(
        round(dash["purchase"]["pct"], 1))


def test_pct_doanh_thu_de_trong_khi_lan_giao_thieu_don_gia(env):
    _deliver(env, NEW, "AP-NEW-2", 5, None)
    rev = upp.run({})["summary"]["doanh_thu"]
    assert rev["pct_thuc_hien"] is None and "đơn giá" in rev["ghi_chu"]


def test_gia_thu_mua_la_binh_quan_gia_quyen(env):
    """PRICED: 100 t @400 + 300 t @500 → BQ gia quyền 475 (trung bình cộng ra 450)."""
    _buy(PRICED, D0, 100)
    _buy(PRICED, D1, 300)
    _px(PRICED, D0, 400)
    _px(PRICED, D1, 500)
    one = ut._unit_purchase({"date_from": _iso(D0), "date_to": _iso(D1), "company": PRICED})
    assert one["summary"]["don_gia_binh_quan"] == pytest.approx(475)
    grp = ut._unit_purchase({"date_from": _iso(D0), "date_to": _iso(D1)})["summary"]
    want = pur.purchase_report(_iso(D0), _iso(D1), group_by="region")["totals"]["price_latex_avg"]
    assert grp["don_gia_thu_mua"]["avg"] == pytest.approx(round(want, 1))
