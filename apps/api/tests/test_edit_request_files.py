"""Đề nghị sửa số liệu — THÊM / BỚT FILE đính kèm của hợp đồng đã quá hạn sửa.

Hai trường hợp phải đúng:
- Chỉ thêm/bớt file (không đụng con số) ⇒ đơn vị lưu THẲNG được, không cần đề nghị (sửa an toàn).
- Thêm/bớt file KÈM sửa số liệu ⇒ đi đề nghị; người duyệt mở được cả file mới lẫn file bị bỏ;
  duyệt xong danh sách file của hợp đồng đúng bằng danh sách trong đề nghị.
"""

from __future__ import annotations

import pytest

from app.core.db import db_healthy
from app.services import contract_files, sales_contract_repo
from tests import edit_request_env
from tests.edit_request_env import OLD, UNIT, approve, client, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung


def _upload(hdr, name: str) -> dict:
    res = client.post("/api/sales-contracts/file", headers=hdr,
                      files={"file": (name, b"%PDF-1.4 zz edit request test", "application/pdf")})
    assert res.status_code == 200, res.text
    got = res.json()
    return {"file": got["file"], "filename": got["filename"]}


def _names(docs: list[dict]) -> list[str]:
    return [d["file"] for d in docs or []]


def test_add_and_remove_files_directly_and_via_request(env) -> None:
    e = env
    a, b, c, d = (_upload(e["admin"], f"hop-dong-{x}.pdf") for x in "abcd")
    try:
        cus = client.put("/api/customers", json={"company": UNIT, "name": "KH file"},
                         headers=e["admin"]).json()["id"]
        body = {"company": UNIT, "code": "HD-ER-FILE", "customer_id": cus, "contract_type": "spot",
                "delivery_type": "single", "sign_date": OLD, "delivered_at": OLD, "channel": "domestic",
                "source": "exploit",
                "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}],
                "files": [a, b]}
        cid = client.put("/api/sales-contracts", headers=e["admin"], json=body).json()["contract"]["id"]

        # 1) Chỉ thêm C, bỏ A — không đụng số ⇒ đơn vị lưu thẳng dù hợp đồng đã quá hạn sửa.
        only_files = {**body, "id": cid, "files": [b, c]}
        direct = client.put("/api/sales-contracts", headers=e["member"], json=only_files)
        assert direct.status_code == 200, direct.text
        assert _names(sales_contract_repo.get(cid)["files"]) == [b["file"], c["file"]]
        assert send(e["member"], "contract_save", only_files).status_code == 409   # không cần đề nghị

        # 2) Sửa sản lượng + thêm D + bỏ B ⇒ bị chặn ⇒ gửi đề nghị.
        edit = {**only_files, "lines": [{**body["lines"][0], "qty": 12.0}], "files": [c, d]}
        blocked = client.put("/api/sales-contracts", headers=e["member"], json=edit)
        assert blocked.status_code == 403
        res = send(e["member"], "contract_save", edit)
        assert res.status_code == 200, res.text
        req = res.json()["request"]
        assert _names(sales_contract_repo.get(cid)["files"]) == [b["file"], c["file"]]  # chưa đổi

        # Người duyệt mở được file mới (D) và file sắp bị bỏ (B); file ngoài đề nghị (A) thì không.
        for doc, code in ((d, 200), (b, 200), (a, 404)):
            got = client.get(f"/api/edit-requests/{req['id']}/file/{doc['file']}", headers=e["editor"])
            assert got.status_code == code, (doc["filename"], got.status_code)

        assert approve(e["editor"], req["id"]).status_code == 200
        after = sales_contract_repo.get(cid)
        assert after["qty"] == 12.0
        assert _names(after["files"]) == [c["file"], d["file"]]
    finally:
        for doc in (a, b, c, d):
            contract_files.path_for(doc["file"]).unlink(missing_ok=True)
