"""Test đăng nhập JWT + bảo vệ route. Tự bỏ qua nếu DB không sẵn sàng."""

from __future__ import annotations

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

    # Tạo.
    r = client.post("/api/users",
                    json={"username": "tester1", "password": "pass123", "full_name": "Tester", "role": "member"},
                    headers=h)
    assert r.status_code == 200 and r.json()["role"] == "member"

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
    for u in ("ed_test", "vw_test"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/users", json={"username": "ed_test", "password": "pass123", "role": "editor"}, headers=h)
    client.post("/api/users", json={"username": "vw_test", "password": "pass123", "role": "viewer"}, headers=h)
    eh, vh = _bearer("ed_test", "pass123"), _bearer("vw_test", "pass123")

    # Đọc: cả editor lẫn viewer đều được.
    assert client.get("/api/member-units", headers=eh).status_code == 200
    assert client.get("/api/member-units", headers=vh).status_code == 200

    # Ghi: editor được, viewer bị chặn 403.
    assert client.post("/api/member-units", json={"name": "_zz_test_unit"}, headers=eh).status_code == 200
    assert client.post("/api/member-units", json={"name": "_zz_test_unit2"}, headers=vh).status_code == 403

    # Cả hai đều KHÔNG phải admin → không vào được quản trị người dùng.
    assert client.get("/api/users", headers=eh).status_code == 403
    assert client.get("/api/users", headers=vh).status_code == 403

    # Dọn.
    client.delete("/api/member-units/_zz_test_unit", headers=h)
    client.delete("/api/users/ed_test", headers=h)
    client.delete("/api/users/vw_test", headers=h)


def test_last_admin_guard() -> None:
    h = _admin_headers()
    # Không thể tự xoá / tự khoá / tự hạ quyền (admin duy nhất).
    assert client.delete("/api/users/admin", headers=h).status_code == 400
    assert client.put("/api/users/admin", json={"is_active": False}, headers=h).status_code == 400
    assert client.put("/api/users/admin", json={"role": "member"}, headers=h).status_code == 400
    # Đảm bảo admin vẫn còn quyền sau các phép thử.
    assert client.get("/api/auth/me", headers=_admin_headers()).json()["role"] == "admin"
