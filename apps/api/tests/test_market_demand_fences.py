"""Nhu cầu thị trường: hàng rào thời gian (§4) · đề nghị sửa (§5) · sáp nhập · nhật ký hoạt động.

Dùng chung fixture `md` + helper của `test_market_demand.py` (đơn vị `_zz_md_`, dọn sạch sau test).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.db import db_healthy
from app.services import audit_repo, config_repo, market_demand_item_repo, member_unit_merge
from app.services.edit_request_ops_demand import OPS
from tests import test_market_demand as base
from tests.edit_request_env import approve, send
from tests.test_market_demand import (
    EDITOR_URL, MEMBER_URL, TODAY, TODAY_ISO, UNIT_A, UNIT_B, UNIT_OLD, YDAY, _ids, client, item, seed,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
md = base.md   # fixture dùng chung
BLOCK = "X-Edit-Blocked"


def _close_windows() -> None:
    """Cửa sổ = 0 cho cả hai vai trò (chỉ hôm nay) — fixture `md` trả lại giá trị cũ."""
    config_repo.set_config({k: "0" for k in base.WINDOW_KEYS})


def _blocked(res) -> bool:
    return res.status_code == 403 and res.headers.get(BLOCK) == "window"


def test_window_blocks_content_but_not_tracking_fields(md) -> None:
    _close_windows()
    old = seed(as_of=YDAY)
    iid, mem = old["id"], md["mem"]
    assert _blocked(client.put(MEMBER_URL, headers=mem, json=item(as_of=YDAY)))
    assert _blocked(client.put(MEMBER_URL, headers=mem, json=item(id=iid, as_of=YDAY, customer="Khác")))
    # Kéo phiếu cũ vào vùng mở (đổi ngày nhận sang hôm nay) cũng bị chặn theo ngày CŨ.
    assert _blocked(client.put(MEMBER_URL, headers=mem, json=item(id=iid)))
    tracking = item(id=iid, as_of=YDAY, qty=100.0, result="Đã ký HĐ số HD-9", note="Đã ký sau 1 ngày")
    res = client.put(MEMBER_URL, headers=mem, json=tracking)
    assert res.status_code == 200, res.text
    assert res.json()["item"]["result"] == "Đã ký HĐ số HD-9" and res.json()["item"]["updated_by"] == "zz_md_mem"
    # Thời gian giao là ô NỘI DUNG — phiếu quá hạn thì không đổi được.
    assert _blocked(client.put(MEMBER_URL, headers=mem, json={**tracking, "delivery_time": "Tháng 12"}))
    assert _blocked(client.delete(f"{MEMBER_URL}/{iid}", headers=mem))
    assert client.put(MEMBER_URL, headers=mem, json=item()).status_code == 200      # hôm nay vẫn nhập

    ed = md["ed"]
    assert _blocked(client.put(EDITOR_URL, headers=ed, json={**tracking, "price": 41}))
    assert client.put(EDITOR_URL, headers=ed, json={**tracking, "result": "Không thành"}).status_code == 200
    admin = client.put(EDITOR_URL, headers=md["admin"], json={**tracking, "customer": "Admin sửa"})
    assert admin.status_code == 200 and admin.json()["item"]["customer"] == "Admin sửa"
    assert client.delete(f"{EDITOR_URL}/{iid}", headers=md["admin"]).status_code == 200


def test_edit_request_save_and_delete_round_trip(md) -> None:
    _close_windows()
    old = seed(as_of=YDAY)
    iid, mem = old["id"], md["mem"]
    base_payload = item(id=iid, as_of=YDAY)
    assert send(mem, "demand_save", {**base_payload, "note": "chỉ ghi chú"}).status_code == 409
    assert send(md["lead"], "demand_save", {**base_payload, "customer": "KH mới"}).status_code == 403
    assert send(md["memb"], "demand_save", {**base_payload, "customer": "KH mới"}).status_code == 403
    assert send(mem, "demand_save", {**base_payload, "grade": "SVR 99"}).status_code == 400

    sent = send(mem, "demand_save", {**base_payload, "customer": "KH mới"})
    assert sent.status_code == 200, sent.text
    req = sent.json()["request"]
    assert req["blocked"] and req["target_key"] == f"demand:{iid}"
    assert req["title"] == f"Nhu cầu KH mới · LATEX ngày {YDAY[8:]}/{YDAY[5:7]}/{YDAY[:4]}"
    assert market_demand_item_repo.get(iid)["customer"] == "Công ty ZZ Anh Dũng"   # chưa đổi
    ok = approve(md["admin"], req["id"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["request"]["status"] == "approved" and not ok.json()["request"]["unlocked"]
    after = market_demand_item_repo.get(iid)
    assert after["customer"] == "KH mới" and after["updated_by"] == "zz_md_mem"

    new = send(mem, "demand_save", item(as_of=YDAY, customer="Khách gửi mới", grade="RSS 3"))
    assert new.status_code == 200 and new.json()["request"]["target_key"].startswith("demand:new:")
    assert approve(md["admin"], new.json()["request"]["id"]).status_code == 200
    made = [x for x in client.get(MEMBER_URL, headers=mem, params={"date_from": YDAY}).json()["items"]
            if x["customer"] == "Khách gửi mới"]
    assert len(made) == 1 and made[0]["created_by"] == "zz_md_mem" and made[0]["as_of"] == YDAY

    assert send(mem, "demand_delete", {"id": 999999999}).status_code == 404
    gone = send(mem, "demand_delete", {"id": iid})
    assert gone.status_code == 200 and gone.json()["request"]["title"].startswith("Xoá nhu cầu KH mới")
    assert approve(md["admin"], gone.json()["request"]["id"]).status_code == 200
    assert market_demand_item_repo.get(iid) is None


def test_merged_unit_is_readable_but_not_writable(md) -> None:
    # Ngày phiếu nằm TRONG cửa sổ 7 ngày → 403 dưới đây chỉ có thể do phạm vi đơn vị, không do cửa sổ.
    old_day = (TODAY - timedelta(days=3)).isoformat()
    kept = seed(company=UNIT_OLD, as_of=old_day, customer="KH đơn vị cũ")
    member_unit_merge.merge(UNIT_OLD, UNIT_A, YDAY)
    params = {"date_from": old_day}
    body = client.get(MEMBER_URL, headers=md["mem"], params=params).json()
    assert body["view_only_units"] == [UNIT_OLD] and UNIT_A in body["units"]
    assert kept["id"] in [x["id"] for x in body["items"]]
    assert kept["id"] not in _ids(client.get(MEMBER_URL, headers=md["memb"], params=params))
    for company in (UNIT_OLD, UNIT_A, UNIT_B):
        res = client.put(MEMBER_URL, headers=md["mem"], json=item(id=kept["id"], as_of=old_day, company=company))
        assert res.status_code == 403, res.text
    assert client.delete(f"{MEMBER_URL}/{kept['id']}", headers=md["mem"]).status_code == 403


def test_audit_log_records_create_update_delete(md) -> None:
    iid = client.put(MEMBER_URL, headers=md["mem"], json=item()).json()["item"]["id"]
    client.put(MEMBER_URL, headers=md["mem"], json=item(id=iid, customer="Khách đổi tên"))
    client.put(MEMBER_URL, headers=md["mem"], json=item(id=iid, customer="Khách đổi tên"))  # không đổi gì
    client.delete(f"{MEMBER_URL}/{iid}", headers=md["mem"])
    rows = audit_repo.search(entity="market_demand", company=UNIT_A)["items"]
    mine = [r for r in rows if r["entity_key"] == str(iid)]
    assert sorted(r["action"] for r in mine) == ["create", "delete", "update"]
    upd = next(r for r in mine if r["action"] == "update")
    assert upd["before"]["customer"] == "Công ty ZZ Anh Dũng" and upd["after"]["customer"] == "Khách đổi tên"
    assert all(r["actor"] == "zz_md_mem" and r["as_of"] == TODAY_ISO for r in mine)


def test_request_from_old_form_applies_with_blank_new_fields(md) -> None:
    """Đề nghị gửi từ mẫu phiếu trước khi rút gọn (có status/contract_no, thiếu delivery_time/result)
    vẫn duyệt được: ô mới thành chuỗi rỗng thay vì NULL làm hỏng lệnh ghi."""
    old = seed(as_of=YDAY)
    payload = {**item(id=old["id"], as_of=YDAY, note="Mẫu cũ"),
               "status": "signed", "contract_no": "HD-1", "contract_date": YDAY}
    out = OPS["demand_save"].apply(payload, "zz_md_mem", UNIT_A)["item"]
    assert out["result"] == "" and out["delivery_time"] == "" and out["note"] == "Mẫu cũ"
