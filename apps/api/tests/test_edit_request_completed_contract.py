"""«Đề nghị sửa» gặp hợp đồng ĐÃ HOÀN THÀNH lúc Ban duyệt (chốt 08/10/2026).

Tái hiện #781 trên prod: đơn vị gửi đề nghị sửa nguồn của một đợt giao rồi 32 giây sau bấm Hoàn thành
hợp đồng ⇒ đề nghị kẹt dù nội dung đúng. Nay: lúc GỬI vẫn chặn (phải mở lại), lúc DUYỆT ghi thẳng,
giữ nguyên ngày hoàn thành — trừ khi lần sửa đẩy ngày giao ra sau ngày hoàn thành.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.db import db_healthy
from app.services import sales_contract_lifecycle, sales_contract_repo
from app.services.edit_request_ops import changed_since
from tests import edit_request_env
from tests.edit_request_env import OLD, TODAY, UNIT, approve, client, lock_round, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung

SIGN = (TODAY - timedelta(days=20)).isoformat()
LATER = (date.fromisoformat(OLD) + timedelta(days=1)).isoformat()   # vẫn ngoài cửa sổ 3 ngày
LINE = {"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND", "source": "goods"}


def _save(e, body: dict) -> dict:
    res = client.put("/api/sales-contracts", headers=e["admin"], json=body)
    assert res.status_code == 200, res.text
    return res.json()["contract"]


def _contract(e, code: str, **kw) -> dict:
    cus = client.put("/api/customers", json={"company": UNIT, "name": f"KH {code}"},
                     headers=e["admin"]).json()["id"]
    return _save(e, {"company": UNIT, "code": code, "customer_id": cus, "contract_type": "spot",
                     "delivery_type": "multi", "sign_date": SIGN, "lines": [{**LINE, "qty": 30.0}], **kw})


def _batch(pid: int, code: str, **kw) -> dict:
    return {"company": UNIT, "parent_id": pid, "code": code, "delivered_at": OLD,
            "channel": "domestic", "lines": [LINE], **kw}


def _complete(cid: int) -> None:
    sales_contract_lifecycle.set_completion(cid, OLD, None, "admin")


def _review(e, rid: int) -> dict:
    return client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()


def test_batch_edit_approved_after_unit_completes_contract(env) -> None:
    """#781: gửi lúc hợp đồng đang mở, đơn vị chốt hoàn thành ngay sau đó ⇒ Ban vẫn duyệt được."""
    e = env
    parent = _contract(e, "HT-01")
    batch = _save(e, _batch(parent["id"], "HT-01-Đợt 1"))
    split = [{**LINE, "qty": 7.0}, {**LINE, "qty": 3.0, "source": "purchase"}]
    rid = send(e["member"], "contract_save", {**_batch(parent["id"], batch["code"], lines=split),
                                              "id": batch["id"]}).json()["request"]["id"]
    _complete(parent["id"])

    assert _review(e, rid)["cannot_approve"] is None
    assert approve(e["editor"], rid).status_code == 200
    lines = sales_contract_repo.get(batch["id"])["lines"]
    assert [(ln["qty"], ln["source"]) for ln in lines] == [(7.0, "goods"), (3.0, "purchase")]
    assert sales_contract_repo.get(parent["id"])["completed_at"] == OLD     # vẫn hoàn thành, đúng ngày cũ

    again = send(e["member"], "contract_save", {**_batch(parent["id"], batch["code"]), "id": batch["id"]})
    assert again.status_code == 400 and "đã hoàn thành" in again.json()["detail"]   # lúc gửi vẫn chặn


def test_approval_refuses_delivery_after_completion_date(env) -> None:
    """Dời ngày giao ra SAU ngày hoàn thành = hợp đồng "xong" trước lần giao ⇒ trang duyệt báo, Duyệt chặn."""
    e = env
    parent = _contract(e, "HT-02")
    batch = _save(e, _batch(parent["id"], "HT-02-Đợt 1"))
    rid = send(e["member"], "contract_save", {**_batch(parent["id"], batch["code"], delivered_at=LATER),
                                              "id": batch["id"]}).json()["request"]["id"]
    _complete(parent["id"])

    problem = _review(e, rid)["cannot_approve"]
    assert problem and "sau ngày hoàn thành hợp đồng HT-02" in problem and "mở lại hợp đồng" in problem
    res = approve(e["editor"], rid)
    assert res.status_code == 400 and res.json()["detail"] == problem
    assert sales_contract_repo.get(batch["id"])["delivered_at"] == OLD


def test_delete_and_switch_approved_on_completed_contract(env) -> None:
    """Xoá đợt giao và chuyển loại giao không dời mốc nào ⇒ duyệt được dù hợp đồng đã hoàn thành."""
    e = env
    parent = _contract(e, "HT-03")
    _save(e, _batch(parent["id"], "HT-03-Đợt 1"))
    second = _save(e, _batch(parent["id"], "HT-03-Đợt 2"))
    rid = send(e["member"], "contract_delete", {"id": second["id"]}).json()["request"]["id"]
    _complete(parent["id"])
    assert _review(e, rid)["cannot_approve"] is None
    assert approve(e["editor"], rid).status_code == 200
    assert [k["code"] for k in sales_contract_repo.children(parent["id"])] == ["HT-03-Đợt 1"]

    single = _contract(e, "HT-04", delivery_type="single", delivered_at=OLD, channel="domestic",
                       lines=[LINE])
    lock_round(e["admin"], OLD)            # chuyển loại giao chỉ vướng chốt số liệu
    rid = send(e["member"], "contract_delivery_type",
               {"id": single["id"], "delivery_type": "multi"}).json()["request"]["id"]
    _complete(single["id"])
    review = _review(e, rid)
    assert review["cannot_approve"] is None
    assert review["changed_since_submit"] is False   # chốt hoàn thành không phải "số liệu đã đổi"
    assert approve(e["editor"], rid).status_code == 200
    after = sales_contract_repo.get(single["id"])
    assert after["delivery_type"] == "multi" and after["completed_at"] == OLD
    assert [k["delivered_at"] for k in sales_contract_repo.children(single["id"])] == [OLD]


def test_completed_single_contract_edit_on_review(env) -> None:
    """Sửa chính hợp đồng giao 1 lần đã hoàn thành: tách nguồn duyệt được; dời ngày giao quá ngày
    hoàn thành thì chặn. Đường ghi THƯỜNG (xoá, chuyển loại giao) vẫn bị khoá như cũ."""
    e = env
    c = _contract(e, "HT-05", delivery_type="single", delivered_at=OLD, channel="domestic",
                  lines=[LINE, {**LINE, "qty": 5.0}])
    body = {key: c[key] for key in ("id", "company", "code", "customer_id", "contract_type", "delivery_type",
                                    "sign_date", "delivered_at", "channel", "lines")}
    split = send(e["member"], "contract_save",
                 {**body, "lines": [LINE, {**LINE, "qty": 5.0, "source": "purchase"}]}).json()["request"]["id"]
    _complete(c["id"])
    assert approve(e["editor"], split).status_code == 200
    after = sales_contract_repo.get(c["id"])
    assert [ln["source"] for ln in after["lines"]] == ["goods", "purchase"] and after["completed_at"] == OLD

    with_open = sales_contract_lifecycle.set_completion(c["id"], None, None, "admin")
    assert with_open["completed_at"] is None
    late = send(e["member"], "contract_save", {**body, "delivered_at": LATER}).json()["request"]["id"]
    _complete(c["id"])
    assert "Ngày giao" in _review(e, late)["cannot_approve"]
    assert approve(e["editor"], late).status_code == 400

    assert client.delete(f"/api/sales-contracts/{c['id']}", headers=e["admin"]).status_code == 400
    switch = client.put(f"/api/sales-contracts/{c['id']}/delivery-type", headers=e["admin"],
                        json={"delivery_type": "multi"})
    assert switch.status_code == 400 and "đã hoàn thành" in switch.json()["detail"]


def test_changed_since_ignores_only_listed_fields() -> None:
    before, done = {"qty": 1, "completed_at": None}, {"qty": 1.0, "completed_at": "2026-05-12"}
    assert changed_since(done, before) is True                       # mặc định vẫn so mọi ô
    assert changed_since(done, before, ("completed_at",)) is False
    assert changed_since({**done, "qty": 2}, before, ("completed_at",)) is True
