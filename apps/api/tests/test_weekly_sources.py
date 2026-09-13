"""Test danh mục nguồn tham khảo Báo cáo tuần: kiểm hợp lệ (thuần) + CRUD repo/API (DB dev, tự dọn)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.services import user_repo, weekly_source_repo as repo
from app.services.weekly_source_defaults import DEFAULT_SOURCES, MODES, SECTIONS, meta

_OK = {"category": "financial", "name": "  Chỉ số   DXY ", "mode": "market_feed", "feed_symbol": "DX-Y.NYB",
       "url": "https://vn.investing.com/indices/usdollar", "sections": ["IV.3", "III.1", "IV.3"]}


def test_clean_source_normalizes_valid_input() -> None:
    src = repo.clean_source(_OK)
    assert src["name"] == "Chỉ số DXY"
    assert src["sections"] == ["III.1", "IV.3"]  # bỏ trùng, theo thứ tự báo cáo
    assert src["feed_symbol"] == "DX-Y.NYB" and src["enabled"] is True


@pytest.mark.parametrize("patch, msg", [
    ({"category": "stock"}, "Nhóm nguồn"),
    ({"mode": "rss"}, "Cách dùng"),
    ({"name": "   "}, "tên nguồn"),
    ({"name": "x" * 201}, "200 ký tự"),
    ({"url": "ftp://example.com"}, "http"),
    ({"url": "javascript:alert(1)"}, "http"),
    ({"sections": ["IV.9"]}, "Mục báo cáo"),
    ({"feed_symbol": ""}, "phải có mã"),
    ({"feed_symbol": "DX Y;drop"}, "Mã số liệu"),
    ({"feed_symbol": "A" * 21}, "Mã số liệu"),
])
def test_clean_source_rejects_invalid(patch: dict, msg: str) -> None:
    with pytest.raises(ValueError, match=msg):
        repo.clean_source({**_OK, **patch})


def test_defaults_are_valid_and_cover_logic_sources() -> None:
    assert len(DEFAULT_SOURCES) >= 14
    cleaned = [repo.clean_source(s) for s in DEFAULT_SOURCES]
    symbols = {s["feed_symbol"] for s in cleaned if s["mode"] == "market_feed"}
    assert symbols == {"DX-Y.NYB", "CL=F", "BZ=F"}
    vb = next(s for s in cleaned if s["mode"] == "vietnambiz")
    assert "tháng 12" in vb["guide"] and "Bước 4" in vb["guide"]
    anrpc = next(s for s in cleaned if s["mode"] == "attachment")
    assert "Short-term Market Outlook" in anrpc["guide"] and "IV.2" in anrpc["sections"]
    by_name = {s["name"]: s["sections"] for s in cleaned}
    assert by_name["Giá dầu thô WTI"] == by_name["Giá dầu Brent"] == ["IV.1"]
    assert by_name["Chỉ số DXY"] == ["IV.3"] and by_name["Tỷ giá USD/JPY"] == ["III.1", "IV.3"]
    assert vb["sections"] == ["I", "II", "III.1", "IV.1", "IV.4"]
    m = meta()
    assert [x["value"] for x in m["modes"]] == list(MODES)
    assert [x["value"] for x in m["sections"]] == list(SECTIONS)


needs_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")


@needs_db
def test_repo_crud_and_section_filter() -> None:
    created = repo.create_source({**_OK, "name": "_zz_test_weekly_source"}, "pytest")
    try:
        assert created["id"] and created["updated_by"] == "pytest"
        assert any(s["id"] == created["id"] for s in repo.sources_for_section("IV.3"))
        upd = repo.update_source(created["id"], {"enabled": False, "sections": ["IV.2"]}, "pytest")
        assert upd["enabled"] is False and upd["sections"] == ["IV.2"] and upd["feed_symbol"] == "DX-Y.NYB"
        assert all(s["id"] != created["id"] for s in repo.sources_for_section("IV.2"))  # đang tắt
        assert all(s["id"] != created["id"] for s in repo.list_sources(enabled_only=True))
        with pytest.raises(ValueError):
            repo.update_source(created["id"], {"feed_symbol": None}, "pytest")  # market_feed thiếu mã
        assert repo.update_source(999_999_999, {"name": "x"}, "pytest") is None
    finally:
        assert repo.delete_source(created["id"]) is True
    assert repo.get_source(created["id"]) is None and repo.delete_source(created["id"]) is False


@needs_db
def test_api_sources_endpoints() -> None:
    from app.main import app

    client = TestClient(app)
    user_repo.seed_admin()
    token = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    lst = client.get("/api/weekly-sources", headers=h)
    assert lst.status_code == 200 and len(lst.json()) >= 1
    assert {"categories", "modes", "sections"} <= set(client.get("/api/weekly-sources/meta", headers=h).json())
    bad = client.post("/api/weekly-sources", json={**_OK, "url": "abc"}, headers=h)
    assert bad.status_code == 400
    r = client.post("/api/weekly-sources", json={**_OK, "name": "_zz_test_api_source"}, headers=h)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    try:
        p = client.put(f"/api/weekly-sources/{sid}", json={"role": "Vai trò test"}, headers=h)
        assert p.status_code == 200 and p.json()["role"] == "Vai trò test"
        assert client.put("/api/weekly-sources/999999999", json={"role": "x"}, headers=h).status_code == 404
    finally:
        assert client.delete(f"/api/weekly-sources/{sid}", headers=h).status_code == 200
    assert client.get("/api/weekly-sources").status_code == 401
