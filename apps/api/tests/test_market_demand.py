"""Test Nhu cầu thị trường THEO TRƯỜNG (phiếu có tình trạng) + phân quyền 4 màn phân tích.

DB dev dùng chung/bản sao prod: đơn vị mang tiền tố `_zz_md_`, tài khoản `zz_md_`, dọn trước và sau
mỗi test; cấu hình cửa sổ nhập liệu trả lại giá trị cũ. Hàng rào thời gian + đề nghị sửa ở
`test_market_demand_fences.py` (dùng chung fixture `md` của file này).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import edit_window
from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import (
    config_repo, mailer, market_demand_item_policy, market_demand_item_repo, member_unit_repo,
    user_repo,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT_A, UNIT_B, UNIT_OLD = "_zz_md_a", "_zz_md_b", "_zz_md_old"
UNITS = [UNIT_A, UNIT_B, UNIT_OLD]
ACCOUNTS = {"mem": ("member", [UNIT_A], []), "memb": ("member", [UNIT_B], []),
            "lead": ("leader", [UNIT_A], []), "ed": ("editor", [], ["market_demand"]),
            "view": ("editor", [], ["market_demand:view"]), "none": ("editor", [], ["unit_daily"])}
WINDOW_KEYS = ("MEMBER_EDIT_WINDOW_DAYS", "EDITOR_EDIT_WINDOW_DAYS")
TODAY = edit_window.today()
TODAY_ISO = TODAY.isoformat()
YDAY = (TODAY - timedelta(days=1)).isoformat()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()
MEMBER_URL, EDITOR_URL = "/api/member/market-demand/items", "/api/market-demand/items"


def login(username: str, password: str = "pass123") -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def item(**kw) -> dict:
    return {"company": UNIT_A, "as_of": TODAY_ISO, "customer": "Công ty ZZ Anh Dũng", "grade": "LATEX",
            "qty": 100, "qty_unit": "ton", "price": 40, "currency": "VND", **kw}


def seed(**kw) -> dict:
    """Ghi thẳng repo (bỏ qua hàng rào) — dựng phiếu cũ cho test."""
    return market_demand_item_repo.save(market_demand_item_policy.clean(item(**kw)), "admin")


def _cleanup() -> None:
    with session_scope() as db:
        for tbl in ("market_demand_item", "edit_request", "audit_log"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM app_user WHERE username = ANY(:n)"),
                   {"n": [f"zz_md_{n}" for n in ACCOUNTS]})
        db.execute(text("UPDATE member_unit SET merged_into = NULL, merged_at = NULL "
                        "WHERE merged_into = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM member_unit WHERE name = ANY(:u)"), {"u": UNITS})


@pytest.fixture()
def md(monkeypatch):
    user_repo.seed_admin()
    _cleanup()
    h = login("admin", "admin")
    for u in UNITS:
        member_unit_repo.add_unit(u)
    for name, (role, units, perms) in ACCOUNTS.items():
        res = client.post("/api/users", headers=h, json={
            "username": f"zz_md_{name}", "password": "pass123", "role": role, "member_units": units,
            "permissions": perms, "email": f"zz_md_{name}@example.invalid"})
        assert res.status_code == 200, res.text
    old = {k: config_repo.get_value(k) for k in WINDOW_KEYS}
    config_repo.set_config({k: "7" for k in WINDOW_KEYS})
    # Đề nghị sửa gửi email cho người duyệt THẬT trong DB bản sao prod — chặn hẳn.
    monkeypatch.setattr(mailer, "send_async", lambda *_a, **_k: None)
    try:
        yield {"admin": h, **{n: login(f"zz_md_{n}") for n in ACCOUNTS}}
    finally:
        config_repo.set_config({k: v or "__CLEAR__" for k, v in old.items()})
        _cleanup()


def _ids(res) -> list[int]:
    assert res.status_code == 200, res.text
    return [x["id"] for x in res.json()["items"]]


def test_member_crud_scope_and_leader_read_only(md) -> None:
    created = client.put(MEMBER_URL, headers=md["mem"], json=item())
    assert created.status_code == 200, created.text
    got = created.json()["item"]
    iid = got["id"]
    assert got["price"] == 40.0 and got["result"] == "" and got["legacy"] is False
    assert got["created_by"] == "zz_md_mem" and got["delivery_time"] == ""
    assert not {"status", "contract_no", "delivery_from", "price_provisional"} & set(got)
    listed = client.get(MEMBER_URL, headers=md["mem"]).json()
    assert listed["units"] == [UNIT_A] and listed["view_only_units"] == []
    assert "LATEX" in listed["grades"] and iid in [x["id"] for x in listed["items"]]

    signed = client.put(MEMBER_URL, headers=md["mem"], json=item(
        id=iid, delivery_time="  đến 30/11/2026 ", result=" Đã ký HĐMB số 1752 ngày 17/09/2026 "))
    assert signed.status_code == 200, signed.text
    assert signed.json()["item"]["result"] == "Đã ký HĐMB số 1752 ngày 17/09/2026"
    assert signed.json()["item"]["delivery_time"] == "đến 30/11/2026"

    # Đơn vị khác: không ghi, không xoá, không thấy.
    assert client.put(MEMBER_URL, headers=md["memb"], json=item()).status_code == 403
    assert client.put(MEMBER_URL, headers=md["memb"], json=item(id=iid, company=UNIT_B)).status_code == 403
    assert client.delete(f"{MEMBER_URL}/{iid}", headers=md["memb"]).status_code == 403
    assert iid not in _ids(client.get(MEMBER_URL, headers=md["memb"]))
    assert client.delete(f"{MEMBER_URL}/999999999", headers=md["mem"]).status_code == 404

    lead = client.get(MEMBER_URL, headers=md["lead"])
    assert lead.json()["units"] == [UNIT_A] and iid in _ids(lead)
    assert client.put(MEMBER_URL, headers=md["lead"], json=item(id=iid)).status_code == 403
    assert client.delete(f"{MEMBER_URL}/{iid}", headers=md["lead"]).status_code == 403

    assert client.delete(f"{MEMBER_URL}/{iid}", headers=md["mem"]).json() == {"ok": True}
    assert iid not in _ids(client.get(MEMBER_URL, headers=md["mem"]))


def test_editor_endpoints_filters_and_caps(md) -> None:
    ed = md["ed"]
    res = client.put(EDITOR_URL, headers=ed, json=item(company=UNIT_B, customer="Khach 100% La"))
    assert res.status_code == 200, res.text
    iid = res.json()["item"]["id"]
    assert res.json()["item"]["created_by"] == "zz_md_ed"
    body = client.get(EDITOR_URL, headers=ed, params={"company": UNIT_B}).json()
    assert UNIT_A in body["units"] and body["grades"] and [x["id"] for x in body["items"]] == [iid]
    assert iid in _ids(client.get(EDITOR_URL, headers=ed, params={"q": "kHACH 100%"}))
    ed_item = res.json()["item"]
    client.put(EDITOR_URL, headers=ed, json={**ed_item, "result": "Đã ký HĐMB số ZZ-77"})
    assert _ids(client.get(EDITOR_URL, headers=ed, params={"company": UNIT_B, "q": "zz-77"})) == [iid]
    # Ký tự đại diện của LIKE được hiểu theo nghĩa đen: "%" khớp chữ "%", "_" không khớp gì.
    assert _ids(client.get(EDITOR_URL, headers=ed, params={"company": UNIT_B, "q": "%"})) == [iid]
    assert _ids(client.get(EDITOR_URL, headers=ed, params={"company": UNIT_B, "q": "_"})) == []
    assert _ids(client.get(EDITOR_URL, headers=ed, params={"company": UNIT_B, "grade": "RSS 3"})) == []
    assert client.get(EDITOR_URL, headers=ed, params={"date_from": TODAY_ISO, "date_to": YDAY}).status_code == 400

    assert client.put(EDITOR_URL, headers=ed, json=item(company="_zz_md_khong_co")).status_code == 400
    assert client.get(EDITOR_URL, headers=md["view"]).status_code == 200
    assert client.put(EDITOR_URL, headers=md["view"], json=item()).status_code == 403
    assert client.delete(f"{EDITOR_URL}/{iid}", headers=md["view"]).status_code == 403
    for who in ("none", "mem", "lead"):
        assert client.get(EDITOR_URL, headers=md[who]).status_code == 403, who
    assert client.delete(f"{EDITOR_URL}/{iid}", headers=ed).status_code == 200
    assert client.delete(f"{EDITOR_URL}/{iid}", headers=ed).status_code == 404


BAD = [
    ({"customer": "   "}, "khách hàng"), ({"customer": "x" * 201}, "tối đa"),
    ({"grade": "SVR 99"}, "Chủng loại"), ({"qty": -1}, "không âm"), ({"qty_unit": "kg"}, "Đơn vị số lượng"),
    ({"currency": "EUR"}, "Loại tiền"), ({"price": 40000}, "TRIỆU"),
    ({"price": 25000, "currency": "USD"}, "USD/tấn"), ({"as_of": "2026-13-01"}, "không hợp lệ"),
    ({"as_of": TOMORROW}, "tương lai"), ({"note": "x" * 2001}, "tối đa"),
    ({"delivery_place": "x" * 201}, "tối đa"), ({"delivery_time": "x" * 201}, "Thời gian giao"),
    ({"result": "x" * 501}, "Kết quả"),
]


def test_business_rules_reject_bad_items(md) -> None:
    for patch, fragment in BAD:
        for url, who in ((MEMBER_URL, "mem"), (EDITOR_URL, "admin")):
            res = client.put(url, headers=md[who], json=item(**patch))
            assert res.status_code == 400, (patch, who, res.text)
            assert fragment.lower() in res.json()["detail"].lower(), (patch, res.json()["detail"])
    ok = client.put(MEMBER_URL, headers=md["mem"], json=item(price=2380, currency="USD", qty=3, qty_unit="container",
                                                            delivery_time="T10+11/2026"))
    assert ok.status_code == 200 and ok.json()["item"]["qty_unit"] == "container", ok.text


def test_analysis_features_cap_gating() -> None:
    user_repo.seed_admin()
    h = login("admin", "admin")
    caps = ["floor_suggest", "bulletin_daily", "bulletin_weekly", "market_movement"]
    for u in ("an_all", "an_none"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/users", json={"username": "an_all", "password": "pass123",
                                    "role": "editor", "permissions": caps}, headers=h)
    client.post("/api/users", json={"username": "an_none", "password": "pass123", "role": "editor"}, headers=h)
    ah, nh = login("an_all"), login("an_none")
    assert set(client.get("/api/auth/me", headers=ah).json()["permissions"]) == set(caps)
    for url in ("/api/floor-suggest/points", "/api/bulletins/drafts", "/api/weekly-reports"):
        assert client.get(url, headers=ah).status_code == 200, url        # có quyền → xem được
        assert client.get(url, headers=nh).status_code == 403, url        # không quyền → chặn
        assert client.get(url, headers=h).status_code == 200, url         # admin → tất cả
    # market_movement chỉ có POST /assessment: không quyền → 403; có quyền → qua gác (body rỗng → 422).
    assert client.post("/api/market-movement/assessment", json={}, headers=nh).status_code == 403
    assert client.post("/api/market-movement/assessment", json={}, headers=ah).status_code != 403
    for u in ("an_all", "an_none"):
        client.delete(f"/api/users/{u}", headers=h)
