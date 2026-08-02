"""Test màn Thống kê số liệu đơn vị nhập (thu mua · tiêu thụ · tồn kho · tình trạng nộp).

Kiểm các quy tắc dễ sai nhất: bình quân GIA QUYỀN (không phải trung bình cộng), tồn kho lấy
THỜI ĐIỂM cuối kỳ (không cộng dồn), dòng USD thiếu tỷ giá bị loại khỏi doanh thu + có cảnh báo,
và bộ lọc theo khu vực / chủng loại / loại HĐ / hình thức / nguồn mủ.
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
UNIT_A, UNIT_B = "_zz_an_a", "_zz_an_b"
REGION = "_zz_an_region"
D0 = (date.today() - timedelta(days=3)).isoformat()
D1 = (date.today() - timedelta(days=2)).isoformat()
API = "/api/unit-daily/analytics"


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _price(unit: str, as_of: str, price_type: str, price: float) -> None:
    """Giá ĐƠN VỊ tự khai — lớp mà màn Thống kê thu mua đọc (xem test_purchase_price_layers)."""
    price_repo.upsert_record({"as_of": as_of, "source": PURCHASE_SOURCE_UNIT, "grade": unit, "contract": "",
                              "price_type": price_type, "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


def _customer(h: dict[str, str], company: str) -> int:
    """Khách hàng của đơn vị (tạo nếu chưa có) — hợp đồng mẹ bắt buộc gán khách."""
    made = client.put("/api/customers", json={"company": company, "name": f"KH {company}"},
                      headers=h).json().get("id")
    return made if made is not None else next(
        c["id"] for c in client.get("/api/customers", headers=h).json() if c["company"] == company)


def _deliver(h: dict[str, str], company: str, code: str, day: str, ctype: str, channel: str,
             grade: str, qty: float, price: float, ccy: str = "VND",
             fx: float | None = None) -> None:
    """1 hợp đồng giao-1-lần ĐÃ GIAO trong ngày `day` — nguồn tiêu thụ của cơ chế mới."""
    r = client.put("/api/sales-contracts", json={
        "company": company, "code": code, "customer_id": _customer(h, company),
        "delivery_type": "single", "contract_type": ctype, "sign_date": day, "start_date": day,
        "delivered_at": day, "channel": channel,
        "lines": [{"grade": grade, "qty": qty, "price": price, "ccy": ccy, "fx": fx}]}, headers=h)
    assert r.status_code == 200, r.text


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "unit_stock_contract",
                    "sales_contract"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
        db.execute(text("DELETE FROM unit_customer WHERE company = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
        db.execute(text("DELETE FROM fact_price WHERE grade = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
    for n in (UNIT_A, UNIT_B):
        client.delete(f"/api/member-units/{n}", headers=h)
    client.delete(f"/api/member-regions/{REGION}", headers=h)


@pytest.fixture()
def seeded():
    """2 đơn vị (A thuộc khu vực test) + số liệu 2 ngày cho cả 2 biểu."""
    h = _admin()
    _cleanup(h)
    client.post("/api/member-regions", json={"name": REGION}, headers=h)
    for n in (UNIT_A, UNIT_B):
        client.post("/api/member-units", json={"name": n}, headers=h)
    client.put(f"/api/member-units/{UNIT_A}", json={"region": REGION, "set_region": True}, headers=h)

    # Thu mua: giá mủ nước khác nhau 2 ngày → kiểm bình quân GIA QUYỀN (không phải TB cộng).
    _price(UNIT_A, D0, "purchase", 400.0)
    _price(UNIT_A, D1, "purchase", 500.0)
    put = lambda body: client.put("/api/unit-daily/report", json=body, headers=h)  # noqa: E731
    put({"kind": "purchase", "company": UNIT_A, "as_of": D0,
         "fields": {"latex_wet": 100, "coagulum": 10,
                    "finished": [{"grade": "SVR 3L", "qty": 5, "price": 40}]}})
    put({"kind": "purchase", "company": UNIT_A, "as_of": D1,
         "fields": {"latex_wet": 300, "finished": [{"grade": "SVR 10", "qty": 5, "price": 2000,
                                                    "ccy": "USD", "fx": None}]}})
    put({"kind": "purchase", "company": UNIT_B, "as_of": D1, "fields": {"no_purchase": True}})

    # Tồn kho 2 ngày (vẫn nhập tay theo ngày).
    put({"kind": "consumption", "company": UNIT_A, "as_of": D0,
         "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 1000}],
                    "stock_warehoused": [{"grade": "SVR 10", "qty": 500}],
                    "stock_material": 70}})
    put({"kind": "consumption", "company": UNIT_A, "as_of": D1,
         "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 800}],
                    "stock_warehoused": [], "stock_material": 60}})
    # Tiêu thụ = 3 LẦN GIAO của hợp đồng (2 loại HĐ, 2 hình thức) — từ 02/08/2026 không còn
    # nhập tay ở biểu ngày nữa.
    _deliver(h, UNIT_A, "HD-A1", D0, "long_term", "export", "SVR 3L", 10, 30)
    _deliver(h, UNIT_A, "HD-A2", D0, "spot", "domestic", "SVR 10 / CSR 10", 20, 20)
    _deliver(h, UNIT_A, "HD-A3", D1, "long_term", "domestic", "SVR 3L", 5, 1800,
             ccy="USD", fx=26000)
    yield h
    _cleanup(h)


def _get(path: str, h: dict, **params) -> dict:
    params.setdefault("date_from", D0)
    params.setdefault("date_to", D1)
    res = client.get(f"{API}/{path}", headers=h, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _row(rep: dict, key: str) -> dict:
    return next(r for r in rep["rows"] if r["key"] == key)


def test_purchase_totals_and_weighted_average(seeded) -> None:
    rep = _get("purchase", seeded, companies=f"{UNIT_A},{UNIT_B}")
    a = _row(rep, UNIT_A)
    assert a["qty_latex"] == 400 and a["qty_cup"] == 10 and a["qty_finished"] == 10
    assert a["qty_total"] == 420                      # tổng theo bộ lọc = cả 3 loại mủ
    # BQ gia quyền: (400×100 + 500×300) / 400 = 475 đ/độ — TB cộng sẽ ra 450 (sai).
    assert a["price_latex_avg"] == pytest.approx(475)
    # Thành phẩm: dòng USD thiếu tỷ giá bị loại → chỉ còn 5 tấn × 40 triệu = 40 triệu đ/tấn.
    assert a["price_finished_avg"] == pytest.approx(40)
    assert any("thiếu tỷ giá" in w for w in rep["warnings"])
    # Đơn vị B chỉ bật cờ "không tổ chức thu mua" → không có sản lượng nhưng vẫn được đếm ngày.
    assert _row(rep, UNIT_B)["no_purchase_days"] == 1
    assert rep["totals"]["qty_total"] == 420


def test_purchase_filters(seeded) -> None:
    only_latex = _get("purchase", seeded, materials="latex", companies=UNIT_A)
    a = _row(only_latex, UNIT_A)
    assert a["qty_latex"] == 400 and a["qty_cup"] is None and a["qty_total"] == 400

    by_region = _get("purchase", seeded, regions=REGION, group_by="region")
    assert [r["key"] for r in by_region["rows"]] == [REGION]     # đơn vị B ngoài khu vực → loại

    by_grade = _get("purchase", seeded, grades="SVR 3L", group_by="grade")
    assert [r["key"] for r in by_grade["rows"]] == ["SVR 3L"]
    assert by_grade["rows"][0]["qty_finished"] == 5              # chỉ áp cho mủ thành phẩm


def test_consumption_filters_and_avg_price(seeded) -> None:
    rep = _get("consumption", seeded, companies=UNIT_A)
    a = _row(rep, UNIT_A)
    assert a["qty"] == 35 and a["qty_long_term"] == 15 and a["qty_spot"] == 20
    assert a["qty_export"] == 10 and a["qty_domestic"] == 25
    # Doanh thu = 10×30tr + 20×20tr + 5×1800USD×26.000 = 934 triệu → BQ = 934/35.
    assert a["revenue_ty"] == pytest.approx(0.934)
    assert a["avg_price_trieu"] == pytest.approx(934 / 35)

    spot = _get("consumption", seeded, contract="spot", companies=UNIT_A)
    assert _row(spot, UNIT_A)["qty"] == 20
    detail = _get("consumption", seeded, group_by="none", companies=UNIT_A)
    assert detail["detail"] and len(detail["rows"]) == 3
    assert {r["contract_label"] for r in detail["rows"]} == {"HĐ dài hạn", "HĐ chuyến"}


def test_delivery_missing_fx_is_excluded_and_warned(seeded) -> None:
    """Lần giao ngoại tệ THIẾU tỷ giá (bản ghi chuyển từ cơ chế cũ) → không tính doanh thu + cảnh báo.

    Form chặn lưu USD thiếu tỷ giá nên ca này chỉ đến từ script chuyển đổi → ghi thẳng vào DB.
    """
    h = seeded
    with session_scope() as db:
        db.execute(text("UPDATE sales_contract SET lines = jsonb_set(lines, '{0,fx}', 'null') "
                        " WHERE code = 'HD-A3'"))
    a = _row(_get("consumption", h, companies=UNIT_A), UNIT_A)
    assert a["qty"] == 35                                  # sản lượng vẫn đếm đủ
    assert a["revenue_ty"] == pytest.approx(0.7)           # chỉ 2 dòng VNĐ có doanh thu
    assert a["avg_price_trieu"] == pytest.approx(700 / 30)  # BQ bỏ sản lượng thiếu tỷ giá
    assert any("thiếu tỷ giá" in w
               for w in _get("consumption", h, companies=UNIT_A)["warnings"])


def test_internal_channel_is_not_counted_as_domestic(seeded) -> None:
    """Tiêu thụ NỘI BỘ là hình thức riêng — gộp vào "trong nước" là sai chỉ tiêu báo cáo."""
    h = seeded
    # Nội bộ chỉ bán được trong nhóm mẹ–con → cho B làm công ty con của A.
    client.put(f"/api/member-units/{UNIT_B}", headers=h,
               json={"set_parent": True, "parent_company": UNIT_A})
    client.put("/api/customers", json={"company": UNIT_B, "name": f"KH {UNIT_B}"}, headers=h)
    cus = next(c["id"] for c in client.get("/api/customers", headers=h).json()
               if c["company"] == UNIT_B)
    r = client.put("/api/sales-contracts", json={
        "company": UNIT_B, "code": "HD-INT", "customer_id": cus, "delivery_type": "single",
        "contract_type": "spot", "sign_date": D0, "start_date": D0, "delivered_at": D0,
        "channel": "internal", "to_company": UNIT_A,
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 7, "price": 25, "ccy": "VND"}]}, headers=h)
    assert r.status_code == 200, r.text

    b = _row(_get("consumption", h, companies=UNIT_B), UNIT_B)
    assert b["qty"] == 7 and b["qty_internal"] == 7
    assert not b["qty_domestic"] and not b["qty_export"]


def test_contract_without_type_goes_to_its_own_bucket(seeded) -> None:
    """HĐ chuyển từ cơ chế cũ chưa khai loại → ô riêng, KHÔNG dồn vào dài hạn hay chuyến."""
    h = seeded
    with session_scope() as db:      # chỉ bản ghi chuyển đổi mới thiếu loại (form ép nhập)
        db.execute(text("UPDATE sales_contract SET contract_type = NULL WHERE code = 'HD-A2'"))
    a = _row(_get("consumption", h, companies=UNIT_A), UNIT_A)
    assert a["qty"] == 35 and a["qty_spot"] is None and a["qty_unknown_type"] == 20


def test_stock_is_snapshot_not_sum(seeded) -> None:
    rep = _get("stock", seeded, companies=UNIT_A)
    a = _row(rep, UNIT_A)
    # Ngày cuối kỳ có số liệu là D1: 800 tấn chưa nhập kho, khối đã nhập kho trống.
    assert a["as_of"] == D1 and a["not_warehoused"] == 800
    assert a["warehoused"] is None and a["total"] == 800      # KHÔNG cộng dồn 1000 + 800
    assert a["material"] == 60
    by_grade = _get("stock", seeded, group_by="grade", companies=UNIT_A)
    assert [r["key"] for r in by_grade["rows"]] == ["SVR 3L"]   # ngày cuối chỉ còn 1 chủng loại


def test_stock_by_day_keeps_each_day_separate(seeded) -> None:
    """Drill xuống NGÀY: mỗi ngày là ảnh chụp riêng; Tổng cộng lấy ngày cuối, KHÔNG cộng dồn."""
    rep = _get("stock", seeded, companies=UNIT_A, group_by="day")
    assert [r["key"] for r in rep["rows"]] == [D0, D1]
    assert _row(rep, D0)["total"] == 1500      # 1000 chưa nhập kho + 500 đã nhập kho
    assert _row(rep, D1)["total"] == 800
    assert rep["totals"]["total"] == 800       # ngày cuối, không phải 2300
    assert any("không cộng dồn" in w for w in rep["warnings"])


def test_drill_region_then_company(seeded) -> None:
    """Chuỗi drill: khu vực → đơn vị → ngày cho ra đúng số của nhánh đang mở."""
    by_region = _get("purchase", seeded, regions=REGION, group_by="region")
    assert _row(by_region, REGION)["qty_total"] == 420
    by_company = _get("purchase", seeded, regions=REGION, group_by="company")
    assert _row(by_company, UNIT_A)["qty_total"] == 420
    by_day = _get("purchase", seeded, companies=UNIT_A, group_by="day")
    assert [r["key"] for r in by_day["rows"]] == [D0, D1]
    assert _row(by_day, D0)["qty_total"] == 115      # 100 nước + 10 chén + 5 thành phẩm
    assert _row(by_day, D1)["qty_total"] == 305


def test_status_matrix(seeded) -> None:
    rep = _get("status", seeded, kind="purchase", companies=f"{UNIT_A},{UNIT_B}")
    assert rep["dates"] == [D0, D1]
    a = next(r for r in rep["rows"] if r["company"] == UNIT_A)
    b = next(r for r in rep["rows"] if r["company"] == UNIT_B)
    assert a["cells"][D0] == "ok" and a["filled"] == 2 and a["missing"] == 0
    assert b["cells"][D0] == "none" and b["cells"][D1] == "no_purchase"
    assert b["missing"] == 1 and rep["totals"]["expected"] == 4


def test_range_validation_and_xlsx(seeded) -> None:
    bad = client.get(f"{API}/purchase", headers=seeded, params={"date_from": D1, "date_to": D0})
    assert bad.status_code == 400
    xlsx = client.get(f"{API}/purchase.xlsx", headers=seeded,
                      params={"date_from": D0, "date_to": D1})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"


def test_requires_unit_daily_cap(seeded) -> None:
    h = seeded
    client.delete("/api/users/an_noperm", headers=h)
    client.post("/api/users", json={"username": "an_noperm", "password": "pass123",
                                    "role": "editor"}, headers=h)
    tok = client.post("/api/auth/login", json={"username": "an_noperm", "password": "pass123"}).json()
    nh = {"Authorization": f"Bearer {tok['access_token']}"}
    res = client.get(f"{API}/purchase", headers=nh, params={"date_from": D0, "date_to": D1})
    assert res.status_code == 403
    client.delete("/api/users/an_noperm", headers=h)
