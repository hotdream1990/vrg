"""Phân quyền các endpoint MỚI của Báo cáo tuần v2 (nguồn tham khảo · đính kèm · chỉ số · tin).

`bulletin_weekly` là quyền 1 cấp (có = xem + thao tác). Người CHỈ XEM màn này là Lãnh đạo Tập đoàn
(role executive): ĐỌC được mọi thứ nhưng mọi thao tác ghi mới (nguồn, đính kèm, lưu, AI) phải bị chặn.
Tài khoản không được cấp quyền thì chặn cả đọc. Mọi request ghi dưới đây dừng ở
tầng phân quyền (403) nên không để lại dữ liệu.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import user_repo

client = TestClient(app)
_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

WEEK = "2099-01-05"  # tuần giả ở tương lai xa — không đụng báo cáo thật
_EXEC, _NONE = "_zz_weekly_exec", "_zz_weekly_none"


def _bearer(username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def users():
    user_repo.seed_admin()
    admin = _bearer("admin", "admin")
    for u, role, perms in ((_EXEC, "executive", []), (_NONE, "editor", ["inventory"])):
        client.delete(f"/api/users/{u}", headers=admin)
        r = client.post("/api/users", headers=admin, json={
            "username": u, "password": "pass123", "role": role, "permissions": perms})
        assert r.status_code == 200, r.text
    yield {"exec": _bearer(_EXEC, "pass123"), "none": _bearer(_NONE, "pass123")}
    for u in (_EXEC, _NONE):
        client.delete(f"/api/users/{u}", headers=admin)


_READS = [
    "/api/weekly-sources",
    "/api/weekly-sources/meta",
    f"/api/weekly-reports/{WEEK}/attachments",
    f"/api/weekly-reports/{WEEK}/check",   # soát lệch dữ liệu — chỉ đọc, người chỉ xem cũng dùng được
]
_WRITES = [
    ("post", "/api/weekly-sources", {"json": {"category": "macro", "name": "x", "mode": "manual"}}),
    ("put", "/api/weekly-sources/1", {"json": {"name": "x"}}),
    ("delete", "/api/weekly-sources/1", {}),
    ("post", "/api/weekly-sources/reset-defaults", {}),
    ("post", f"/api/weekly-reports/{WEEK}/attachments",
     {"files": {"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}}),
    ("patch", f"/api/weekly-reports/{WEEK}/attachments/1", {"json": {"kind": "other"}}),
    ("delete", f"/api/weekly-reports/{WEEK}/attachments/1", {}),
    ("post", f"/api/weekly-reports/{WEEK}/attachments/1/summarize", {}),
    ("put", f"/api/weekly-reports/{WEEK}", {"json": {"span_weeks": 2}}),
    ("delete", f"/api/weekly-reports/{WEEK}", {}),
    ("post", f"/api/weekly-reports/{WEEK}/ai-assist-all", {}),
]


@_db
def test_executive_reads_but_cannot_write(users) -> None:
    h = users["exec"]
    for path in _READS:
        assert client.get(path, headers=h).status_code == 200, path
    for method, path, kw in _WRITES:
        r = getattr(client, method)(path, headers=h, **kw)
        assert r.status_code == 403, f"{method.upper()} {path} → {r.status_code}"


@_db
def test_without_cap_blocks_reads_too(users) -> None:
    h = users["none"]
    for path in _READS:
        assert client.get(path, headers=h).status_code == 403, path


# ── Chặn SSRF: server chỉ tự mở trang của vietnambiz.vn ──
def test_vietnambiz_host_allowlist() -> None:
    from app.services.weekly_source_repo import clean_source, is_vietnambiz_url

    assert is_vietnambiz_url("https://vietnambiz.vn/gia-cao-su.html")
    assert is_vietnambiz_url("https://www.vietnambiz.vn/gia-cao-su/trang-2.html")
    for bad in ("http://127.0.0.1:8390/api", "https://vietnambiz.vn.evil.com/x", "file:///etc/passwd",
                "https://evil.com/?u=https://vietnambiz.vn", "http://169.254.169.254/latest/meta-data"):
        assert not is_vietnambiz_url(bad), bad
    with pytest.raises(ValueError):
        clean_source({"category": "news", "name": "x", "mode": "vietnambiz", "url": "http://10.0.0.5/"})


def test_news_fetch_refuses_foreign_host_without_network() -> None:
    from app.services import weekly_news

    with pytest.raises(ValueError):
        weekly_news._get("http://127.0.0.1:1/gia-cao-su-hom-nay-x.htm")
