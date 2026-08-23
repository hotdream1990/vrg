"""Test đăng nhập JWT + bảo vệ route. Tự bỏ qua nếu DB không sẵn sàng."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def test_login_and_protected_route() -> None:
    # Route dữ liệu phải chặn khi chưa đăng nhập.
    assert client.get("/api/prices/latest").status_code == 401

    # Đăng nhập đúng → có token.
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["user"]["username"] == "admin"

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).json()["username"] == "admin"
    assert client.get("/api/prices/latest", headers=headers).status_code == 200


def test_bad_login() -> None:
    assert client.post("/api/auth/login", json={"username": "admin", "password": "x"}).status_code == 401


def _bearer(username: str, password: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict[str, str]:
    return _bearer("admin", "admin")


def test_profile_update() -> None:
    h = _admin_headers()
    r = client.put("/api/auth/me", json={"full_name": "Sếp Tổng"}, headers=h)
    assert r.status_code == 200 and r.json()["full_name"] == "Sếp Tổng"
    assert client.get("/api/auth/me", headers=h).json()["full_name"] == "Sếp Tổng"
    client.put("/api/auth/me", json={"full_name": "Quản trị viên"}, headers=h)  # khôi phục


def test_change_password() -> None:
    # Đổi mật khẩu trên user tạm để không đụng vào tài khoản admin.
    h = _admin_headers()
    client.delete("/api/users/pwuser", headers=h)
    client.post("/api/users", json={"username": "pwuser", "password": "pass123"}, headers=h)
    uh = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": "pwuser", "password": "pass123"}).json()["access_token"]}

    # Sai mật khẩu cũ → 400; đúng → 200 và đăng nhập bằng mật khẩu mới được.
    assert client.post("/api/auth/change-password",
                       json={"old_password": "wrong", "new_password": "pass456"}, headers=uh).status_code == 400
    assert client.post("/api/auth/change-password",
                       json={"old_password": "pass123", "new_password": "pass456"}, headers=uh).status_code == 200
    assert client.post("/api/auth/login", json={"username": "pwuser", "password": "pass456"}).status_code == 200
    client.delete("/api/users/pwuser", headers=h)  # dọn


def test_user_management_crud() -> None:
    h = _admin_headers()
    client.delete("/api/users/tester1", headers=h)  # dọn nếu sót từ lần trước

    # Tạo (role=member phải kèm ≥1 đơn vị; thiếu đơn vị → 400).
    assert client.post("/api/users",
                       json={"username": "tester1", "password": "pass123", "role": "member"},
                       headers=h).status_code == 400
    r = client.post("/api/users",
                    json={"username": "tester1", "password": "pass123", "full_name": "Tester",
                          "role": "member", "member_units": ["Cao su Test", "Cao su Test 2"]},
                    headers=h)
    assert r.status_code == 200 and r.json()["role"] == "member"
    assert r.json()["member_units"] == ["Cao su Test", "Cao su Test 2"]

    # Trùng username → 409.
    assert client.post("/api/users",
                       json={"username": "tester1", "password": "pass123"}, headers=h).status_code == 409

    # Có trong danh sách.
    assert any(u["username"] == "tester1" for u in client.get("/api/users", headers=h).json())

    # Cập nhật + đăng nhập được.
    assert client.put("/api/users/tester1", json={"full_name": "Tester 2"}, headers=h).json()["full_name"] == "Tester 2"
    assert client.post("/api/users/tester1/reset-password", json={"new_password": "newpass1"}, headers=h).status_code == 200
    assert client.post("/api/auth/login", json={"username": "tester1", "password": "newpass1"}).status_code == 200

    # Member KHÔNG được vào quản trị người dùng → 403.
    mh = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": "tester1", "password": "newpass1"}).json()["access_token"]}
    assert client.get("/api/users", headers=mh).status_code == 403

    # Xoá.
    assert client.delete("/api/users/tester1", headers=h).status_code == 200


def test_role_editor_vs_viewer_write_access() -> None:
    h = _admin_headers()
    for u in ("ed_test", "ed_nocap", "vw_test"):
        client.delete(f"/api/users/{u}", headers=h)
    # editor CÓ quyền 'member_unit' · editor KHÔNG có quyền nào · viewer
    client.post("/api/users", json={"username": "ed_test", "password": "pass123", "role": "editor",
                                    "permissions": ["member_unit"]}, headers=h)
    client.post("/api/users", json={"username": "ed_nocap", "password": "pass123", "role": "editor"}, headers=h)
    client.post("/api/users", json={"username": "vw_test", "password": "pass123", "role": "viewer"}, headers=h)
    eh, nh, vh = _bearer("ed_test", "pass123"), _bearer("ed_nocap", "pass123"), _bearer("vw_test", "pass123")

    # /me phản ánh đúng quyền đã cấp.
    assert client.get("/api/auth/me", headers=eh).json()["permissions"] == ["member_unit"]
    assert client.get("/api/auth/me", headers=nh).json()["permissions"] == []

    # Đọc: mọi tài khoản đăng nhập đều được.
    assert client.get("/api/member-units", headers=eh).status_code == 200
    assert client.get("/api/member-units", headers=vh).status_code == 200

    # Ghi: editor CÓ quyền được; editor KHÔNG có quyền và viewer đều bị 403.
    assert client.post("/api/member-units", json={"name": "_zz_test_unit"}, headers=eh).status_code == 200
    assert client.post("/api/member-units", json={"name": "_zz_test_unit2"}, headers=nh).status_code == 403
    assert client.post("/api/member-units", json={"name": "_zz_test_unit3"}, headers=vh).status_code == 403

    # Không phải admin → không vào được quản trị người dùng.
    assert client.get("/api/users", headers=eh).status_code == 403
    assert client.get("/api/users", headers=vh).status_code == 403

    # Dọn.
    client.delete("/api/member-units/_zz_test_unit", headers=h)
    for u in ("ed_test", "ed_nocap", "vw_test"):
        client.delete(f"/api/users/{u}", headers=h)


def test_last_admin_guard() -> None:
    h = _admin_headers()
    # Không thể tự xoá / tự khoá / tự hạ quyền (admin duy nhất).
    assert client.delete("/api/users/admin", headers=h).status_code == 400
    assert client.put("/api/users/admin", json={"is_active": False}, headers=h).status_code == 400
    assert client.put("/api/users/admin", json={"role": "member"}, headers=h).status_code == 400
    # Đảm bảo admin vẫn còn quyền sau các phép thử.
    assert client.get("/api/auth/me", headers=_admin_headers()).json()["role"] == "admin"


def test_impersonate_flow() -> None:
    h = _admin_headers()
    client.delete("/api/users/imp_target", headers=h)
    client.delete("/api/users/imp_locked", headers=h)
    client.post("/api/users", json={"username": "imp_target", "password": "pass123",
                                    "full_name": "Người được mạo danh", "role": "viewer"}, headers=h)
    client.post("/api/users", json={"username": "imp_locked", "password": "pass123",
                                    "role": "viewer"}, headers=h)
    client.put("/api/users/imp_locked", json={"is_active": False}, headers=h)

    # Admin mạo danh thành công → token trả về là của tài khoản đích, /me phản ánh đúng + báo impersonated_by.
    r = client.post("/api/auth/impersonate", json={"username": "imp_target"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["username"] == "imp_target"
    assert body["user"]["impersonated_by"] == "admin"
    imp_headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/auth/me", headers=imp_headers).json()
    assert me["username"] == "imp_target" and me["impersonated_by"] == "admin"

    # Token đang mạo danh không được mạo danh tiếp.
    assert client.post("/api/auth/impersonate", json={"username": "admin"},
                       headers=imp_headers).status_code == 403

    # Non-admin (chưa mạo danh) không được gọi endpoint mạo danh.
    vh = _bearer("imp_target", "pass123")
    assert client.post("/api/auth/impersonate", json={"username": "admin"}, headers=vh).status_code == 403

    # Admin tự mạo danh chính mình → 400.
    assert client.post("/api/auth/impersonate", json={"username": "admin"}, headers=h).status_code == 400

    # Tài khoản không tồn tại → 404; tài khoản đã khoá → 400.
    assert client.post("/api/auth/impersonate", json={"username": "no_such_user"},
                       headers=h).status_code == 404
    assert client.post("/api/auth/impersonate", json={"username": "imp_locked"},
                       headers=h).status_code == 400

    # Phiên bình thường (không mạo danh) không có impersonated_by.
    assert client.get("/api/auth/me", headers=h).json()["impersonated_by"] is None

    client.delete("/api/users/imp_target", headers=h)
    client.delete("/api/users/imp_locked", headers=h)


def test_member_self_price_flow() -> None:
    from datetime import date, timedelta
    from urllib.parse import quote

    h = _admin_headers()
    client.delete("/api/users/mem_test", headers=h)  # dọn nếu sót
    u1, u2, other = "Cao su Member A", "Cao su Member B", "Cao su Không Gán"

    # Tạo tài khoản đơn vị thành viên gắn NHIỀU đơn vị + đăng nhập.
    assert client.post("/api/users", json={"username": "mem_test", "password": "pass123",
                                           "role": "member", "member_units": [u1, u2]}, headers=h).status_code == 200
    mh = _bearer("mem_test", "pass123")
    assert client.get("/api/auth/me", headers=mh).json()["member_units"] == [u1, u2]

    today = date.today().isoformat()
    g = client.get("/api/member/prices", headers=mh)
    assert g.status_code == 200 and g.json()["units"] == [u1, u2]

    # Nhập mủ nước cho u1 + mủ chén cho u2 → đọc lại đúng theo từng đơn vị.
    assert client.put("/api/member/prices",
                      json={"company": u1, "as_of": today, "price_type": "purchase", "price": 385},
                      headers=mh).status_code == 200
    assert client.put("/api/member/prices",
                      json={"company": u2, "as_of": today, "price_type": "purchase_cup", "price": 12500},
                      headers=mh).status_code == 200
    sheets = client.get("/api/member/prices", headers=mh).json()["sheets"]
    assert sheets[u1]["purchase"][today] == 385 and sheets[u2]["purchase_cup"][today] == 12500

    # Đơn vị KHÔNG được gán → 403 (không ghi được cho đơn vị khác).
    assert client.put("/api/member/prices",
                      json={"company": other, "as_of": today, "price_type": "purchase", "price": 1},
                      headers=mh).status_code == 403

    # Ngoài cửa sổ 7 ngày → 403; ngày tương lai → 400.
    old = (date.today() - timedelta(days=30)).isoformat()
    future = (date.today() + timedelta(days=1)).isoformat()
    assert client.put("/api/member/prices",
                      json={"company": u1, "as_of": old, "price_type": "purchase", "price": 100},
                      headers=mh).status_code == 403
    assert client.put("/api/member/prices",
                      json={"company": u1, "as_of": future, "price_type": "purchase", "price": 100},
                      headers=mh).status_code == 400

    # Token member KHÔNG đụng được endpoint nội bộ (cần quyền mục) → 403.
    assert client.delete(f"/api/prices/purchase?as_of={today}", headers=mh).status_code == 403
    # Admin (không phải member) gọi endpoint member → 403.
    assert client.get("/api/member/prices", headers=h).status_code == 403

    # Dọn: xoá 2 ô đã nhập + tài khoản.
    client.delete(f"/api/member/prices?company={quote(u1)}&as_of={today}&price_type=purchase", headers=mh)
    client.delete(f"/api/member/prices?company={quote(u2)}&as_of={today}&price_type=purchase_cup", headers=mh)
    client.delete("/api/users/mem_test", headers=h)


def test_member_has_purchase_plan_flag() -> None:
    """Cờ `member_has_purchase_plan` suy từ SỐ KẾ HOẠCH THU MUA ở màn Kế hoạch năm (chốt 03/08/2026).

    Không còn cờ bật/tắt trên từng đơn vị: có số > 0 thì đơn vị mới thấy màn Thu mua; khai 0 =
    không tổ chức thu mua.
    """
    from datetime import date

    from app.services import member_unit_repo, unit_daily_repo

    h = _admin_headers()
    plan_unit, no_plan_unit = "Cao su Có KH Test", "Cao su Không KH Test"
    member_unit_repo.add_unit(plan_unit)
    member_unit_repo.add_unit(no_plan_unit)
    year = date.today().year
    unit_daily_repo.set_year_plan(year, plan_unit, 1000.0, None, None, None, None, None, "admin")
    unit_daily_repo.set_year_plan(year, no_plan_unit, 0.0, None, None, None, None, None, "admin")
    client.delete("/api/users/mem_plan", headers=h)  # dọn nếu sót

    # Chỉ gắn đơn vị KHÔNG có KH thu mua → cờ False.
    assert client.post("/api/users", json={"username": "mem_plan", "password": "pass123",
                                           "role": "member", "member_units": [no_plan_unit]},
                       headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=_bearer("mem_plan", "pass123")
                      ).json()["member_has_purchase_plan"] is False

    # Gắn thêm đơn vị CÓ KH thu mua → cờ True (any-of); login response cũng mang cờ.
    assert client.put("/api/users/mem_plan",
                      json={"member_units": [no_plan_unit, plan_unit]}, headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=_bearer("mem_plan", "pass123")
                      ).json()["member_has_purchase_plan"] is True
    lr = client.post("/api/auth/login", json={"username": "mem_plan", "password": "pass123"}).json()
    assert lr["user"]["member_has_purchase_plan"] is True

    # Dọn.
    client.delete("/api/users/mem_plan", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = ANY(:c)"),
                   {"c": [plan_unit, no_plan_unit]})
    member_unit_repo.delete_unit(plan_unit)
    member_unit_repo.delete_unit(no_plan_unit)
