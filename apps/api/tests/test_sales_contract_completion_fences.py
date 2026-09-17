"""Nút «Hoàn thành» của hợp đồng giao 1 lần phải qua đúng hai hàng rào thời gian (17/09/2026).

Chốt hoàn thành một hợp đồng giao 1 lần chưa có ngày giao = ghi luôn LẦN GIAO. Trước đây bước này
không kiểm gì: đặt cửa sổ sửa 0 ngày, đơn vị vẫn ghi được ngày giao lùi 10 ngày (tức ghi sản lượng
vào kỳ đã qua), kể cả kỳ đơn vị đã chốt số liệu.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import config_repo, data_lock_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_scf_unit"
MEMBER = "zz_scf_mem"
TODAY = date.today()
WINDOW_KEY = "MEMBER_EDIT_WINDOW_DAYS"


def _login(username: str, password: str) -> dict[str, str]:
    tok = client.post("/api/auth/login",
                      json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture()
def env():
    """Đơn vị + tài khoản nhập liệu + khách hàng; cửa sổ sửa của đơn vị = 0 (chỉ hôm nay)."""
    user_repo.seed_admin()
    admin = _login("admin", "admin")
    before_window = config_repo.get_value(WINDOW_KEY)
    client.post("/api/member-units", json={"name": UNIT}, headers=admin)
    client.delete(f"/api/users/{MEMBER}", headers=admin)
    client.post("/api/users", json={"username": MEMBER, "password": "pass123",
                                    "role": "member", "member_units": [UNIT]}, headers=admin)
    config_repo.set_config({WINDOW_KEY: "0"}, "test")
    member = _login(MEMBER, "pass123")
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH hoàn thành"},
                     headers=member).json()["id"]
    yield {"admin": admin, "member": member, "cus": cus}
    config_repo.set_config({WINDOW_KEY: before_window if before_window else "__CLEAR__"}, "test")
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = :u"), {"u": UNIT})
        db.execute(text("DELETE FROM unit_customer WHERE company = :u"), {"u": UNIT})
    client.delete(f"/api/users/{MEMBER}", headers=admin)
    client.delete(f"/api/member-units/{UNIT}", headers=admin)


def _single_contract(env, code: str, sign_days_ago: int = 30) -> int:
    """Hợp đồng giao 1 lần, CHƯA có ngày giao — ký từ lâu vẫn nhập được (cửa sổ không soi ngày ký)."""
    r = client.put("/api/sales-contracts", headers=env["member"], json={
        "company": UNIT, "code": code, "customer_id": env["cus"], "contract_type": "spot",
        "delivery_type": "single", "sign_date": (TODAY - timedelta(days=sign_days_ago)).isoformat(),
        "lines": [{"grade": "SVR 3L", "qty": 40.0, "price": 42.0, "ccy": "VND"}]})
    assert r.status_code == 200, r.text
    return r.json()["contract"]["id"]


def _complete(env, cid: int, day: date, headers_key: str = "member"):
    return client.put(f"/api/sales-contracts/{cid}/completion", headers=env[headers_key],
                      json={"completed_at": day.isoformat(), "channel": "domestic"})


def test_hoan_thanh_voi_ngay_giao_lui_bi_cua_so_chan(env) -> None:
    cid = _single_contract(env, "HD-SCF-LUI")
    late = _complete(env, cid, TODAY - timedelta(days=10))
    assert late.status_code == 403, late.text
    assert late.headers.get("X-Edit-Blocked") == "window"       # web mời gửi «Đề nghị sửa»
    got = client.get(f"/api/sales-contracts/{cid}", headers=env["member"]).json()
    assert got["contract"]["delivered_at"] is None               # KHÔNG ghi lần giao nào
    assert got["contract"]["completed_at"] is None               # và cũng không chốt nửa vời

    ok = _complete(env, cid, TODAY)                               # đúng hôm nay thì vẫn chốt được
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract"]["delivered_at"] == TODAY.isoformat()


def test_hoan_thanh_vao_ky_da_chot_bi_chan(env) -> None:
    """Cửa sổ rộng nhưng kỳ đã chốt → vẫn chặn (hàng rào thứ hai)."""
    config_repo.set_config({WINDOW_KEY: "30"}, "test")
    cid = _single_contract(env, "HD-SCF-CHOT")
    locked_day = TODAY - timedelta(days=5)
    rnd = data_lock_repo.save_round(locked_day.isoformat(), "ZZ SCF", "admin")
    data_lock_repo.confirm(rnd["id"], UNIT, MEMBER)
    try:
        blocked = _complete(env, cid, locked_day - timedelta(days=1))
        assert blocked.status_code == 403, blocked.text
        assert blocked.headers.get("X-Edit-Blocked") == "lock"
        after_lock = _complete(env, cid, locked_day + timedelta(days=1))   # sau ngày chốt: được
        assert after_lock.status_code == 200, after_lock.text
    finally:
        data_lock_repo.delete_round(rnd["id"])


def test_quan_tri_khong_bi_chan_va_huy_hop_dong_khong_ghi_lan_giao(env) -> None:
    cid = _single_contract(env, "HD-SCF-ADMIN")
    assert _complete(env, cid, TODAY - timedelta(days=10), "admin").status_code == 200

    cancelled = _single_contract(env, "HD-SCF-HUY")
    r = client.put(f"/api/sales-contracts/{cancelled}/completion", headers=env["member"],
                   json={"completed_at": TODAY.isoformat(), "no_delivery": True})
    assert r.status_code == 200, r.text
    assert r.json()["contract"]["delivered_at"] is None
