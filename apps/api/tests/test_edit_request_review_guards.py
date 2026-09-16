"""«Đề nghị sửa»: các chốt chặn bổ sung sau rà đối kháng (phase 04).

Phiên bản đề nghị khi duyệt/từ chối · số liệu đổi sau khi gửi · nhu cầu thị trường không gỡ chốt ·
khoá riêng cho đổi ngày · hợp đồng đã hoàn thành · nút Thêm (`create_only`) · tiêu đề email.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import data_lock_repo, mailer, market_demand_repo, unit_daily_repo
from tests import edit_request_env
from tests.edit_request_env import OLD, RECENT, TODAY, UNIT, approve, client, lock_round, reject, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung

DAILY = {"kind": "purchase", "company": UNIT, "as_of": OLD, "fields": {"latex_wet": 5}}


def _review(hdr, rid: int, action: str, **body):
    return client.post(f"/api/edit-requests/{rid}/{action}", headers=hdr, json=body)


def test_stale_version_and_changed_since_submit(env) -> None:
    e = env
    unit_daily_repo.upsert("purchase", OLD, UNIT, {"latex_wet": 1}, "admin")
    rid = send(e["member"], "daily_report", DAILY).json()["request"]["id"]
    seen = client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()["request"]["updated_at"]
    assert _review(e["editor"], rid, "approve").status_code == 400                  # thiếu mốc
    again = send(e["member"], "daily_report", {**DAILY, "fields": {"latex_wet": 6}})
    assert again.json()["replaced"] is True
    for action, body in (("approve", {}), ("reject", {"note": "Không đủ căn cứ"})):
        stale = _review(e["editor"], rid, action, expected_updated_at=seen, **body)
        assert stale.status_code == 409 and "vừa cập nhật" in stale.json()["detail"]

    unit_daily_repo.upsert("purchase", OLD, UNIT, {"latex_wet": 3}, "admin")         # Ban sửa thẳng
    detail = client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()
    assert detail["changed_since_submit"] is True and detail["labels"] == {}
    changed = approve(e["editor"], rid)
    assert changed.status_code == 409 and "đã thay đổi" in changed.json()["detail"]
    assert unit_daily_repo.entries_on("purchase", OLD)[UNIT]["fields"] == {"latex_wet": 3.0}
    ok = approve(e["editor"], rid, accept_changed=True)
    assert ok.status_code == 200, ok.text
    assert unit_daily_repo.entries_on("purchase", OLD)[UNIT]["fields"] == {"latex_wet": 6.0}


def test_market_demand_approval_keeps_data_lock(env) -> None:
    e = env
    yday = (TODAY - timedelta(days=1)).isoformat()
    lock_round(e["admin"], yday)
    market_demand_repo.upsert(OLD, UNIT, "Nội dung cũ", "admin")
    rid = send(e["member"], "market_demand", {"company": UNIT, "as_of": OLD, "content": "Mới"}).json()["request"]["id"]
    assert client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()["lock"]["will_unlock"] == []
    ok = approve(e["editor"], rid)
    assert ok.status_code == 200, ok.text
    assert not ok.json()["request"]["unlocked"] and str(data_lock_repo.locked_until(UNIT)) == yday


def test_daily_move_does_not_replace_daily_report(env) -> None:
    e = env
    unit_daily_repo.upsert("purchase", OLD, UNIT, {"latex_wet": 1}, "admin")
    first = send(e["member"], "daily_report", DAILY).json()
    move = send(e["member"], "daily_move", {"kind": "purchase", "company": UNIT, "as_of": OLD, "to_date": RECENT})
    assert move.status_code == 200, move.text
    assert move.json()["replaced"] is False and move.json()["request"]["id"] != first["request"]["id"]
    assert move.json()["request"]["target_key"] == f"daily_move:purchase:{OLD}"
    listed = client.get("/api/member/edit-requests", headers=e["member"], params={"status": "pending"})
    assert listed.json()["total"] == 2


def test_completed_contract_rejected_at_submit_and_labels(env) -> None:
    e = env
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH đề nghị"}, headers=e["admin"]).json()["id"]
    body = {"company": UNIT, "code": "HD-ER-2", "customer_id": cus, "contract_type": "spot",
            "delivery_type": "single", "sign_date": OLD, "delivered_at": OLD, "channel": "domestic",
            "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]}
    cid = client.put("/api/sales-contracts", headers=e["admin"], json=body).json()["contract"]["id"]
    edit = {**body, "id": cid, "lines": [{**body["lines"][0], "qty": 20.0}]}
    rid = send(e["member"], "contract_save", edit).json()["request"]["id"]
    labels = client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()["labels"]
    assert labels["customer_id"] == {str(cus): "KH đề nghị"} and labels["channel"]["domestic"]
    assert reject(e["editor"], rid, "Làm lại sau").status_code == 200

    with session_scope() as db:
        db.execute(text("UPDATE sales_contract SET completed_at = CAST(:d AS date) WHERE id = :i"),
                   {"d": OLD, "i": cid})
    for op, payload in (("contract_save", edit), ("contract_delete", {"id": cid})):
        res = send(e["member"], op, payload)
        assert res.status_code == 400 and "đã hoàn thành" in res.json()["detail"], res.text


def test_create_only_on_existing_entry(env) -> None:
    e = env
    unit_daily_repo.upsert("purchase", OLD, UNIT, {"latex_wet": 1}, "admin")
    market_demand_repo.upsert(OLD, UNIT, "Đã có", "admin")
    dup = send(e["member"], "daily_report", {**DAILY, "create_only": True})
    assert dup.status_code == 409 and dup.json()["detail"].startswith("Đơn vị này đã có số liệu")
    dup = send(e["member"], "market_demand", {"company": UNIT, "as_of": OLD, "content": "X", "create_only": True})
    assert dup.status_code == 409 and dup.json()["detail"].startswith("Đơn vị này đã có nhu cầu")
    fresh = send(e["member"], "daily_report", {**DAILY, "kind": "consumption", "fields": {}, "create_only": True})
    assert fresh.status_code == 200, fresh.text
    assert "create_only" not in fresh.json()["request"]["payload"]


def test_email_subject_and_inactive_requester(env) -> None:
    e = env
    msg = mailer._build(["a@example.invalid"], "HĐ\r\nBcc: x@evil.invalid\nA", "nội dung", "s@example.invalid")
    assert msg["Subject"] == "HĐ Bcc: x@evil.invalid A" and "\n" not in msg["Subject"]
    rid = send(e["member"], "market_demand", {"company": UNIT, "as_of": OLD, "content": "Mới"}).json()["request"]["id"]
    with session_scope() as db:
        db.execute(text("UPDATE app_user SET is_active = false WHERE username = '_zz_er_member'"))
    sent = len(e["mails"])
    assert reject(e["editor"], rid, "Tài khoản đã khoá").status_code == 200
    assert len(e["mails"]) == sent
