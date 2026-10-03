"""Kế hoạch năm CHỐT CÙNG ĐỢT chốt số liệu + «Đề nghị sửa» kế hoạch năm (03/10/2026).

Đơn vị xác nhận chốt đến hết ngày X ⇒ kế hoạch năm ≤ năm của X khoá với đơn vị; muốn đổi gửi đề nghị
`year_plan`, Ban duyệt thì ghi + gỡ chốt các đợt của ĐÚNG năm đó."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.data_lock import plan_locked
from tests import edit_request_env
from tests.edit_request_env import OLD, UNIT, approve, client, lock_round, send

env = edit_request_env.env   # fixture dùng chung

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
YEAR = int(OLD[:4])
PREV_YEAR_END = f"{YEAR - 1}-12-31"


@pytest.fixture(autouse=True)
def _clean_plans():
    yield
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :u"), {"u": UNIT})


def _put(hdr, year: int = YEAR, **values):
    return client.put("/api/member/plan", headers=hdr, json={"year": year, "company": UNIT, **values})


def _plan(hdr, year: int = YEAR) -> dict:
    return client.get(f"/api/member/plan?year={year}", headers=hdr).json()


def test_plan_lock_rule() -> None:
    assert not plan_locked(None, 2026)
    assert plan_locked(date(2026, 1, 5), 2026) and plan_locked(date(2027, 3, 1), 2026)
    assert not plan_locked(date(2025, 12, 31), 2026)          # kế hoạch năm mới mở tới đợt đầu năm đó


def test_plan_locks_with_the_round_and_edit_request_unlocks_that_year(env) -> None:
    e = env
    assert _put(e["member"], plan_tonnes=100).status_code == 200
    assert _plan(e["member"])["locked"][UNIT] is False
    rid = client.put("/api/data-lock/rounds", headers=e["admin"],
                     json={"lock_date": OLD, "note": "ZZ EDIT REQUEST TEST"}).json()["round"]["id"]
    # Bảng số liệu sẽ chốt bày cả kế hoạch năm — đơn vị rà chỉ tiêu trước khi bấm.
    summ = client.get(f"/api/data-lock/summary?company={UNIT}&round_id={rid}", headers=e["member"]).json()
    assert summ["plan"]["year"] == YEAR and summ["plan"]["values"]["plan_tonnes"] == 100
    assert client.post("/api/data-lock/confirm", headers=e["member"],
                       json={"round_id": rid, "company": UNIT}).status_code == 200
    plan = _plan(e["member"])
    assert plan["locked"][UNIT] is True and plan["locked_until"][UNIT] == OLD
    r = _put(e["member"], plan_tonnes=120)
    assert r.status_code == 403 and r.headers.get("x-edit-blocked") == "lock"
    assert f"Kế hoạch năm {YEAR}" in r.json()["detail"] and "Đề nghị sửa" in r.json()["detail"]
    assert _put(e["member"], year=YEAR + 1, plan_tonnes=50).status_code == 200   # năm sau chưa chốt
    assert client.put("/api/unit-daily/plan", headers=e["admin"],             # Ban vẫn sửa được
                      json={"year": YEAR, "company": UNIT, "plan_goods_tonnes": 7}).status_code == 200

    res = send(e["member"], "year_plan", {"year": YEAR, "company": UNIT, "plan_tonnes": 120},
               reason="Tổng giám đốc giao lại chỉ tiêu")
    assert res.status_code == 200, res.text
    req = res.json()["request"]
    assert req["op_label"] == "Kế hoạch năm" and req["title"] == f"Kế hoạch năm {YEAR}"
    assert req["dates"] == [f"{YEAR}-01-01"] and req["blocked"] and req["before"]["plan_tonnes"] == 100
    detail = client.get(f"/api/edit-requests/{req['id']}", headers=e["editor"]).json()
    assert [w["round_id"] for w in detail["lock"]["will_unlock"]] == [rid]
    assert detail["changed_since_submit"] is False
    ok = approve(e["editor"], req["id"])
    assert ok.status_code == 200, ok.text
    assert _plan(e["member"])["plans"][UNIT]["plan_tonnes"] == 120
    assert _plan(e["member"])["plans"][UNIT]["plan_goods_tonnes"] == 7      # ô không đề nghị giữ nguyên
    assert _plan(e["member"])["locked"][UNIT] is False                      # gỡ chốt → rà, chốt lại
    assert [u["round_id"] for u in ok.json()["request"]["unlocked"]] == [rid]


def test_plan_request_needs_lock_entry_types_and_unlocks_only_its_year(env) -> None:
    e = env
    body = {"year": YEAR, "company": UNIT, "plan_tonnes": 1, "plan_revenue_ty": 5}
    r = send(e["member"], "year_plan", body)
    assert r.status_code == 409 and "sửa trực tiếp" in r.json()["detail"]   # chưa chốt → sửa thẳng
    this_year = lock_round(e["admin"], OLD)
    last_year = lock_round(e["admin"], PREV_YEAR_END)
    # Tài khoản chỉ được giao Thu mua: ô doanh thu (Hợp đồng & tiêu thụ) bị bỏ khỏi đề nghị.
    assert client.put("/api/users/_zz_er_member", headers=e["admin"],
                      json={"entry_types": ["purchase"]}).status_code == 200
    req = send(e["member"], "year_plan", body).json()["request"]
    assert set(req["payload"]) == {"year", "company", "plan_tonnes"}
    assert send(e["member"], "year_plan", {"year": YEAR, "company": UNIT, "plan_revenue_ty": 5}).status_code == 403
    # Đề nghị kế hoạch năm trước chỉ gỡ đợt của năm trước — đợt năm nay giữ nguyên.
    prev = send(e["member"], "year_plan", {"year": YEAR - 1, "company": UNIT, "plan_tonnes": 3}).json()["request"]
    will = client.get(f"/api/edit-requests/{prev['id']}", headers=e["editor"]).json()["lock"]["will_unlock"]
    assert [w["round_id"] for w in will] == [last_year]
    will = client.get(f"/api/edit-requests/{req['id']}", headers=e["editor"]).json()["lock"]["will_unlock"]
    assert [w["round_id"] for w in will] == [this_year]
    assert client.post(f"/api/member/edit-requests/{req['id']}/cancel", headers=e["member"]).status_code == 200
