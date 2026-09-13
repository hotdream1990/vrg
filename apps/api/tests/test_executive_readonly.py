"""Test LÃNH ĐẠO TẬP ĐOÀN (role=executive): xem mọi báo cáo · thống kê · AI, KHÔNG ghi được gì.

Ba điều phải khoá chặt:
1. Xem được các màn nghiệp vụ mức Tập đoàn (không bị chặn như tài khoản đơn vị).
2. Không vào được phần kỹ thuật/quản trị (người dùng · cấu hình · lịch chạy · nhật ký · hộp thư).
3. Chỉ xem: mọi method ghi đều 403 (chặn ở dependency toàn cục), trừ đúng 4 thao tác cho phép.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.core.executive_readonly_guard import EXECUTIVE_WRITE_ALLOW
from app.core.permissions import EXECUTIVE_CAPS, LEVEL_EDIT, effective_caps, has_cap
from app.main import app
from app.services import user_repo

client = TestClient(app)

EXEC_USER, EXEC_PASS = "_zz_exec_leader", "pass123"
_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")


def test_quyen_hieu_luc_chi_o_muc_xem() -> None:
    """Quyền lãnh đạo Tập đoàn cố định theo vai trò — `permissions` gửi kèm không nâng được lên Sửa."""
    caps = effective_caps("executive", ["physical", "audit", "support"])
    assert set(caps) == set(EXECUTIVE_CAPS)
    assert all(level == "view" for level in caps.values())
    for technical in ("member_unit", "support", "audit"):
        assert technical not in caps
    assert not has_cap(caps, "physical", LEVEL_EDIT)


def test_danh_sach_cho_phep_khop_route_that() -> None:
    """Đổi đường dẫn một endpoint trong danh sách mà quên sửa theo → lãnh đạo mất tính năng đó."""
    paths = app.openapi()["paths"]
    for method, path in EXECUTIVE_WRITE_ALLOW:
        assert method.lower() in paths.get(path, {}), f"{method} {path} không còn tồn tại"


def _bearer(username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def env():
    user_repo.seed_admin()
    admin = _bearer("admin", "admin")
    client.delete(f"/api/users/{EXEC_USER}", headers=admin)
    r = client.post("/api/users", headers=admin, json={
        "username": EXEC_USER, "password": EXEC_PASS, "full_name": "Lãnh đạo test",
        "role": "executive", "permissions": ["physical"]})
    assert r.status_code == 200, r.text
    yield {"admin": admin, "exec": _bearer(EXEC_USER, EXEC_PASS)}
    client.delete(f"/api/users/{EXEC_USER}", headers=admin)


@_db
def test_xem_duoc_bao_cao_thong_ke_va_ai(env) -> None:
    h = env["exec"]
    for url in ("/api/series/stock", "/api/floor-suggest/points", "/api/floor",
                "/api/market-quote", "/api/inventory", "/api/prices/latest",
                "/api/unit-daily/analytics/filters", "/api/sales-contracts/meta",
                "/api/weekly-reports", "/api/assistant/history", "/api/bulletins/published"):
        r = client.get(url, headers=h)
        assert r.status_code == 200, f"{url} → {r.status_code} {r.text[:200]}"
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "executive"


@_db
def test_khong_vao_phan_ky_thuat_quan_tri(env) -> None:
    h = env["exec"]
    for url in ("/api/users", "/api/config", "/api/schedules", "/api/anomalies",
                "/api/audit", "/api/support/threads"):
        r = client.get(url, headers=h)
        assert r.status_code == 403, f"{url} → {r.status_code} (phải 403)"


@_db
def test_moi_thao_tac_ghi_deu_bi_chan(env) -> None:
    h = env["exec"]
    writes = [
        ("post", "/api/prices/scan"), ("put", "/api/prices/records"), ("delete", "/api/prices/records"),
        ("post", "/api/floor"), ("put", "/api/market-quote"), ("post", "/api/inventory"),
        ("put", "/api/market-demand"), ("put", "/api/unit-daily/report"), ("put", "/api/unit-daily/plan"),
        ("put", "/api/sales-contracts"), ("put", "/api/customers"), ("put", "/api/master-contracts"),
        ("post", "/api/bulletins/draft"), ("post", "/api/bulletins/market-analysis"),
        ("put", "/api/weekly-reports/2026-09-07"), ("post", "/api/weekly-reports/2026-09-07/ai-assist"),
        ("post", "/api/member-units"), ("put", "/api/prices/purchase-auto-sync"),
        ("post", "/api/data-lock/confirm"), ("post", "/api/users"), ("post", "/api/auth/impersonate"),
        ("delete", "/api/assistant/history"),
    ]
    for method, url in writes:
        r = getattr(client, method)(url, headers=h, **({} if method == "delete" else {"json": {}}))
        assert r.status_code == 403, f"{method.upper()} {url} → {r.status_code} (phải 403)"
        # Đúng hàng rào toàn cục chặn — không phải tình cờ bị một kiểu gác khác chặn hộ.
        assert "Lãnh đạo Tập đoàn" in r.json()["detail"], f"{method.upper()} {url}: {r.text[:120]}"


@_db
def test_van_dung_duoc_ho_so_doi_mat_khau_va_ai(env) -> None:
    h = env["exec"]
    r = client.put("/api/auth/me", headers=h, json={"full_name": "Lãnh đạo test 2"})
    assert r.status_code == 200, r.text
    r = client.post("/api/auth/change-password", headers=h,
                    json={"old_password": EXEC_PASS, "new_password": "pass1234"})
    assert r.status_code == 200, r.text
    # Body sai kiểu → 422 chứng tỏ đã QUA hàng rào (không gọi LLM thật khi test).
    for url in ("/api/assistant/chat", "/api/market-movement/assessment"):
        r = client.post(url, headers=h, json={"messages": "x", "groups": "x"})
        assert r.status_code == 422, f"{url} → {r.status_code} {r.text[:200]}"
    # Xuất PDF báo cáo tuần: tuần sai định dạng thì lỗi ngay khi dựng báo cáo (không chạy trình
    # duyệt in PDF) — miễn KHÔNG phải 403 là đã qua hàng rào.
    r = client.post("/api/weekly-reports/khong-phai-tuan/generate-pdf", headers=h)
    assert r.status_code != 403, r.text[:200]


@_db
def test_hang_rao_khong_anh_huong_vai_tro_khac(env) -> None:
    """Chưa đăng nhập vẫn 401 như cũ; admin ghi bình thường (hàng rào chỉ nhắm executive)."""
    assert client.post("/api/floor", json={}).status_code == 401
    r = client.put(f"/api/users/{EXEC_USER}", headers=env["admin"], json={"full_name": "Đổi bởi admin"})
    assert r.status_code == 200, r.text
