"""Test Nhu cầu thị trường (member + editor có quyền) + phân quyền 4 màn phân tích."""

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


def test_market_demand_member_and_editor_flow() -> None:
    h = _admin()
    unit = "_zz_md_unit"
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=40)).isoformat()
    for u in ("md_mem", "md_ed", "md_noed"):
        client.delete(f"/api/users/{u}", headers=h)

    # Đơn vị test trong catalog + 3 tài khoản: member(gán unit) · editor có quyền · editor không quyền.
    client.post("/api/member-units", json={"name": unit}, headers=h)
    assert client.post("/api/users", json={"username": "md_mem", "password": "pass123",
                                           "role": "member", "member_units": [unit]}, headers=h).status_code == 200
    client.post("/api/users", json={"username": "md_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["market_demand"]}, headers=h)
    client.post("/api/users", json={"username": "md_noed", "password": "pass123", "role": "editor"}, headers=h)
    mh, eh, nh = _bearer("md_mem", "pass123"), _bearer("md_ed", "pass123"), _bearer("md_noed", "pass123")

    # Member: xem đơn vị của mình + ghi nhu cầu.
    g = client.get(f"/api/member/market-demand?as_of={today}", headers=mh)
    assert g.status_code == 200 and g.json()["units"] == [unit]
    assert client.put("/api/member/market-demand",
                      json={"company": unit, "as_of": today, "content": "Cần mua nhiều SVR10"},
                      headers=mh).status_code == 200
    assert client.get(f"/api/member/market-demand?as_of={today}",
                      headers=mh).json()["entries"][unit] == "Cần mua nhiều SVR10"

    # Member timeline: CHỈ đơn vị được gán, thấy nội dung mình vừa nhập.
    mtl = client.get("/api/member/market-demand/timeline?days=30", headers=mh)
    assert mtl.status_code == 200
    assert all(x["company"] == unit for x in mtl.json()["entries"])
    assert any(x["as_of"] == today and x["content"] == "Cần mua nhiều SVR10" for x in mtl.json()["entries"])

    # Member: đơn vị lạ → 403; ngày ngoài cửa sổ → 403.
    assert client.put("/api/member/market-demand",
                      json={"company": "Đơn vị khác", "as_of": today, "content": "x"},
                      headers=mh).status_code == 403
    assert client.put("/api/member/market-demand",
                      json={"company": unit, "as_of": old, "content": "x"},
                      headers=mh).status_code == 403

    # Editor CÓ quyền: xem mọi đơn vị (thấy nội dung member vừa nhập) + sửa được.
    ge = client.get(f"/api/market-demand?as_of={today}", headers=eh)
    assert ge.status_code == 200 and ge.json()["entries"].get(unit) == "Cần mua nhiều SVR10"
    assert client.put("/api/market-demand",
                      json={"company": unit, "as_of": today, "content": "CV cập nhật"},
                      headers=eh).status_code == 200

    # Chống ghi trùng: TẠO MỚI (create_only) cho đơn vị đã có nhu cầu ngày đó → 409;
    # nhưng SỬA (không create_only) vẫn ghi đè được.
    assert client.put("/api/market-demand",
                      json={"company": unit, "as_of": today, "content": "trùng", "create_only": True},
                      headers=eh).status_code == 409
    assert client.put("/api/market-demand",
                      json={"company": unit, "as_of": today, "content": "sửa lại", "create_only": False},
                      headers=eh).status_code == 200

    # Timeline tổng quát: chỉ ngày ĐÃ có nhập; entry hôm nay của đơn vị xuất hiện.
    tl = client.get("/api/market-demand/timeline?days=30", headers=eh)
    assert tl.status_code == 200
    assert any(x["company"] == unit and x["as_of"] == today for x in tl.json()["entries"])
    assert client.get("/api/market-demand/timeline?days=30", headers=nh).status_code == 403

    # Editor KHÔNG quyền: cả xem lẫn sửa đều 403.
    assert client.get(f"/api/market-demand?as_of={today}", headers=nh).status_code == 403
    assert client.put("/api/market-demand",
                      json={"company": unit, "as_of": today, "content": "y"}, headers=nh).status_code == 403

    # Member không đụng được endpoint editor (không phải member endpoint) → 403.
    assert client.get(f"/api/market-demand?as_of={today}", headers=mh).status_code == 403

    # Dọn: xoá nội dung (content rỗng → không còn trong timeline) + tài khoản + đơn vị test.
    client.put("/api/market-demand", json={"company": unit, "as_of": today, "content": ""}, headers=eh)
    for u in ("md_mem", "md_ed", "md_noed"):
        client.delete(f"/api/users/{u}", headers=h)
    client.delete(f"/api/member-units/{unit}", headers=h)


def test_analysis_features_cap_gating() -> None:
    h = _admin()
    caps = ["floor_suggest", "bulletin_daily", "bulletin_weekly", "market_movement"]
    for u in ("an_all", "an_none"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/users", json={"username": "an_all", "password": "pass123",
                                    "role": "editor", "permissions": caps}, headers=h)
    client.post("/api/users", json={"username": "an_none", "password": "pass123", "role": "editor"}, headers=h)
    ah, nh = _bearer("an_all", "pass123"), _bearer("an_none", "pass123")

    # /me phản ánh đủ 4 quyền mới.
    assert set(client.get("/api/auth/me", headers=ah).json()["permissions"]) == set(caps)

    reads = [
        "/api/floor-suggest/points",
        "/api/bulletins/drafts",
        "/api/weekly-reports",
    ]
    for url in reads:
        assert client.get(url, headers=ah).status_code == 200, url        # có quyền → xem được
        assert client.get(url, headers=nh).status_code == 403, url        # không quyền → chặn
        assert client.get(url, headers=h).status_code == 200, url         # admin → tất cả

    # market_movement chỉ có POST /assessment: không quyền → 403; có quyền → qua gác (body rỗng → 422, KHÔNG 403).
    assert client.post("/api/market-movement/assessment", json={}, headers=nh).status_code == 403
    assert client.post("/api/market-movement/assessment", json={}, headers=ah).status_code != 403

    for u in ("an_all", "an_none"):
        client.delete(f"/api/users/{u}", headers=h)
