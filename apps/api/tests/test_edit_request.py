"""«Đề nghị sửa số liệu quá khứ»: đơn vị gửi → số liệu CHƯA đổi → Ban duyệt mới ghi thật + gỡ chốt."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.db import db_healthy
from app.services import (
    data_lock_repo, market_demand_item_repo, sales_contract_repo, unit_daily_repo, unit_purchase_price,
)
from app.services.edit_request_ops_daily import _day_fields, _unit_prices
from tests import edit_request_env
from tests.edit_request_env import (
    OLD, OTHER, RECENT, TODAY, UNIT, approve, client, demand, lock_round, reject, seed_demand, send,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung


def test_daily_report_submit_review_and_unlock(env) -> None:
    e = env
    unit_daily_repo.upsert("purchase", OLD, UNIT, {"latex_wet": 1}, "admin")
    unit_purchase_price.save(UNIT, OLD, "purchase_cup", 200)
    direct = client.put("/api/member/daily-report", headers=e["member"], json={
        "kind": "purchase", "company": UNIT, "as_of": OLD, "fields": {"latex_wet": 5}})
    assert direct.status_code == 403 and direct.headers.get("X-Edit-Blocked") == "window"

    payload = {"kind": "purchase", "company": UNIT, "as_of": OLD, "fields": {"latex_wet": 5},
               "prices": {"purchase": 350, "purchase_cup": 0}}
    assert send(e["member"], "daily_report", payload, "  ").status_code == 400
    assert send(e["member"], "bogus", payload).status_code == 400
    assert send(e["member"], "daily_report", {**payload, "company": OTHER}).status_code == 403
    assert send(e["member"], "daily_report", {**payload, "as_of": RECENT}).status_code == 409
    assert send(e["leader"], "daily_report", payload).status_code == 403
    first = send(e["member"], "daily_report", payload)
    assert first.status_code == 200, first.text
    req = first.json()["request"]
    assert first.json()["replaced"] is False and req["status"] == "pending" and req["blocked"]
    assert req["before"]["fields"] == {"latex_wet": 1.0} and req["title"] == f"Biểu Thu mua ngày {OLD[8:]}/{OLD[5:7]}/{OLD[:4]}"
    assert _day_fields("purchase", OLD, UNIT) == {"latex_wet": 1.0}       # số liệu CHƯA đổi
    again = send(e["member"], "daily_report", payload, "Sửa lại lý do cho rõ")
    assert again.json()["replaced"] is True and again.json()["request"]["id"] == req["id"]
    assert len(e["mails"]) == 2 and "zz_er_editor@example.invalid" in e["mails"][0][0]

    assert client.get("/api/edit-requests", headers=e["none"]).status_code == 403
    listed = client.get("/api/edit-requests", headers=e["editor"], params={"q": UNIT}).json()
    assert [r["id"] for r in listed["items"]] == [req["id"]] and listed["counts"]["pending"] == 1
    assert client.get("/api/edit-requests/pending-count", headers=e["editor"]).json()["count"] >= 1

    older = (TODAY - timedelta(days=11)).isoformat()        # đợt cũ hơn ngày sửa → giữ nguyên
    yday = (TODAY - timedelta(days=1)).isoformat()
    keep, drop = lock_round(e["admin"], older), lock_round(e["admin"], yday)
    locked = client.put("/api/member/daily-report", headers=e["member"], json={
        "kind": "purchase", "company": UNIT, "as_of": yday, "fields": {"latex_wet": 2}})
    assert locked.status_code == 403 and locked.headers.get("X-Edit-Blocked") == "lock"
    detail = client.get(f"/api/edit-requests/{req['id']}", headers=e["editor"]).json()
    assert detail["still_blocked"] is True and detail["changed_since_submit"] is False
    assert [r["round_id"] for r in detail["lock"]["will_unlock"]] == [drop]

    ok = approve(e["editor"], req["id"])
    assert ok.status_code == 200, ok.text
    done = ok.json()["request"]
    assert done["status"] == "approved" and [r["round_id"] for r in done["unlocked"]] == [drop]
    row = unit_daily_repo.entries_on("purchase", OLD)[UNIT]
    assert row["fields"] == {"latex_wet": 5.0} and row["updated_by"] == "_zz_er_member"
    assert _unit_prices(OLD, UNIT) == {"purchase": 350.0}                 # 0 = xoá ô mủ chén
    assert str(data_lock_repo.locked_until(UNIT)) == older and keep != drop
    assert approve(e["editor"], req["id"]).status_code == 409
    assert e["mails"][-1][0] == ["zz_er_member@example.invalid"] and "đã duyệt" in e["mails"][-1][1]


def test_market_demand_reject_approve_and_cancel(env) -> None:
    e = env
    iid = seed_demand()["id"]
    payload = demand(id=iid, customer="KH mới")
    rid = send(e["member"], "demand_save", payload).json()["request"]["id"]
    assert reject(e["editor"], rid, " ").status_code == 400
    rej = reject(e["editor"], rid, "Không đủ căn cứ")
    assert rej.json()["request"]["status"] == "rejected"
    assert market_demand_item_repo.get(iid)["customer"] == "KH cũ"

    rid2 = send(e["member"], "demand_save", payload).json()["request"]["id"]
    assert rid2 != rid
    assert approve(e["admin"], rid2).status_code == 200
    assert market_demand_item_repo.get(iid)["customer"] == "KH mới"

    rid3 = send(e["member"], "demand_save", {**payload, "customer": "Lần ba"}).json()["request"]["id"]
    assert client.post(f"/api/member/edit-requests/{rid3}/cancel", headers=e["member"]).json()["request"]["status"] == "cancelled"
    assert client.post(f"/api/member/edit-requests/{rid3}/cancel", headers=e["member"]).status_code == 409
    mine = client.get("/api/member/edit-requests", headers=e["leader"]).json()
    assert mine["total"] == 3 and mine["counts"] == {"pending": 0, "approved": 1, "rejected": 1, "cancelled": 1}


def test_daily_move_round_trip(env) -> None:
    e = env
    unit_daily_repo.upsert("consumption", OLD, UNIT, {"stock_warehoused": [{"grade": "SVR 10 / CSR 10", "qty": 7}]}, "admin")
    payload = {"kind": "consumption", "company": UNIT, "as_of": OLD, "to_date": RECENT}
    res = send(e["member"], "daily_move", payload)
    assert res.status_code == 200, res.text
    rid = res.json()["request"]["id"]
    assert approve(e["editor"], rid).status_code == 200
    assert _day_fields("consumption", OLD, UNIT) is None and _day_fields("consumption", RECENT, UNIT)


def test_contract_save_delete_and_file_guard(env) -> None:
    e = env
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH đề nghị"}, headers=e["admin"]).json()["id"]
    body = {"company": UNIT, "code": "HD-ER-1", "customer_id": cus, "contract_type": "spot",
            "delivery_type": "single", "sign_date": OLD, "delivered_at": OLD, "channel": "domestic",
            "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]}
    cid = client.put("/api/sales-contracts", headers=e["admin"], json=body).json()["contract"]["id"]
    edit = {**body, "id": cid, "lines": [{**body["lines"][0], "qty": 20.0}]}
    direct = client.put("/api/sales-contracts", headers=e["member"], json=edit)
    assert direct.status_code == 403 and direct.headers.get("X-Edit-Blocked") == "window"

    rid = send(e["member"], "contract_save", edit).json()["request"]["id"]
    assert client.get(f"/api/edit-requests/{rid}/file/not-in-request.pdf", headers=e["editor"]).status_code == 404
    assert approve(e["editor"], rid).status_code == 200
    assert sales_contract_repo.get(cid)["qty"] == 20.0

    rid = send(e["member"], "contract_delete", {"id": cid}).json()["request"]["id"]
    assert approve(e["editor"], rid).status_code == 200
    assert sales_contract_repo.get(cid) is None
