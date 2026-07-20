"""Test báo cáo tiêu thụ–tồn kho theo ngày (member + chuyên viên có quyền `unit_daily`) + cửa sổ sửa ngày."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(username: str, password: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin() -> dict[str, str]:
    return _bearer("admin", "admin")


def _cleanup(h: dict[str, str], users: list[str], units: list[str]) -> None:
    """Dọn sạch dữ liệu test — không để lại tài khoản/đơn vị `_zz_*` trong DB dev."""
    from sqlalchemy import text

    from app.core.db import session_scope
    for u in users:
        client.delete(f"/api/users/{u}", headers=h)
    with session_scope() as db:
        for tbl, col in (("unit_daily_report", "company"), ("unit_purchase_plan", "company")):
            db.execute(text(f"DELETE FROM {tbl} WHERE {col} = ANY(:u)"), {"u": units})
        db.execute(text("DELETE FROM fact_price WHERE source = 'vrg' AND grade = ANY(:u)"), {"u": units})
    for n in units:
        client.delete(f"/api/member-units/{n}", headers=h)


def test_unit_daily_member_and_editor_flow() -> None:
    h = _admin()
    unit = "_zz_ud_unit"
    today = date.today().isoformat()
    for u in ("ud_mem", "ud_ed", "ud_noed"):
        client.delete(f"/api/users/{u}", headers=h)

    client.post("/api/member-units", json={"name": unit}, headers=h)
    assert client.post("/api/users", json={"username": "ud_mem", "password": "pass123",
                                           "role": "member", "member_units": [unit]}, headers=h).status_code == 200
    client.post("/api/users", json={"username": "ud_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily"]}, headers=h)
    client.post("/api/users", json={"username": "ud_noed", "password": "pass123", "role": "editor"}, headers=h)
    mh, eh, nh = _bearer("ud_mem", "pass123"), _bearer("ud_ed", "pass123"), _bearer("ud_noed", "pass123")

    # Member ghi số liệu thu mua hôm nay (key rác 'bad' bị loại).
    body = {"kind": "purchase", "company": unit, "as_of": today,
            "fields": {"latex_wet": 120.5, "coagulum": 30, "cum_purchase": 800, "bad": 9}}
    assert client.put("/api/member/daily-report", json=body, headers=mh).status_code == 200
    g = client.get(f"/api/member/daily-report?kind=purchase&as_of={today}", headers=mh)
    assert g.status_code == 200 and g.json()["units"] == [unit]
    saved = g.json()["entries"][unit]["fields"]
    assert saved["latex_wet"] == 120.5 and "bad" not in saved

    # Member không được đụng đơn vị khác.
    bad = {"kind": "purchase", "company": "khac", "as_of": today, "fields": {"latex_wet": 1}}
    assert client.put("/api/member/daily-report", json=bad, headers=mh).status_code == 403

    # create_only chống ghi trùng (đã có số → 409).
    dup = {**body, "create_only": True}
    assert client.put("/api/member/daily-report", json=dup, headers=mh).status_code == 409

    # Chuyên viên có quyền: xem lưới cả ngày + đặt SỐ LIỆU NĂM (kế hoạch thu mua + HĐ dài hạn đã ký).
    dy = client.get(f"/api/unit-daily/day?kind=purchase&as_of={today}", headers=eh)
    assert dy.status_code == 200 and unit in dy.json()["entries"]
    assert client.put("/api/unit-daily/plan",
                      json={"year": date.today().year, "company": unit, "plan_tonnes": 2000,
                            "signed_lt_tonnes": 1500, "carry_lt_tonnes": 40, "carry_spot_tonnes": 15},
                      headers=eh).status_code == 200
    pl = client.get(f"/api/unit-daily/plan?year={date.today().year}", headers=eh)
    assert pl.json()["plans"][unit] == {"plan_tonnes": 2000, "signed_lt_tonnes": 1500,
                                        "carry_lt_tonnes": 40, "carry_spot_tonnes": 15}

    # Đơn vị thành viên tự cập nhật số liệu năm của mình; không đụng được đơn vị khác.
    assert client.put("/api/member/plan",
                      json={"year": date.today().year, "company": unit, "plan_tonnes": 2500},
                      headers=mh).status_code == 200
    mp = client.get(f"/api/member/plan?year={date.today().year}", headers=mh)
    assert mp.status_code == 200 and mp.json()["plans"][unit]["plan_tonnes"] == 2500
    assert client.put("/api/member/plan",
                      json={"year": date.today().year, "company": "Đơn vị khác", "plan_tonnes": 1},
                      headers=mh).status_code == 403

    # Chuyên viên sửa số của đơn vị (consumption) + timeline hiện bản ghi.
    # Biểu tiêu thụ dùng BẢNG NHIỀU DÒNG: `sales` + tồn kho dạng mảng. Tồn kho tính bằng TẤN
    # và KHÔNG còn "loại bành"; giá bán chọn loại tiền qua `sales_ccy`.
    cons = {"kind": "consumption", "company": unit, "as_of": today, "fields": {
        "sales": [{"contract": "long_term", "channel": "export", "grade": "RSS",
                   "qty": 12.5, "price": 45}],
        "sales_ccy": "VND", "stock_ccy": "VND",
        "revenue": 562_500_000,
        "stock_no_contract": [{"grade": "RSS", "bale": "bỏ đi", "qty": 24}],
        "stock_material": 3.5,
    }}
    assert client.put("/api/unit-daily/report", json=cons, headers=eh).status_code == 200
    tl = client.get("/api/unit-daily/timeline?kind=consumption&days=30", headers=eh)
    saved = next(e for e in tl.json()["entries"] if e["company"] == unit)["fields"]
    assert saved["sales"][0]["qty"] == 12.5
    assert saved["stock_no_contract"][0]["qty"] == 24
    assert "bale" not in saved["stock_no_contract"][0]     # cột loại bành đã bỏ hẳn
    assert saved["sales_ccy"] == "VND" and saved["stock_material"] == 3.5

    # Báo cáo tổng hợp theo kỳ: cộng dồn sản lượng, tồn kho lấy thời điểm cuối kỳ (đã là tấn).
    pr = client.get(f"/api/unit-daily/period-report?kind=consumption&date_from={today}&date_to={today}",
                    headers=eh)
    assert pr.status_code == 200
    row = next(r for r in pr.json()["rows"] if r["company"] == unit)
    assert row["lt_export"] == 12.5 and row["total_consumption"] == 12.5
    assert row["stock_no_hd"] == 24.0 and row["stock_material"] == 3.5   # thời điểm, đơn vị tấn

    # Đơn vị thành viên KHÔNG được xem báo cáo tổng hợp (chỉ admin / quyền unit_daily).
    assert client.get(f"/api/unit-daily/period-report?kind=purchase&date_from={today}&date_to={today}",
                      headers=mh).status_code == 403
    assert client.get(f"/api/member/period-report?kind=purchase&date_from={today}&date_to={today}",
                      headers=mh).status_code == 404

    # Editor KHÔNG quyền unit_daily bị chặn; member không vào được endpoint chuyên viên.
    assert client.get(f"/api/unit-daily/day?kind=purchase&as_of={today}", headers=nh).status_code == 403
    assert client.get(f"/api/unit-daily/day?kind=purchase&as_of={today}", headers=mh).status_code == 403

    _cleanup(h, ["ud_mem", "ud_ed", "ud_noed"], [unit])


def test_unit_daily_edit_window_blocks_old_day() -> None:
    h = _admin()
    unit = "_zz_ud_win"
    old_day = (date.today() - timedelta(days=60)).isoformat()
    client.delete("/api/users/ud_win", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_win", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_win", "pass123")

    body = {"kind": "purchase", "company": unit, "as_of": old_day, "fields": {"latex_wet": 1}}
    # Ngày đã quá cửa sổ sửa (mặc định 7 ngày) → 403 chỉ-xem.
    assert client.put("/api/member/daily-report", json=body, headers=mh).status_code == 403

    # Ngày trong tương lai → 400.
    future = {**body, "as_of": (date.today() + timedelta(days=14)).isoformat()}
    assert client.put("/api/member/daily-report", json=future, headers=mh).status_code == 400

    _cleanup(h, ["ud_win"], [unit])


def test_cup_basis_and_prev_stock() -> None:
    """Mủ chén tính theo độ TSC/DRC + nút 'Lấy tồn ngày trước' (tồn kho là số thời điểm)."""
    h = _admin()
    unit = "_zz_ud_basis"
    today = date.today()
    y_day, t_day = (today - timedelta(days=1)).isoformat(), today.isoformat()
    client.delete("/api/users/ud_basis", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_basis", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_basis", "pass123")

    # 1) Thu mua: chọn độ DRC → lưu kèm payload, và giá ghi vào kho mang nhãn "đồng/độ DRC".
    assert client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": unit, "as_of": t_day,
        "fields": {"coagulum": 8, "cup_basis": "drc"}}).status_code == 200
    assert client.put("/api/member/prices", headers=mh, json={
        "company": unit, "as_of": t_day, "price_type": "purchase_cup",
        "price": 480, "basis": "drc"}).status_code == 200
    day = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}", headers=mh).json()
    assert day["entries"][unit]["fields"]["cup_basis"] == "drc"

    # Giá trị lạ ngoài {tsc, drc} phải bị loại, không ghi vào payload.
    client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": unit, "as_of": t_day,
        "fields": {"coagulum": 8, "cup_basis": "xyz"}})
    day = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}", headers=mh).json()
    assert "cup_basis" not in day["entries"][unit]["fields"]

    # 2) Tồn kho hôm qua → "Lấy tồn ngày trước" của HÔM NAY phải trả đúng số đó (đơn vị tấn).
    assert client.put("/api/member/daily-report", headers=mh, json={
        "kind": "consumption", "company": unit, "as_of": y_day, "fields": {
            "stock_no_contract": [{"grade": "RSS", "qty": 30}],
            "stock_contract": [{"grade": "SVR 10 / 20", "qty": 12, "price": 40}],
            "stock_material": 5, "stock_ccy": "USD"}}).status_code == 200
    prev = client.get(f"/api/member/daily-report/prev-stock?company={unit}&before={t_day}",
                      headers=mh).json()
    assert prev["found"] and prev["as_of"] == y_day
    assert prev["stock_no_contract"][0]["qty"] == 30 and prev["stock_material"] == 5
    assert prev["stock_ccy"] == "USD"
    assert "sales" not in prev          # KHÔNG chép dòng bán sang ngày mới (số phát sinh)

    # Không có ngày nào trước đó → found=false (không dựng số khống).
    empty = client.get(f"/api/member/daily-report/prev-stock?company={unit}&before={y_day}",
                       headers=mh).json()
    assert empty["found"] is False

    # Đơn vị khác không lấy được tồn kho của đơn vị này.
    assert client.get("/api/member/daily-report/prev-stock?company=Đơn vị khác&before=" + t_day,
                      headers=mh).status_code == 403

    _cleanup(h, ["ud_basis"], [unit])
