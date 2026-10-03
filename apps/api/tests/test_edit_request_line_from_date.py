"""«Đề nghị sửa» + NGÀY HIỆU LỰC theo dòng hợp đồng (30/09/2026).

Hợp đồng giao 1 lần đã giao trong kỳ ĐÃ CHỐT: sửa ô không dịch số (ghi chú) vẫn lưu thẳng dù form
gửi `from_date` của mọi dòng; đổi ngày hiệu lực là đổi số liệu → bị chặn, đi đề nghị, duyệt xong
ngày mới được ghi đúng.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.db import db_healthy
from tests import edit_request_env
from tests.edit_request_env import OLD, TODAY, UNIT, approve, client, lock_round, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung

SIGN = (TODAY - timedelta(days=20)).isoformat()
ADDED = (TODAY - timedelta(days=15)).isoformat()
LINE = {"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}


def test_line_date_change_on_locked_delivery_goes_through_request(env) -> None:
    e = env
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH hiệu lực"},
                     headers=e["admin"]).json()["id"]
    c = client.put("/api/sales-contracts", headers=e["admin"], json={
        "company": UNIT, "code": "HD-HL", "customer_id": cus, "contract_type": "spot",
        "delivery_type": "single", "sign_date": SIGN, "delivered_at": OLD, "channel": "domestic",
        "source": "exploit",
        "lines": [LINE, {**LINE, "qty": 6.0, "from_date": ADDED}]}).json()["contract"]
    lock_round(e["admin"], OLD)
    # Form gửi lại mọi dòng: dòng không ngày thành `from_date: null` — vẫn là sửa an toàn.
    form = {**c, "lines": [{**LINE, "from_date": None}, {**LINE, "qty": 6.0, "from_date": ADDED}]}
    note = client.put("/api/sales-contracts", headers=e["member"], json={**form, "note": "đính HĐ"})
    assert note.status_code == 200, note.text

    moved_day = (TODAY - timedelta(days=12)).isoformat()
    moved = {**form, "lines": [form["lines"][0], {**form["lines"][1], "from_date": moved_day}]}
    blocked = client.put("/api/sales-contracts", headers=e["member"], json=moved)
    assert blocked.status_code == 403 and blocked.headers.get("X-Edit-Blocked")
    rid = send(e["member"], "contract_save", moved).json()["request"]["id"]
    assert approve(e["editor"], rid).status_code == 200
    got = client.get(f"/api/sales-contracts/{c['id']}", headers=e["admin"]).json()["contract"]
    assert got["lines"][1]["from_date"] == moved_day
