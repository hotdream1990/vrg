"""«Đề nghị sửa» hợp đồng: luật nghiệp vụ kiểm NGAY lúc lưu/gửi — không để lọt tới lúc Ban bấm Duyệt.

Tái hiện 2 đề nghị kẹt trên prod 17–18/09/2026: đơn vị bấm THÊM rồi gõ lại số của một đợt giao /
hợp đồng đã có (#36 "…-Đợt 2", #51 "Phụ lục 04"). Phân biệt THÊM với SỬA để không báo trùng nhầm:
sửa mà giữ nguyên số thì không kiểm trùng (dữ liệu cũ có sẵn hợp đồng trùng số).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import sales_contract_repo
from tests import edit_request_env
from tests.edit_request_env import OLD, OTHER, TODAY, UNIT, approve, client, reject, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung

SIGN = (TODAY - timedelta(days=20)).isoformat()
LINE = {"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}


def _customer(e) -> int:
    return client.put("/api/customers", json={"company": UNIT, "name": "KH trùng số"},
                      headers=e["admin"]).json()["id"]


def _admin_save(e, body: dict) -> dict:
    res = client.put("/api/sales-contracts", headers=e["admin"], json=body)
    assert res.status_code == 200, res.text
    return res.json()["contract"]


def _contract(e, code: str, cus: int, **kw) -> dict:
    return _admin_save(e, {"company": UNIT, "code": code, "customer_id": cus, "contract_type": "spot",
                           "delivery_type": "single", "sign_date": SIGN, "delivered_at": OLD,
                           "channel": "domestic", "source": "exploit", "lines": [LINE], **kw})


def _delivery(pid: int, code: str, **kw) -> dict:
    return {"company": UNIT, "parent_id": pid, "code": code, "delivered_at": OLD,
            "channel": "domestic", "source": "exploit", "lines": [LINE], **kw}


def _pending() -> int:
    with session_scope() as db:
        return db.execute(text("SELECT count(*) FROM edit_request WHERE company = :c"),
                          {"c": UNIT}).scalar() or 0


def test_new_delivery_reusing_existing_number_is_refused_before_request(env) -> None:
    """#36: hợp đồng đã có Đợt 1, Đợt 2 — đơn vị THÊM đợt mới mà gõ lại "Đợt 2"."""
    e = env
    parent = _contract(e, "PL-08", _customer(e), delivery_type="multi", delivered_at=None,
                       lines=[{**LINE, "qty": 30.0}])
    for code in ("PL-08-Đợt 1", "PL-08-Đợt 2"):
        _admin_save(e, _delivery(parent["id"], code))

    dup = _delivery(parent["id"], "pl-08-đợt 2")            # khác hoa/thường vẫn là trùng
    direct = client.put("/api/sales-contracts", headers=e["member"], json=dup)
    assert direct.status_code == 400, direct.text             # báo trùng TRƯỚC hàng rào (không 403)
    msg = direct.json()["detail"]
    assert "đã có đợt giao số “PL-08-Đợt 2”" in msg and f"giao {OLD[8:10]}/{OLD[5:7]}" in msg
    assert "mở đúng đợt đó rồi bấm Sửa" in msg
    sent = send(e["member"], "contract_save", dup)
    assert sent.status_code == 400 and sent.json()["detail"] == msg
    assert _pending() == 0                                    # không sinh đề nghị kẹt

    ok = _delivery(parent["id"], "PL-08-Đợt 3")
    blocked = client.put("/api/sales-contracts", headers=e["member"], json=ok)
    assert blocked.status_code == 403 and blocked.headers.get("X-Edit-Blocked") == "window"
    rid = send(e["member"], "contract_save", ok).json()["request"]["id"]
    assert client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()["cannot_approve"] is None
    assert approve(e["editor"], rid).status_code == 200
    assert len(sales_contract_repo.children(parent["id"])) == 3


def test_new_contract_reusing_existing_number_and_other_parent_is_fine(env) -> None:
    """#51: THÊM hợp đồng "Phụ lục 04" khi đơn vị đã có. Đợt "1" ở hợp đồng khác thì không trùng."""
    e = env
    cus = _customer(e)
    _contract(e, "Phụ lục 04", cus, lines=[{**LINE, "qty": 105.0}])
    res = send(e["member"], "contract_save", {**_contract_body(cus), "code": "phụ lục 04"})
    assert res.status_code == 400, res.text
    assert "Đơn vị đã có hợp đồng số “Phụ lục 04”" in res.json()["detail"]
    assert "105 tấn" in res.json()["detail"]

    a = _contract(e, "HĐ-A", cus, delivery_type="multi", delivered_at=None)
    b = _contract(e, "HĐ-B", cus, delivery_type="multi", delivered_at=None)
    _admin_save(e, _delivery(a["id"], "1"))
    assert send(e["member"], "contract_save", _delivery(b["id"], "1")).status_code == 200


def test_update_keeps_own_number_even_when_legacy_duplicate_exists(env) -> None:
    """Sửa mà GIỮ số: không báo trùng nhầm dù dữ liệu cũ có 2 hợp đồng cùng số. ĐỔI sang số đã có: chặn."""
    e = env
    cus = _customer(e)
    first = _contract(e, "02/HDXK26", cus)
    other = _contract(e, "03/HDXK26", cus)
    with session_scope() as db:                               # dữ liệu cũ: 2 hợp đồng trùng số
        db.execute(text("UPDATE sales_contract SET code = '02/HDXK26' WHERE id = :i"), {"i": other["id"]})
    edit = {**_contract_body(cus), "id": first["id"], "code": "02/HDXK26", "lines": [{**LINE, "qty": 12.0}]}
    direct = client.put("/api/sales-contracts", headers=e["member"], json=edit)
    assert direct.status_code == 403, direct.text             # chỉ còn vướng cửa sổ sửa
    rid = send(e["member"], "contract_save", edit).json()["request"]["id"]
    assert approve(e["editor"], rid).status_code == 200
    assert sales_contract_repo.get(first["id"])["qty"] == 12.0

    third = _contract(e, "04/HDXK26", cus)
    renamed = send(e["member"], "contract_save", {**_contract_body(cus), "id": third["id"], "code": "02/hdxk26"})
    assert renamed.status_code == 400
    assert renamed.json()["detail"].startswith("Số “02/HDXK26” đã dùng cho một hợp đồng khác")


def test_other_rules_checked_at_submit(env) -> None:
    """Không chỉ trùng số: vượt 110% sản lượng, thêm đợt vào hợp đồng giao-1-lần cũng báo lúc gửi."""
    e = env
    cus = _customer(e)
    multi = _contract(e, "HĐ-CAP", cus, delivery_type="multi", delivered_at=None)
    over = send(e["member"], "contract_save", _delivery(multi["id"], "1", lines=[{**LINE, "qty": 11.5}]))
    assert over.status_code == 400 and "vượt quá 110%" in over.json()["detail"]
    single = _contract(e, "HĐ-SINGLE", cus)
    res = send(e["member"], "contract_save", _delivery(single["id"], "1"))
    assert res.status_code == 400 and "giao nhiều lần" in res.json()["detail"]
    assert _pending() == 0


def test_other_units_contract_numbers_never_leak(env) -> None:
    """Câu báo trùng nêu ngày giao · sản lượng — đoán `parent_id` của đơn vị KHÁC không được đọc số của họ."""
    e = env
    cus = client.put("/api/customers", json={"company": OTHER, "name": "KH đơn vị khác"},
                     headers=e["admin"]).json()["id"]
    theirs = _admin_save(e, {"company": OTHER, "code": "HĐ-KHÁC", "customer_id": cus, "contract_type": "spot",
                             "delivery_type": "multi", "sign_date": SIGN, "lines": [{**LINE, "qty": 30.0}]})
    _admin_save(e, {**_delivery(theirs["id"], "Đợt 2"), "company": OTHER})
    probe = {**_delivery(theirs["id"], "Đợt 2"), "company": UNIT}
    for res in (client.put("/api/sales-contracts", headers=e["member"], json=probe),
                send(e["member"], "contract_save", probe)):
        assert res.status_code == 400 and res.json()["detail"] == "Hợp đồng thuộc đơn vị khác.", res.text


def test_review_page_flags_request_that_became_unapprovable(env) -> None:
    """Gửi lúc hợp lệ, sau đó Ban tự nhập đúng số đó ⇒ trang duyệt báo trước, Duyệt vẫn chặn, Từ chối được."""
    e = env
    parent = _contract(e, "PL-09", _customer(e), delivery_type="multi", delivered_at=None,
                       lines=[{**LINE, "qty": 30.0}])
    rid = send(e["member"], "contract_save", _delivery(parent["id"], "Đợt 1")).json()["request"]["id"]
    _admin_save(e, _delivery(parent["id"], "Đợt 1"))

    detail = client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()
    assert "đã có đợt giao số “Đợt 1”" in detail["cannot_approve"]
    bad = approve(e["editor"], rid)
    assert bad.status_code == 400 and bad.json()["detail"] == detail["cannot_approve"]
    assert len(sales_contract_repo.children(parent["id"])) == 1
    assert reject(e["editor"], rid, "Đợt 1 đã có — gửi lại với số Đợt 2").status_code == 200
    closed = client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()
    assert closed["cannot_approve"] is None                  # hết chờ duyệt thì thôi kiểm


def _contract_body(cus: int) -> dict:
    return {"company": UNIT, "code": "", "customer_id": cus, "contract_type": "spot",
            "delivery_type": "single", "sign_date": SIGN, "delivered_at": OLD, "channel": "domestic",
            "source": "exploit",
            "lines": [LINE]}
