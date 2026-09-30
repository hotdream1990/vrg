"""NGÀY HIỆU LỰC theo dòng chủng loại của hợp đồng (30/09/2026).

Hợp đồng ký 10 tấn ngày 10, ngày 15 thêm 6 tấn ⇒ "đã ký HĐ chưa giao" 10–14 là 10 tấn, từ 15 là
16 tấn. Tăng = thêm dòng có ngày hiệu lực; giảm = sửa thẳng số của dòng (chủ dự án chốt).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.schemas.sales_contract import ContractIn
from app.services import sales_contract_lock, user_repo
from app.services.edit_request_ops import parse

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_fd_unit"
SVR = "SVR 10 / CSR 10"


def _admin() -> dict[str, str]:
    user_repo.seed_admin()
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = :u"), {"u": UNIT})
        db.execute(text("DELETE FROM unit_customer WHERE company = :u"), {"u": UNIT})
    client.delete(f"/api/member-units/{UNIT}", headers=h)


@pytest.fixture()
def env():
    h = _admin()
    _cleanup(h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH hiệu lực"},
                     headers=h).json()["id"]
    yield h, cus
    _cleanup(h)


def _line(qty: float, **kw) -> dict:
    return {"grade": SVR, "qty": qty, "price": 40.0, "ccy": "VND", **kw}


def _save(h, body: dict):
    return client.put("/api/sales-contracts", json={"company": UNIT, **body}, headers=h)


def _contract(h, cus, **kw) -> dict:
    body = {"code": "HD-FD", "delivery_type": "multi", "contract_type": "spot",
            "customer_id": cus, "sign_date": "2026-09-10", "lines": [_line(10.0)], **kw}
    r = _save(h, body)
    assert r.status_code == 200, r.text
    return r.json()["contract"]


def _block3(h, day: str) -> float:
    rep = client.get(f"/api/sales-contracts/undelivered?as_of={day}&company={UNIT}",
                     headers=h).json()["by_company"]
    return (rep.get(UNIT) or {}).get("qty", 0.0)


def test_added_line_counts_only_from_its_effective_date(env) -> None:
    """Ví dụ của chủ dự án: 10 tấn ký ngày 10, thêm 6 tấn từ ngày 15."""
    h, cus = env
    c = _contract(h, cus)
    r = _save(h, {**c, "lines": [*c["lines"], _line(6.0, from_date="2026-09-15")]})
    assert r.status_code == 200, r.text
    assert r.json()["contract"]["lines"][1]["from_date"] == "2026-09-15"

    assert _block3(h, "2026-09-09") == pytest.approx(0.0)
    assert _block3(h, "2026-09-10") == pytest.approx(10.0)
    assert _block3(h, "2026-09-14") == pytest.approx(10.0)
    assert _block3(h, "2026-09-15") == pytest.approx(16.0)

    # Đợt giao 4 tấn ngày 12 trừ vào cả hai giai đoạn.
    kid = _save(h, {"parent_id": c["id"], "code": "Đ1", "delivered_at": "2026-09-12",
                    "channel": "export", "lines": [_line(4.0)]})
    assert kid.status_code == 200, kid.text
    assert _block3(h, "2026-09-12") == pytest.approx(6.0)
    assert _block3(h, "2026-09-15") == pytest.approx(12.0)

    # Số HIỆN TẠI (màn Hợp đồng) tính mọi dòng: 16 − 4.
    d = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()
    assert d["remaining_qty"] == pytest.approx(12.0)


def test_effective_date_rules(env) -> None:
    h, cus = env
    c = _contract(h, cus)
    # Trước ngày ký → chặn, nói rõ lý do.
    r = _save(h, {**c, "lines": [*c["lines"], _line(6.0, from_date="2026-09-09")]})
    assert r.status_code == 400 and "trước ngày ký" in r.json()["detail"]
    # Ngày sai định dạng → chặn, không lặng lẽ bỏ qua.
    r = _save(h, {**c, "lines": [_line(10.0, from_date="15/09/2026")]})
    assert r.status_code == 400 and "không hợp lệ" in r.json()["detail"]
    # Trùng ngày ký vẫn giữ nguyên (không quy về trống — xem test ngày ký 10 → 15 → 10).
    r = _save(h, {**c, "lines": [_line(10.0, from_date="2026-09-10")]})
    assert r.status_code == 200 and r.json()["contract"]["lines"][0]["from_date"] == "2026-09-10"
    # Để trống → không ghi khoá (bản ghi cũ lưu lại không đổi JSON).
    r = _save(h, {**c, "lines": [_line(10.0, from_date=None)]})
    assert r.status_code == 200 and "from_date" not in r.json()["contract"]["lines"][0]

    # Đợt giao KHÔNG có ngày hiệu lực theo dòng — ngày của đợt là ngày giao.
    kid = _save(h, {"parent_id": c["id"], "code": "Đ1", "lines": [_line(3.0, from_date="2026-09-20")]})
    assert kid.status_code == 200, kid.text
    assert "from_date" not in kid.json()["contract"]["lines"][0]


def test_single_delivered_contract_line_cannot_start_after_delivery(env) -> None:
    h, cus = env
    body = {"code": "HD-1L", "delivery_type": "single", "contract_type": "spot",
            "customer_id": cus, "sign_date": "2026-09-10", "delivered_at": "2026-09-12",
            "channel": "export", "lines": [_line(10.0), _line(6.0, from_date="2026-09-15")]}
    r = _save(h, body)
    assert r.status_code == 400 and "sau ngày giao" in r.json()["detail"]
    ok = _save(h, {**body, "lines": [_line(10.0), _line(6.0, from_date="2026-09-12")]})
    assert ok.status_code == 200, ok.text


def test_moving_sign_date_past_a_dated_line_is_rejected(env) -> None:
    h, cus = env
    c = _contract(h, cus, lines=[_line(10.0), _line(6.0, from_date="2026-09-15")])
    # Dòng mặc định theo ngày ký mới; dòng có ngày riêng giữ ngày của nó.
    moved = _save(h, {**c, "sign_date": "2026-09-12"})
    assert moved.status_code == 200, moved.text
    assert _block3(h, "2026-09-11") == pytest.approx(0.0)
    assert _block3(h, "2026-09-12") == pytest.approx(10.0)
    assert _block3(h, "2026-09-15") == pytest.approx(16.0)
    r = _save(h, {**c, "sign_date": "2026-09-16"})
    assert r.status_code == 400 and "trước ngày ký" in r.json()["detail"]


def test_switch_to_multi_keeps_dates_on_the_contract_not_the_batch(env) -> None:
    h, cus = env
    c = _save(h, {"code": "HD-SW", "delivery_type": "single", "contract_type": "spot",
                  "customer_id": cus, "sign_date": "2026-09-10", "delivered_at": "2026-09-20",
                  "channel": "export",
                  "lines": [_line(10.0), _line(6.0, from_date="2026-09-15")]}).json()["contract"]
    r = client.put(f"/api/sales-contracts/{c['id']}/delivery-type",
                   json={"delivery_type": "multi"}, headers=h)
    assert r.status_code == 200, r.text
    d = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()
    assert d["contract"]["lines"][1]["from_date"] == "2026-09-15"
    batch = d["children"][0]
    assert [ln.get("from_date") for ln in batch["lines"]] == [None, None]
    assert [ln["qty"] for ln in batch["lines"]] == [10.0, 6.0]
    assert _block3(h, "2026-09-14") == pytest.approx(10.0)
    assert _block3(h, "2026-09-20") == pytest.approx(0.0)


def test_lock_snapshot_treats_effective_date_as_a_number_bearing_field() -> None:
    """Dời ngày hiệu lực là dời phần "đã ký HĐ chưa giao" sang ngày khác ⇒ không phải sửa an toàn.
    Còn form gửi đúng ngày ký (server lưu trống) thì phải so ra BẰNG, không báo "đổi số liệu"."""
    old = {"id": 1, "company": "X", "sign_date": "2026-09-10",
           "lines": [{"grade": SVR, "qty": 10.0, "price": 40.0, "ccy": "VND"},
                     {"grade": SVR, "qty": 6.0, "price": 40.0, "ccy": "VND",
                      "from_date": "2026-09-15"}]}
    moved = {**old, "lines": [old["lines"][0], {**old["lines"][1], "from_date": "2026-09-16"}]}
    same = {**old, "lines": [{**old["lines"][0], "from_date": "2026-09-10"}, old["lines"][1]]}
    assert not sales_contract_lock.is_safe_edit(old, moved)
    assert sales_contract_lock.is_safe_edit(old, same)


def test_edit_request_payload_keeps_the_effective_date() -> None:
    """Đề nghị sửa lưu payload qua `ContractIn` — thiếu ô ở schema là ngày bị nuốt khi Ban duyệt."""
    p = parse(ContractIn, {"company": "X", "code": "HD", "lines": [
        {"grade": SVR, "qty": 6, "from_date": "2026-09-15"}]}).model_dump()
    assert p["lines"][0]["from_date"] == "2026-09-15"


def test_fixing_a_mistyped_sign_date_keeps_the_line_date(env) -> None:
    """Sửa nhầm ngày ký 10 → 15 rồi sửa lại 10: dòng "từ 15" vẫn là từ 15 (rà soát 30/09/2026)."""
    h, cus = env
    c = _contract(h, cus, lines=[_line(10.0), _line(6.0, from_date="2026-09-15")])
    c = _save(h, {**c, "sign_date": "2026-09-15"}).json()["contract"]
    back = _save(h, {**c, "sign_date": "2026-09-10"})
    assert back.status_code == 200, back.text
    assert back.json()["contract"]["lines"][1]["from_date"] == "2026-09-15"
    assert _block3(h, "2026-09-14") == pytest.approx(10.0)


def test_batch_cannot_deliver_a_grade_before_its_line_is_effective(env) -> None:
    """Chủng loại thêm sau (SVR 3L từ 15/09) mà đợt giao 12/09 đã có SVR 3L → chặn cả hai chiều:
    thêm đợt giao, và dời ngày hiệu lực ra sau một đợt đã giao."""
    h, cus = env
    c = _contract(h, cus, lines=[_line(10.0), {**_line(6.0, from_date="2026-09-15"), "grade": "SVR 3L"}])
    early = {"parent_id": c["id"], "code": "Đ1", "delivered_at": "2026-09-12", "channel": "export",
             "lines": [{**_line(6.0), "grade": "SVR 3L"}]}
    r = _save(h, early)
    assert r.status_code == 400 and "hiệu lực từ 15/09/2026" in r.json()["detail"]
    # Chủng loại đã có từ ngày ký thì giao lúc nào cũng được.
    assert _save(h, {**early, "lines": [_line(4.0)]}).status_code == 200
    ok = _save(h, {**early, "code": "Đ2", "delivered_at": "2026-09-16"})
    assert ok.status_code == 200, ok.text
    moved = _save(h, {**c, "lines": [_line(10.0), {**_line(6.0, from_date="2026-09-17"), "grade": "SVR 3L"}]})
    assert moved.status_code == 400 and "Đợt giao Đ2" in moved.json()["detail"]


def test_completion_cannot_precede_a_line_effective_date(env) -> None:
    h, cus = env
    c = _contract(h, cus, lines=[_line(10.0), _line(6.0, from_date="2026-09-20")])
    r = client.put(f"/api/sales-contracts/{c['id']}/completion",
                   json={"completed_at": "2026-09-13"}, headers=h)
    assert r.status_code == 400 and "20/09/2026" in r.json()["detail"]
    ok = client.put(f"/api/sales-contracts/{c['id']}/completion",
                    json={"completed_at": "2026-09-20"}, headers=h)
    assert ok.status_code == 200, ok.text


def test_a_malformed_date_written_by_hand_does_not_break_reports(env) -> None:
    """Mọi đường ghi đều kiểm ngày, nhưng một chuỗi hỏng ghi bằng SQL tay không được làm sập MỌI
    báo cáo dùng khối 3 — dòng đó coi như theo ngày ký."""
    h, cus = env
    c = _contract(h, cus)
    with session_scope() as db:
        db.execute(text("UPDATE sales_contract SET lines = jsonb_set(lines, '{0,from_date}', "
                        "'\"15/09/2026\"') WHERE id = :i"), {"i": c["id"]})
    assert _block3(h, "2026-09-10") == pytest.approx(10.0)


def test_line_cannot_start_after_contract_expiry(env) -> None:
    h, cus = env
    c = _contract(h, cus, expiry_date="2026-12-31")
    r = _save(h, {**c, "lines": [*c["lines"], _line(6.0, from_date="2027-01-05")]})
    assert r.status_code == 400 and "sau thời hạn hợp đồng" in r.json()["detail"]


def test_saving_a_contract_resyncs_group_inventory_from_the_first_changed_day(env, monkeypatch) -> None:
    """Tồn kho Tập đoàn tính lại TỪ ngày sớm nhất bị ảnh hưởng, không chỉ tuần đang chạy."""
    from app.services import inventory_auto

    seen: list = []
    monkeypatch.setattr(inventory_auto, "sync_since_async", lambda day, by=None: seen.append(day))
    h, cus = env
    c = _contract(h, cus)
    assert seen[-1] == "2026-09-10"                                   # tạo mới: từ ngày ký
    _save(h, {**c, "lines": [*c["lines"], _line(6.0, from_date="2026-09-15")]})
    assert seen[-1] == "2026-09-15"                                   # chỉ từ ngày của dòng thêm
    c = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()["contract"]
    _save(h, {**c, "note": "chỉ sửa ghi chú"})
    assert seen[-1] is None                                           # không đổi sản lượng nào


def test_block3_footprint_and_week_range() -> None:
    from app.services import inventory_auto, sales_contract_line_dates as ld

    base = {"parent_id": None, "sign_date": "2026-09-10", "delivered_at": None,
            "lines": [{"grade": SVR, "qty": 10.0}]}
    more = {**base, "lines": [*base["lines"], {"grade": SVR, "qty": 6.0, "from_date": "2026-09-15"}]}
    assert ld.block3_changed_since(base, more) == "2026-09-15"
    assert ld.block3_changed_since(base, {**base, "sign_date": "2026-09-12"}) == "2026-09-10"
    assert ld.block3_changed_since(base, {**base, "note": "x"}) is None
    batch = {"parent_id": 1, "delivered_at": "2026-09-20", "lines": [{"grade": SVR, "qty": 4.0}]}
    assert ld.block3_changed_since(batch, None) == "2026-09-20"
    assert ld.block3_changed_since(None, {**batch, "delivered_at": None}) is None   # đợt chưa giao
    far = "2999-01-01"
    assert inventory_auto.anchors_since(far) == []                   # dòng hiệu lực tương lai
    weeks = inventory_auto.anchors_since("2000-01-01")
    assert len(weeks) == inventory_auto.MAX_RECOMPUTE_WEEKS and weeks == sorted(weeks)


def test_assistant_counts_a_top_up_in_the_period_it_takes_effect(env) -> None:
    """"Hợp đồng ký mới trong kỳ" của Trợ lý: phần bổ sung tính vào kỳ CÓ HIỆU LỰC, không dồn về kỳ ký."""
    from app.services import sales_contract_signed_volume as sv
    from app.services.assistant_tools.contract_tools import _contract_summary

    h, cus = env
    c = _contract(h, cus, sign_date="2031-08-20", lines=[_line(10.0)])
    _save(h, {**c, "lines": [*c["lines"], _line(6.0, from_date="2031-09-15")]})
    aug = sv.by_company("2031-08-01", "2031-08-31", [UNIT])[UNIT]
    sep = sv.by_company("2031-09-01", "2031-09-30", [UNIT])[UNIT]
    assert (aug["qty"], aug["topup_qty"]) == (10.0, 0.0)
    assert (sep["qty"], sep["topup_qty"], sep["topup_contracts"]) == (6.0, 6.0, 1)
    s = _contract_summary({"date_from": "2031-09-01", "date_to": "2031-09-30"})["summary"]
    assert s["so_hop_dong"] == 0 and s["tong_cam_ket_tan"] == 6.0
    assert s["trong_do_bo_sung_hd_ky_truoc_tan"] == 6.0


def test_background_resync_runs_one_worker_and_merges_bursts(monkeypatch) -> None:
    """Lưu dồn dập trong lúc đang tính: không mở thêm luồng, gộp thành MỘT lượt từ ngày sớm nhất."""
    import threading
    import time

    from app.services import inventory_auto

    gate, calls = threading.Event(), []

    def slow(day, by=None):
        calls.append(day)
        if len(calls) == 1:
            gate.wait(5)
        return []

    monkeypatch.setattr(inventory_auto, "enabled", lambda: True)
    monkeypatch.setattr(inventory_auto, "sync_since", slow)
    inventory_auto.sync_since_async("2026-09-20")
    time.sleep(0.2)                                   # luồng đầu đang chạy, chặn ở `gate`
    for day in ("2026-09-15", "2026-09-10", "2026-09-18"):
        inventory_auto.sync_since_async(day)
    gate.set()
    for _ in range(50):
        if not inventory_auto._worker_running:
            break
        time.sleep(0.1)
    assert calls == ["2026-09-20", "2026-09-10"]
