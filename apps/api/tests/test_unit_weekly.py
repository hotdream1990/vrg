"""Test báo cáo tuần đơn vị (member + chuyên viên có quyền `unit_weekly`) + cửa sổ sửa tuần."""

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


def _monday(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def test_unit_weekly_member_and_editor_flow() -> None:
    h = _admin()
    unit = "_zz_uw_unit"
    this_week = _monday(date.today())
    for u in ("uw_mem", "uw_ed", "uw_noed"):
        client.delete(f"/api/users/{u}", headers=h)

    client.post("/api/member-units", json={"name": unit}, headers=h)
    assert client.post("/api/users", json={"username": "uw_mem", "password": "pass123",
                                           "role": "member", "member_units": [unit]}, headers=h).status_code == 200
    client.post("/api/users", json={"username": "uw_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_weekly"]}, headers=h)
    client.post("/api/users", json={"username": "uw_noed", "password": "pass123", "role": "editor"}, headers=h)
    mh, eh, nh = _bearer("uw_mem", "pass123"), _bearer("uw_ed", "pass123"), _bearer("uw_noed", "pass123")

    # Member ghi số liệu thu mua tuần này (key rác 'bad' bị loại).
    body = {"kind": "purchase", "company": unit, "week_key": this_week,
            "fields": {"latex_wet": 120.5, "coagulum": 30, "cum_purchase": 800, "bad": 9}}
    assert client.put("/api/member/weekly-report", json=body, headers=mh).status_code == 200
    g = client.get(f"/api/member/weekly-report?kind=purchase&week_key={this_week}", headers=mh)
    assert g.status_code == 200 and g.json()["units"] == [unit]
    saved = g.json()["entries"][unit]["fields"]
    assert saved["latex_wet"] == 120.5 and "bad" not in saved

    # Member không được đụng đơn vị khác.
    bad = {"kind": "purchase", "company": "khac", "week_key": this_week, "fields": {"latex_wet": 1}}
    assert client.put("/api/member/weekly-report", json=bad, headers=mh).status_code == 403

    # create_only chống ghi trùng (đã có số → 409).
    dup = {**body, "create_only": True}
    assert client.put("/api/member/weekly-report", json=dup, headers=mh).status_code == 409

    # Chuyên viên có quyền: xem lưới cả tuần + đặt chỉ tiêu kế hoạch → tính % ở FE.
    wk = client.get(f"/api/unit-weekly/week?kind=purchase&week_key={this_week}", headers=eh)
    assert wk.status_code == 200 and unit in wk.json()["entries"]
    assert client.put("/api/unit-weekly/plan",
                      json={"year": date.today().year, "company": unit, "plan_tonnes": 2000},
                      headers=eh).status_code == 200
    pl = client.get(f"/api/unit-weekly/plan?year={date.today().year}", headers=eh)
    assert pl.json()["plans"][unit] == 2000

    # Chuyên viên sửa số của đơn vị (consumption) + timeline hiện bản ghi.
    cons = {"kind": "consumption", "company": unit, "week_key": this_week,
            "fields": {"stock_finished": 500, "stock_finished_hd": 300, "g_latex": 50}}
    assert client.put("/api/unit-weekly/report", json=cons, headers=eh).status_code == 200
    tl = client.get("/api/unit-weekly/timeline?kind=consumption&weeks=8", headers=eh)
    assert any(e["company"] == unit for e in tl.json()["entries"])

    # Editor KHÔNG quyền unit_weekly bị chặn; member không vào được endpoint chuyên viên.
    assert client.get(f"/api/unit-weekly/week?kind=purchase&week_key={this_week}", headers=nh).status_code == 403
    assert client.get(f"/api/unit-weekly/week?kind=purchase&week_key={this_week}", headers=mh).status_code == 403


def test_unit_weekly_edit_window_blocks_old_week() -> None:
    h = _admin()
    unit = "_zz_uw_win"
    old_week = _monday(date.today() - timedelta(days=60))
    client.delete("/api/users/uw_win", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "uw_win", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("uw_win", "pass123")

    body = {"kind": "purchase", "company": unit, "week_key": old_week, "fields": {"latex_wet": 1}}
    # Tuần đã quá cửa sổ sửa (mặc định 7 ngày) → 403 chỉ-xem.
    assert client.put("/api/member/weekly-report", json=body, headers=mh).status_code == 403

    # Tuần trong tương lai → 400.
    future = {**body, "week_key": _monday(date.today() + timedelta(days=14))}
    assert client.put("/api/member/weekly-report", json=future, headers=mh).status_code == 400
