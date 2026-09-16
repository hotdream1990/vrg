"""Môi trường dùng chung cho test «Đề nghị sửa số liệu quá khứ» (fixture `env` + helper gọi API).

Không phải file test (không có tiền tố `test_`). DB dev dùng chung/bản sao prod: mọi dữ liệu mang tiền
tố `_zz_er_`, dọn trước và sau mỗi test; cấu hình cửa sổ sửa trả lại giá trị cũ.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import session_scope
from app.main import app
from app.services import config_repo, mailer, member_unit_repo, user_repo

client = TestClient(app)
UNIT, OTHER = "_zz_er_unit", "_zz_er_other"
USERS = {"member": ("member", [UNIT], []), "leader": ("leader", [UNIT], []),
         "editor": ("editor", [], ["edit_request"]), "none": ("editor", [], ["unit_daily"])}
TODAY = date.today()
OLD = (TODAY - timedelta(days=10)).isoformat()          # ngoài cửa sổ 3 ngày
RECENT = TODAY.isoformat()
NOTE = "ZZ EDIT REQUEST TEST"
KEY = "MEMBER_EDIT_WINDOW_DAYS"


def login(u: str, p: str = "pass123") -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _cleanup(h: dict[str, str]) -> None:
    for name in USERS:
        client.delete(f"/api/users/_zz_er_{name}", headers=h)
    with session_scope() as db:
        for tbl in ("edit_request", "unit_daily_report", "market_demand", "sales_contract",
                    "unit_customer", "unit_data_lock"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": [UNIT, OTHER]})
        db.execute(text("DELETE FROM fact_price WHERE grade = :u"), {"u": UNIT})
        db.execute(text("DELETE FROM data_lock_round WHERE note = :n"), {"n": NOTE})
    for u in (UNIT, OTHER):
        member_unit_repo.delete_unit(u)


@pytest.fixture()
def env(monkeypatch):
    user_repo.seed_admin()
    h = login("admin", "admin")
    _cleanup(h)
    for u in (UNIT, OTHER):
        member_unit_repo.add_unit(u)
    for name, (role, units, perms) in USERS.items():
        client.post("/api/users", headers=h, json={"username": f"_zz_er_{name}", "password": "pass123",
                                                   "role": role, "member_units": units, "permissions": perms,
                                                   "email": f"zz_er_{name}@example.invalid"})
    old_window = config_repo.get_value(KEY)
    client.put("/api/config", json={KEY: "3"}, headers=h)
    mails: list[tuple] = []
    monkeypatch.setattr(mailer, "send_async", lambda to, subject, body: mails.append((to, subject)))
    try:
        yield {"admin": h, "mails": mails, **{n: login(f"_zz_er_{n}") for n in USERS}}
    finally:
        client.put("/api/config", json={KEY: old_window or "__CLEAR__"}, headers=h)
        _cleanup(h)


def send(hdr, op: str, payload: dict, reason: str = "Nhập nhầm số liệu"):
    return client.post("/api/member/edit-requests", headers=hdr,
                       json={"op": op, "payload": payload, "reason": reason})


def lock_round(h, lock_date: str, company: str = UNIT) -> int:
    rid = client.put("/api/data-lock/rounds", headers=h,
                     json={"lock_date": lock_date, "note": NOTE}).json()["round"]["id"]
    client.post("/api/data-lock/lock", headers=h, json={"round_id": rid, "companies": [company]})
    return rid


def seen_at(hdr, rid: int) -> str:
    """`updated_at` người duyệt đang thấy (đúng thứ màn chi tiết gửi lại khi bấm Duyệt/Từ chối)."""
    return client.get(f"/api/edit-requests/{rid}", headers=hdr).json()["request"]["updated_at"]


def approve(hdr, rid: int, **body):
    return client.post(f"/api/edit-requests/{rid}/approve", headers=hdr,
                       json={"expected_updated_at": seen_at(hdr, rid), **body})


def reject(hdr, rid: int, note: str):
    return client.post(f"/api/edit-requests/{rid}/reject", headers=hdr,
                       json={"note": note, "expected_updated_at": seen_at(hdr, rid)})
