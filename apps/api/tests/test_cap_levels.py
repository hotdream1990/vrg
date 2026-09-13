"""Test phân cấp quyền Xem/Sửa cho các mục nhập liệu (permissions.py + require_cap_edit)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.core.permissions import (
    LEVEL_EDIT,
    LEVEL_VIEW,
    SPLIT_CAPS,
    clean_caps,
    effective_caps,
    has_cap,
    parse_cap,
)
from app.main import app
from app.services import user_repo

client = TestClient(app)


# ── Thuần logic (không cần DB) ──

def test_legacy_bare_key_means_edit() -> None:
    """Bản ghi cũ chỉ có key trần → giữ nguyên quyền Sửa (không cần migration dữ liệu)."""
    caps = effective_caps("editor", ["physical", "inventory"])
    assert has_cap(caps, "physical", LEVEL_EDIT)
    assert has_cap(caps, "inventory", LEVEL_EDIT)


def test_view_level_grants_read_but_not_write() -> None:
    caps = effective_caps("editor", ["physical:view"])
    assert has_cap(caps, "physical", LEVEL_VIEW)
    assert not has_cap(caps, "physical", LEVEL_EDIT)


def test_missing_cap_grants_nothing() -> None:
    caps = effective_caps("editor", ["physical:view"])
    assert not has_cap(caps, "inventory", LEVEL_VIEW)


def test_admin_gets_every_cap_at_edit_level() -> None:
    caps = effective_caps("admin", None)
    assert all(has_cap(caps, k, LEVEL_EDIT) for k in caps)


def test_viewer_and_member_get_nothing() -> None:
    assert effective_caps("viewer", ["physical"]) == {}
    assert effective_caps("member", ["physical"]) == {}


def test_non_split_cap_ignores_view_suffix() -> None:
    """Màn phân tích chỉ 1 cấp — `assistant:view` vẫn là quyền đầy đủ."""
    assert "assistant" not in SPLIT_CAPS
    assert has_cap(effective_caps("editor", ["assistant:view"]), "assistant", LEVEL_EDIT)


def test_clean_caps_normalizes_and_drops_invalid() -> None:
    assert clean_caps(["bogus", "physical:nonsense", "physical:view"]) == ["physical:view"]
    assert clean_caps(["physical:view", "physical"]) == ["physical"]  # trùng key → giữ mức cao hơn
    assert parse_cap("not_a_cap") is None


# ── Qua HTTP (cần DB) ──

_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")


@pytest.fixture(autouse=True)
def _seed():
    if db_healthy():
        user_repo.seed_admin()


def _bearer(username: str, password: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@_db
def test_view_only_editor_reads_but_cannot_write() -> None:
    """Chuyên viên được cấp `inventory:view`: GET 200, POST/DELETE 403."""
    h = _bearer("admin", "admin")
    for u in ("cap_view", "cap_edit"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/users", json={"username": "cap_view", "password": "pass123",
                                    "role": "editor", "permissions": ["inventory:view"]}, headers=h)
    client.post("/api/users", json={"username": "cap_edit", "password": "pass123",
                                    "role": "editor", "permissions": ["inventory"]}, headers=h)
    vh, eh = _bearer("cap_view", "pass123"), _bearer("cap_edit", "pass123")
    today = date.today().isoformat()

    assert client.get("/api/inventory", headers=vh).status_code == 200
    assert client.post("/api/inventory", json={"as_of": today, "ton_kho": 10}, headers=vh).status_code == 403
    assert client.delete(f"/api/inventory/{today}", headers=vh).status_code == 403

    # Cùng mục ở mức Sửa thì ghi được → chứng minh 403 ở trên đến từ CẤP quyền, không phải lỗi khác.
    assert client.post("/api/inventory", json={"as_of": today, "ton_kho": 10}, headers=eh).status_code == 200
    client.delete(f"/api/inventory/{today}", headers=eh)

    for u in ("cap_view", "cap_edit"):
        client.delete(f"/api/users/{u}", headers=h)


@_db
def test_private_units_editor_adds_only_admin_deletes() -> None:
    """Danh mục đơn vị tư nhân (Mục 6 Báo giá): chuyên viên có quyền Báo giá THÊM được, không XOÁ
    được; chỉ-Xem không thêm được; admin xoá được."""
    h = _bearer("admin", "admin")
    for u in ("cap_pu_edit", "cap_pu_view"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/users", json={"username": "cap_pu_edit", "password": "pass123", "role": "editor",
                                    "permissions": ["market_quote"]}, headers=h)
    client.post("/api/users", json={"username": "cap_pu_view", "password": "pass123", "role": "editor",
                                    "permissions": ["market_quote:view"]}, headers=h)
    eh, vh = _bearer("cap_pu_edit", "pass123"), _bearer("cap_pu_view", "pass123")
    name = "_zz_cap Tư nhân thử"

    assert client.post("/api/market-quote/private-units", json={"name": name}, headers=vh).status_code == 403
    res = client.post("/api/market-quote/private-units", json={"name": name}, headers=eh)
    assert res.status_code == 200, res.text
    unit = next(u for u in res.json() if u["name"] == name)
    assert client.post("/api/market-quote/private-units", json={"name": name}, headers=eh).status_code == 400
    assert client.delete(f"/api/market-quote/private-units/{unit['id']}", headers=eh).status_code == 403
    res = client.delete(f"/api/market-quote/private-units/{unit['id']}", headers=h)
    assert res.status_code == 200 and all(u["id"] != unit["id"] for u in res.json())

    for u in ("cap_pu_edit", "cap_pu_view"):
        client.delete(f"/api/users/{u}", headers=h)


@_db
def test_quote_rejects_reversed_private_range() -> None:
    """Giá max nhỏ hơn Giá → 400, phiếu không lưu."""
    h = _bearer("admin", "admin")
    today = date.today().isoformat()
    client.delete(f"/api/market-quote/{today}", headers=h)
    body = {"as_of": today, "private_prices": {"_zz_cap ngược": {"price": 563, "price_max": 560}}}
    res = client.put("/api/market-quote", json=body, headers=h)
    assert res.status_code == 400 and "Giá max" in res.json()["detail"]
    assert client.get(f"/api/market-quote/{today}", headers=h).status_code == 404


@_db
def test_delete_quote_needs_market_quote_edit_not_raw_material() -> None:
    """Phiếu báo giá chỉ thuộc quyền `market_quote` → quyền `raw_material` không ghi/xoá được."""
    h = _bearer("admin", "admin")
    client.delete("/api/users/cap_del", headers=h)
    client.post("/api/users", json={"username": "cap_del", "password": "pass123", "role": "editor",
                                    "permissions": ["raw_material"]}, headers=h)
    dh = _bearer("cap_del", "pass123")
    today = date.today().isoformat()
    client.put("/api/market-quote", json={"as_of": today, "footer": "khong duoc xoa"}, headers=h)

    assert client.delete(f"/api/market-quote/{today}", headers=dh).status_code == 403
    assert client.put("/api/market-quote", json={"as_of": today, "footer": "x"}, headers=dh).status_code == 403
    assert client.get(f"/api/market-quote/{today}", headers=h).status_code == 200  # vẫn còn nguyên

    client.delete(f"/api/market-quote/{today}", headers=h)
    client.delete("/api/users/cap_del", headers=h)


@_db
def test_view_level_survives_round_trip_through_api() -> None:
    """Mức Xem lưu/đọc lại đúng qua /api/users (không bị clean_caps làm rơi)."""
    h = _bearer("admin", "admin")
    client.delete("/api/users/cap_rt", headers=h)
    client.post("/api/users", json={"username": "cap_rt", "password": "pass123", "role": "editor",
                                    "permissions": ["physical:view", "raw_material"]}, headers=h)
    got = next(u for u in client.get("/api/users", headers=h).json() if u["username"] == "cap_rt")
    assert set(got["permissions"]) == {"physical:view", "raw_material"}
    client.delete("/api/users/cap_rt", headers=h)
