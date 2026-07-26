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
    price_repo.upsert_record({"as_of": as_of, "source": "vrg", "grade": unit, "contract": "",
                              "price_type": price_type, "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "unit_stock_contract"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
        db.execute(text("DELETE FROM fact_price WHERE source = 'vrg' AND grade = ANY(:u)"),
                   {"u": [UNIT_A, UNIT_B]})
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

    # Tiêu thụ: 3 dòng bán (2 nguồn mủ, 2 loại HĐ, 2 hình thức) + tồn kho 2 ngày.
    put({"kind": "consumption", "company": UNIT_A, "as_of": D0,
         "fields": {"sales": [{"grade": "SVR 3L", "qty": 10, "price": 30,
                               "contract": "long_term", "channel": "export"}],
                    "sales_own": [{"grade": "SVR 10", "qty": 20, "price": 20,
                                   "contract": "spot", "channel": "domestic"}],
                    "stock_not_warehoused": [{"grade": "SVR 3L", "qty": 1000}],
                    "stock_warehoused": [{"grade": "SVR 10", "qty": 500}],
                    "stock_material": 70}})
    put({"kind": "consumption", "company": UNIT_A, "as_of": D1,
         "fields": {"sales": [{"grade": "SVR 3L", "qty": 5, "price": 1800, "ccy": "USD",
                               "contract": "long_term", "channel": "domestic"}],
                    "stock_not_warehoused": [{"grade": "SVR 3L", "qty": 800}],
                    "stock_warehoused": [], "stock_material": 60}})
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
    # Doanh thu = 10×30tr + 20×20tr = 700 triệu (dòng USD thiếu tỷ giá bị loại) → BQ = 700/30.
    assert a["revenue_ty"] == pytest.approx(0.7)
    assert a["avg_price_trieu"] == pytest.approx(700 / 30)
    assert any("thiếu tỷ giá" in w for w in rep["warnings"])

    spot = _get("consumption", seeded, contract="spot", companies=UNIT_A)
    assert _row(spot, UNIT_A)["qty"] == 20
    own = _get("consumption", seeded, source="sales_own", group_by="source", companies=UNIT_A)
    assert [r["key"] for r in own["rows"]] == ["Mủ khai thác"]
    detail = _get("consumption", seeded, group_by="none", companies=UNIT_A)
    assert detail["detail"] and len(detail["rows"]) == 3
    assert detail["rows"][0]["source_label"] in ("Mủ thu mua", "Mủ khai thác")


def _legacy_consumption(company: str, as_of: str, payload: dict) -> None:
    """Ghi thẳng payload kiểu CŨ vào DB (API hiện tại luôn tự điền loại tiền cho từng dòng)."""
    import json

    with session_scope() as db:
        db.execute(
            text("INSERT INTO unit_daily_report (as_of, company, kind, payload, updated_by, updated_at) "
                 "VALUES (CAST(:d AS date), :c, 'consumption', CAST(:p AS jsonb), 'test', now()) "
                 "ON CONFLICT (as_of, company, kind) DO UPDATE SET payload = EXCLUDED.payload"),
            {"d": as_of, "c": company, "p": json.dumps(payload)})


def test_legacy_line_uses_day_level_currency(seeded) -> None:
    """Dòng bán CŨ chưa có loại tiền riêng → lấy theo mức ngày / theo đơn vị nước ngoài (USD).

    Đọc nhầm thành VND sẽ thổi doanh thu lên 1.000 lần (1.600 USD/tấn ↦ 1.600 triệu đ/tấn).
    """
    h = seeded
    client.put(f"/api/member-units/{UNIT_B}", headers=h,
               json={"country": "LA", "currency": "LAK", "set_locale": True})
    _legacy_consumption(UNIT_B, D0, {"sales": [{"grade": "SVR 10", "qty": 10, "price": 1600}],
                                     "fx_revenue": 26000, "revenue": 10 * 1600 * 26000})
    rep = _get("consumption", h, companies=UNIT_B)
    assert _row(rep, UNIT_B)["revenue_vnd"] == pytest.approx(10 * 1600 * 26000)
    assert not rep["warnings"]      # doanh thu đã lưu khớp tổng dòng → không cảnh báo


def test_warns_when_stored_revenue_differs_from_lines(seeded) -> None:
    """Doanh thu ĐÃ LƯU lệch tổng các dòng (đổi loại tiền sau khi lưu) → phải cảnh báo, không tự sửa."""
    _legacy_consumption(UNIT_B, D1, {
        "sales": [{"grade": "SVR 10", "qty": 10, "price": 1800, "ccy": "USD", "fx": 26000}],
        "revenue": 10 * 1800 * 1_000_000})       # số cũ: cộng giá USD như VNĐ
    rep = _get("consumption", seeded, companies=UNIT_B)
    assert any("lệch" in w for w in rep["warnings"])
    assert _row(rep, UNIT_B)["revenue_vnd"] == pytest.approx(10 * 1800 * 26000)


def test_stock_is_snapshot_not_sum(seeded) -> None:
    rep = _get("stock", seeded, companies=UNIT_A)
    a = _row(rep, UNIT_A)
    # Ngày cuối kỳ có số liệu là D1: 800 tấn chưa nhập kho, khối đã nhập kho trống.
    assert a["as_of"] == D1 and a["not_warehoused"] == 800
    assert a["warehoused"] is None and a["total"] == 800      # KHÔNG cộng dồn 1000 + 800
    assert a["material"] == 60
    by_grade = _get("stock", seeded, group_by="grade", companies=UNIT_A)
    assert [r["key"] for r in by_grade["rows"]] == ["SVR 3L"]   # ngày cuối chỉ còn 1 chủng loại


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
