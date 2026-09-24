"""Link công khai `/nhap-gia-mu` chịu CÙNG hàng rào với tài khoản đơn vị (`PUT /api/member/prices`).

Trước đây link này luôn ghi được giá hôm nay. Từ khi hạn nhập tính tới giờ chốt (24/09/2026), N = 0
mà qua 11:00 thì tài khoản đơn vị bị chặn — link công khai không được thành đường lách luật đó, và
cũng phải tôn trọng mốc chốt số liệu của đơn vị.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import config_repo, data_lock_repo, user_repo
from tests.edit_window_clock import pin_clock, window_config

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_public_win_unit"
PW_KEY = "PUBLIC_PURCHASE_PASSWORD"
PW = "zz-public-win-pass"


def _wipe() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM fact_price WHERE grade = :g"), {"g": UNIT})


@pytest.fixture()
def env():
    """1 đơn vị + mật khẩu link công khai; trả lại mật khẩu + cửa sổ cũ sau test."""
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    old_pw = config_repo.get_value(PW_KEY)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    config_repo.set_config({PW_KEY: PW}, "test")
    _wipe()
    try:
        yield h
    finally:
        config_repo.set_config({PW_KEY: old_pw or "__CLEAR__"}, "test")
        _wipe()
        client.delete(f"/api/member-units/{UNIT}", headers=h)


def _auth() -> dict:
    res = client.post("/api/public/purchase/auth", json={"password": PW})
    assert res.status_code == 200, res.text
    return res.json()


def _submit(token: str, price: float = 540):
    return client.post("/api/public/purchase", json={"company": UNIT, "price": price},
                       headers={"Authorization": f"Bearer {token}"})


def test_public_link_closes_today_at_the_cutoff(env, monkeypatch) -> None:
    """N = 0: trước 11:00 gửi được; từ 11:00 bị chặn như tài khoản đơn vị, trang biết trước qua `closed`."""
    with window_config(member=0):
        pin_clock(monkeypatch, 10, 59)
        auth = _auth()
        assert auth["closed"] is None
        assert _submit(auth["token"]).status_code == 200

        today = pin_clock(monkeypatch, 11, 0).date()
        auth = _auth()
        assert auth["today"] == today.isoformat()
        assert "đến 11:00 cùng ngày" in auth["closed"]
        res = _submit(auth["token"], 550)
        assert res.status_code == 403 and res.headers.get("X-Edit-Blocked") == "window"
        assert res.json()["detail"] == auth["closed"]           # trang báo trước đúng câu server chặn

    recent = client.post("/api/public/purchase/recent", json={"company": UNIT},
                         headers={"Authorization": f"Bearer {auth['token']}"}).json()["records"]
    assert [r["price"] for r in recent] == [540]                 # giá gửi sau giờ chốt KHÔNG được ghi


def test_public_link_respects_the_unit_data_lock(env, monkeypatch) -> None:
    """Cửa sổ còn mở nhưng đơn vị đã chốt số liệu tới hôm nay → link công khai cũng bị chặn."""
    with window_config():
        today = pin_clock(monkeypatch, 9).date()
        rnd = data_lock_repo.save_round(today.isoformat(), "ZZ public", "admin")
        data_lock_repo.confirm(rnd["id"], UNIT, "admin")
        try:
            auth = _auth()
            assert auth["closed"] is None                        # chốt tính theo đơn vị, chưa biết lúc vào trang
            res = _submit(auth["token"])
            assert res.status_code == 403 and res.headers.get("X-Edit-Blocked") == "lock"
        finally:
            data_lock_repo.delete_round(rnd["id"])
