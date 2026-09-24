"""Cửa sổ nhập liệu qua API: hạn = giờ chốt (mặc định 11:00) của ngày D + N; admin miễn, admin đổi được N và giờ chốt."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import config_repo, user_repo
from tests.edit_window_clock import pin_clock, restored_window_config, window_config

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
    """Xoá N + giờ chốt → hệ thống dùng mặc định (7 · 7 · 11), bất kể DB đang cấu hình gì."""
    client.put("/api/config", json={"EDITOR_EDIT_WINDOW_DAYS": "__CLEAR__", "MEMBER_EDIT_WINDOW_DAYS": "__CLEAR__",
                                    "EDIT_CUTOFF_HOUR": "__CLEAR__"}, headers=h)


@pytest.fixture()
def keep_config():
    """Trả lại N + giờ chốt ĐANG LƯU sau test (test đổi cấu hình không được để lại dấu)."""
    with restored_window_config():
        yield


def test_editor_window_enforced_admin_exempt_configurable(keep_config) -> None:
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
    assert s["cutoff_hour"] == 11 and s["editor_editable_from"] <= today

    # Chuyên viên: hôm nay OK, ngày cũ (30 ngày) → 403 (ngoài cửa sổ)
    assert client.put("/api/prices/records", json=_rec(today), headers=eh).status_code == 200
    assert client.put("/api/prices/records", json=_rec(old), headers=eh).status_code == 403

    # Admin: ngày cũ vẫn ghi được (miễn cửa sổ)
    assert client.put("/api/prices/records", json=_rec(old), headers=h).status_code == 200

    # Admin nới cửa sổ chuyên viên lên 60 ngày → chuyên viên ghi được ngày cũ
    assert client.put("/api/config", json={"EDITOR_EDIT_WINDOW_DAYS": "60"}, headers=h).status_code == 200
    assert client.get("/api/settings/edit-windows", headers=eh).json()["editor_days"] == 60
    assert client.put("/api/prices/records", json=_rec(old), headers=eh).status_code == 200

    # Dọn: xoá bản ghi test + xoá user (cấu hình cũ do `keep_config` trả lại)
    for d in (today, old):
        client.delete(
            f"/api/prices/records?as_of={d}&source=vrg&grade={_GRADE}&contract=&price_type=purchase", headers=h)
    client.delete("/api/users/win_ed", headers=h)


# ── Giờ chốt qua API (đồng hồ ghim) ────────────────────────────────────────────────────────────
UNIT = "_zz_cutoff_unit"
MEMBER, EDITOR = "zz_cutoff_mem", "zz_cutoff_ed"
def _cleanup_cutoff(h: dict[str, str]) -> None:
    for u in (MEMBER, EDITOR):
        client.delete(f"/api/users/{u}", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :u"), {"u": UNIT})
    client.delete(f"/api/member-units/{UNIT}", headers=h)


@pytest.fixture()
def env():
    user_repo.seed_admin()
    h = _admin_headers()
    _cleanup_cutoff(h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    client.post("/api/users", headers=h, json={"username": MEMBER, "password": "pass123",
                                               "role": "member", "member_units": [UNIT]})
    client.post("/api/users", headers=h, json={"username": EDITOR, "password": "pass123",
                                               "role": "editor", "permissions": ["unit_daily"]})
    try:
        with window_config():   # nền tường minh 7 · 7 · 11:00 — từng test tự đổi phần mình cần
            yield {"admin": h, "mem": _bearer(MEMBER, "pass123"), "ed": _bearer(EDITOR, "pass123")}
    finally:
        _cleanup_cutoff(h)


def _report(as_of: date, kind: str = "consumption") -> dict:
    fields = {"stock_material": 5} if kind == "consumption" else {"latex_wet": 1}
    return {"kind": kind, "company": UNIT, "as_of": as_of.isoformat(), "fields": fields}


def _put_member(env, as_of: date, kind: str = "consumption"):
    return client.put("/api/member/daily-report", json=_report(as_of, kind), headers=env["mem"])


def test_window_zero_closes_today_at_cutoff(env, monkeypatch) -> None:
    config_repo.set_config({"MEMBER_EDIT_WINDOW_DAYS": "0", "EDITOR_EDIT_WINDOW_DAYS": "0"}, "test")
    today = pin_clock(monkeypatch, 10, 59).date()
    for kind in ("purchase", "consumption"):
        assert _put_member(env, today, kind).status_code == 200
    s = client.get("/api/settings/edit-windows", headers=env["mem"]).json()
    assert s["member_editable_from"] == today.isoformat()
    # Mốc đổi kế tiếp = giờ chốt hôm nay (web hẹn giờ tải lại đúng lúc này).
    assert s["next_change_at"] == f"{today.isoformat()}T11:00:00+07:00"

    pin_clock(monkeypatch, 11, 0, today)
    res = _put_member(env, today)
    assert res.status_code == 403 and res.headers.get("X-Edit-Blocked") == "window"
    assert "đến 11:00 cùng ngày" in res.json()["detail"]
    s = client.get("/api/settings/edit-windows", headers=env["mem"]).json()
    assert s["member_editable_from"] == (today + timedelta(days=1)).isoformat()   # > hôm nay
    assert s["next_change_at"] == f"{(today + timedelta(days=1)).isoformat()}T11:00:00+07:00"
    day = client.get(f"/api/member/daily-report?kind=purchase&as_of={today}", headers=env["mem"]).json()
    assert day["editable_from"] == s["member_editable_from"] and day["edit_window_days"] == 0

    # Chuyên viên cùng luật; admin miễn.
    ed = client.put("/api/unit-daily/report", json=_report(today), headers=env["ed"])
    assert ed.status_code == 403 and ed.headers.get("X-Edit-Blocked") == "window"
    old = today - timedelta(days=30)
    assert client.put("/api/unit-daily/report", json=_report(old), headers=env["admin"]).status_code == 200


def test_window_one_keeps_yesterday_until_cutoff(env, monkeypatch) -> None:
    config_repo.set_config({"MEMBER_EDIT_WINDOW_DAYS": "1"}, "test")
    today = pin_clock(monkeypatch, 10, 59).date()
    yesterday = today - timedelta(days=1)
    assert _put_member(env, yesterday).status_code == 200
    assert _put_member(env, yesterday - timedelta(days=1)).status_code == 403
    pin_clock(monkeypatch, 11, 0, today)
    assert _put_member(env, yesterday).status_code == 403
    assert _put_member(env, today).status_code == 200
    chk = client.get("/api/member/checklist", headers=env["mem"]).json()
    assert chk["editable_from"] == today.isoformat()
    assert "purchase_editable_from" not in chk and "stock_editable_from" not in chk


def test_admin_moves_the_cutoff_hour(env, monkeypatch) -> None:
    config_repo.set_config({"MEMBER_EDIT_WINDOW_DAYS": "0", "EDIT_CUTOFF_HOUR": "15"}, "test")
    today = pin_clock(monkeypatch, 14, 59).date()
    assert _put_member(env, today).status_code == 200
    assert client.get("/api/settings/edit-windows", headers=env["mem"]).json()["cutoff_hour"] == 15
    pin_clock(monkeypatch, 15, 0, today)
    res = _put_member(env, today)
    assert res.status_code == 403 and "đến 15:00 cùng ngày" in res.json()["detail"]
