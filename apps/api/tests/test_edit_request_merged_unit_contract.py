"""«Đề nghị sửa» hợp đồng của đơn vị ĐÃ SÁP NHẬP (08/10/2026).

Hợp đồng cũ chạy tiếp ở đơn vị cũ (chốt 24/08/2026) ⇒ tài khoản đã chuyển sang đơn vị nhận vẫn gửi
đề nghị sửa/xoá được, Ban duyệt thì ghi vào ĐÚNG đơn vị cũ. Web từng ẩn nút với đơn vị đã sáp nhập nên
hợp đồng Bình Long (sáp nhập vào Lộc Ninh) quá hạn sửa là đơn vị hết đường sửa.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.db import db_healthy
from app.services import member_unit_merge, sales_contract_repo, user_repo
from tests import edit_request_env
from tests.edit_request_env import OLD, OTHER, TODAY, UNIT, approve, client, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung

SIGN = (TODAY - timedelta(days=20)).isoformat()
MERGED_AT = (TODAY - timedelta(days=15)).isoformat()   # sau ngày ký, trước ngày giao OLD
LINE = {"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND", "source": "exploit"}


def _body(code: str, cus: int, **kw) -> dict:
    return {"company": UNIT, "code": code, "customer_id": cus, "contract_type": "spot",
            "delivery_type": "single", "sign_date": SIGN, "delivered_at": OLD, "channel": "domestic",
            "lines": [LINE], **kw}


def _contract(e, code: str) -> tuple[dict, dict]:
    """Ký TRƯỚC khi sáp nhập (đơn vị cũ còn ký được) — trả (hợp đồng, thân gửi lại được)."""
    cus = client.put("/api/customers", json={"company": UNIT, "name": f"KH {code}"},
                     headers=e["admin"]).json()["id"]
    res = client.put("/api/sales-contracts", headers=e["admin"], json=_body(code, cus))
    assert res.status_code == 200, res.text
    c = res.json()["contract"]
    return c, _body(code, cus, id=c["id"])


def test_moved_account_edits_merged_units_contract_via_request(env) -> None:
    e = env
    kept, body = _contract(e, "SN-01")
    gone, _ = _contract(e, "SN-02")
    member_unit_merge.merge(UNIT, OTHER, MERGED_AT)
    assert user_repo.get_user("_zz_er_member")["member_units"] == [OTHER]   # tài khoản chuyển hẳn

    res = send(e["member"], "contract_save", {**body, "lines": [{**LINE, "price": 45.0}]})
    assert res.status_code == 200, res.text
    assert approve(e["editor"], res.json()["request"]["id"]).status_code == 200
    after = sales_contract_repo.get(kept["id"])
    assert after["company"] == UNIT                  # vẫn ở đơn vị cũ, không nhảy sang đơn vị nhận
    assert after["lines"][0]["price"] == 45.0

    res = send(e["member"], "contract_delete", {"id": gone["id"]})
    assert res.status_code == 200, res.text
    assert approve(e["editor"], res.json()["request"]["id"]).status_code == 200
    assert sales_contract_repo.get(gone["id"]) is None


def test_merged_unit_still_cannot_sign_new_contract_via_request(env) -> None:
    """Mở đường đề nghị cho hợp đồng CŨ không được thành cửa sau ký hợp đồng MỚI cho đơn vị đã sáp nhập."""
    e = env
    _, body = _contract(e, "SN-03")
    member_unit_merge.merge(UNIT, OTHER, MERGED_AT)
    fresh = {k: v for k, v in body.items() if k != "id"}
    res = send(e["member"], "contract_save", {**fresh, "code": "SN-04"})
    assert res.status_code == 400 and "đã sáp nhập" in res.json()["detail"]
