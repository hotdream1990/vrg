"""Cửa sổ nhập liệu: chuyên viên bị giới hạn N ngày gần nhất, admin miễn, admin đổi được số ngày."""

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


def _admin_headers() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _bearer(u: str, p: str) -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


_GRADE = "_ZZ_win_test"


def _rec(as_of: str, price: float = 100.0) -> dict:
    return {"as_of": as_of, "source": "vrg", "grade": _GRADE, "contract": "",
            "price_type": "purchase", "price": price, "currency": "VND", "unit": "đồng/độ TSC"}


def _clear_windows(h: dict[str, str]) -> None:
    client.put("/api/config",
               json={"EDITOR_EDIT_WINDOW_DAYS": "__CLEAR__", "MEMBER_EDIT_WINDOW_DAYS": "__CLEAR__"}, headers=h)


def test_editor_window_enforced_admin_exempt_configurable() -> None:
    h = _admin_headers()
    _clear_windows(h)  # baseline sạch (idempotent giữa các lần chạy)
    client.delete("/api/users/win_ed", headers=h)
    assert client.post("/api/users", json={"username": "win_ed", "password": "pass123",
                                           "role": "editor", "permissions": ["raw_material"]},
                       headers=h).status_code == 200
    eh = _bearer("win_ed", "pass123")

    today = date.today().isoformat()
    old = (date.today() - timedelta(days=30)).isoformat()

    # settings đọc-được: mặc định 7 ngày cho cả hai
    s = client.get("/api/settings/edit-windows", headers=eh).json()
    assert s["editor_days"] == 7 and s["member_days"] == 7

    # Chuyên viên: hôm nay OK, ngày cũ (30 ngày) → 403 (ngoài cửa sổ)
    assert client.put("/api/prices/records", json=_rec(today), headers=eh).status_code == 200
    assert client.put("/api/prices/records", json=_rec(old), headers=eh).status_code == 403

    # Admin: ngày cũ vẫn ghi được (miễn cửa sổ)
    assert client.put("/api/prices/records", json=_rec(old), headers=h).status_code == 200

    # Admin nới cửa sổ chuyên viên lên 60 ngày → chuyên viên ghi được ngày cũ
    assert client.put("/api/config", json={"EDITOR_EDIT_WINDOW_DAYS": "60"}, headers=h).status_code == 200
    assert client.get("/api/settings/edit-windows", headers=eh).json()["editor_days"] == 60
    assert client.put("/api/prices/records", json=_rec(old), headers=eh).status_code == 200

    # Dọn: về mặc định + xoá bản ghi test + xoá user
    _clear_windows(h)
    for d in (today, old):
        client.delete(
            f"/api/prices/records?as_of={d}&source=vrg&grade={_GRADE}&contract=&price_type=purchase", headers=h)
    client.delete("/api/users/win_ed", headers=h)
