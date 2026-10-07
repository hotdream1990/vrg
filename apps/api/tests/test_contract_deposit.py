"""Test TIỀN ĐẶT CỌC (nhiều đợt cọc) + CHỈ THỊ GIAO HÀNG của hợp đồng bán (07/10/2026): lưu ·
kiểm đơn vị tính · chỉ ở hợp đồng · sửa được sau chốt số liệu · file chứng từ tải được."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

# Tên đơn vị RIÊNG của file này — chạy cạnh test_sales_contract.py không dẫm dữ liệu của nhau.
UNIT = "_zz_dep_unit"
MEMBER = "zz_dep_mem"
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def _admin() -> dict[str, str]:
    user_repo.seed_admin()
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = :u"), {"u": UNIT})
        db.execute(text("DELETE FROM unit_customer WHERE company = :u"), {"u": UNIT})
    client.delete(f"/api/users/{MEMBER}", headers=h)
    client.delete(f"/api/member-units/{UNIT}", headers=h)


@pytest.fixture()
def env():
    h = _admin()
    _cleanup(h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH cọc"},
                     headers=h).json()["id"]
    yield h, cus
    _cleanup(h)


def _line(qty=100.0, price=40.0, ccy="VND", **kw) -> dict:
    return {"grade": "SVR 10 / CSR 10", "qty": qty, "price": price, "ccy": ccy, **kw}


def _contract(cus: int, **kw) -> dict:
    return {"company": UNIT, "code": "HD-COC", "delivery_type": "single", "contract_type": "spot",
            "customer_id": cus, "sign_date": YESTERDAY, "lines": [_line()], **kw}


def _dep(amount=None, ccy="VND", day=None, docs=None) -> dict:
    return {"amount": amount, "ccy": ccy, "date": day, "docs": docs or []}


def test_many_deposits_are_saved_on_the_contract(env) -> None:
    h, cus = env
    up = client.post("/api/sales-contracts/file", headers=h,
                     files={"file": ("coc.pdf", b"%PDF-1.4 coc", "application/pdf")})
    assert up.status_code == 200, up.text
    doc = {"file": up.json()["file"], "filename": up.json()["filename"]}
    r = client.put("/api/sales-contracts", headers=h, json=_contract(cus, deposits=[
        _dep(400.5, day=YESTERDAY, docs=[doc]), _dep(), _dep(600, day=TODAY)]))
    assert r.status_code == 200, r.text
    deps = r.json()["contract"]["deposits"]
    # Đợt trống hẳn bị bỏ; thứ tự người nhập được giữ.
    assert [d["amount"] for d in deps] == [400.5, 600]
    assert deps[0]["date"] == YESTERDAY and deps[0]["docs"][0]["file"] == doc["file"]
    # File chỉ gắn ở CHỨNG TỪ CỌC (lồng trong đợt cọc) vẫn phải tải được — thiếu là 404.
    from app.services import sales_contract_repo
    assert sales_contract_repo.companies_of_file(doc["file"]) == {UNIT}
    assert client.get(f"/api/sales-contracts/file/{doc['file']}", headers=h).status_code == 200


def test_total_deposit_larger_than_contract_value_is_rejected(env) -> None:
    """100 t × 40 triệu = 4.000 triệu: TỔNG các đợt cọc vượt giá trị hợp đồng → chặn."""
    h, cus = env
    r = client.put("/api/sales-contracts", headers=h,
                   json=_contract(cus, deposits=[_dep(2500), _dep(2000)]))
    assert r.status_code == 400 and "Tổng tiền cọc" in r.json()["detail"]
    # Gõ ĐỒNG vào ô triệu đồng ở một đợt cũng bị bắt.
    big = client.put("/api/sales-contracts", headers=h,
                     json=_contract(cus, deposits=[_dep(400_000_000)]))
    assert big.status_code == 400
    ok = client.put("/api/sales-contracts", headers=h,
                    json=_contract(cus, deposits=[_dep(2000), _dep(2000)]))
    assert ok.status_code == 200, ok.text


def test_deposit_in_another_currency_is_not_compared(env) -> None:
    """Hợp đồng USD cọc bằng VNĐ: không quy đổi được (chưa có tỷ giá) → không chặn, không đoán."""
    h, cus = env
    r = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, lines=[_line(price=1800.0, ccy="USD")], deposits=[_dep(5000, "VND")]))
    assert r.status_code == 200, r.text
    usd = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, code="HD-USD", lines=[_line(price=1800.0, ccy="USD")],
        deposits=[_dep(100_000, "USD"), _dep(100_000, "USD")]))
    assert usd.status_code == 400 and "USD" in usd.json()["detail"]


def test_invalid_deposit_inputs_are_rejected(env) -> None:
    h, cus = env
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    for bad in (_dep(-1), _dep(10, "EUR"), _dep(10, day="07/10/2026"), _dep(10, day=tomorrow)):
        r = client.put("/api/sales-contracts", headers=h, json=_contract(cus, deposits=[_dep(1), bad]))
        assert r.status_code == 400 and "Đợt cọc 2" in r.json()["detail"], (bad, r.text)


def test_currency_without_amount_is_dropped_and_zero_price_not_compared(env) -> None:
    h, cus = env
    r = client.put("/api/sales-contracts", headers=h,
                   json=_contract(cus, deposits=[_dep(None, "USD", day=YESTERDAY)]))
    assert r.status_code == 200, r.text
    d = r.json()["contract"]["deposits"][0]
    assert d["amount"] is None and d["ccy"] is None and d["date"] == YESTERDAY
    # Giá 0 = chưa chốt giá (phụ lục theo công thức) → không so, không chặn oan.
    ok = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, code="HD-GIA0", lines=[_line(price=0.0)], deposits=[_dep(500)]))
    assert ok.status_code == 200, ok.text


def test_batch_never_carries_a_deposit(env) -> None:
    """Cọc thuộc HỢP ĐỒNG — đợt giao gửi kèm cũng bị bỏ, không nhân đôi khoản cọc."""
    h, cus = env
    parent = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, delivery_type="multi", deposits=[_dep(100)])).json()["contract"]
    kid = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "parent_id": parent["id"], "code": "D1", "delivered_at": TODAY,
        "channel": "export", "lines": [_line(qty=10.0, source="exploit")],
        "deposits": [_dep(50, day=TODAY)]})
    assert kid.status_code == 200, kid.text
    assert kid.json()["contract"]["deposits"] == []
    got = client.get(f"/api/sales-contracts/{parent['id']}", headers=h).json()["contract"]
    assert [d["amount"] for d in got["deposits"]] == [100]


def test_deposit_is_editable_after_the_data_lock(env) -> None:
    """Cọc là số ghi nhận, không dịch số báo cáo nào ⇒ đơn vị bổ sung đợt cọc cả khi đã chốt."""
    from app.services import data_lock_repo

    h, cus = env
    client.post("/api/users", headers=h, json={"username": MEMBER, "password": "pass123",
                                               "role": "member", "member_units": [UNIT]})
    mh = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": MEMBER, "password": "pass123"}).json()["access_token"]}
    body = _contract(cus, sign_date=TODAY, delivered_at=TODAY, channel="export",
                     lines=[_line(qty=50.0, source="exploit")])
    made = client.put("/api/sales-contracts", headers=mh, json=body)
    assert made.status_code == 200, made.text
    cid = made.json()["contract"]["id"]

    rnd = data_lock_repo.save_round(TODAY, "test", "admin")
    data_lock_repo.confirm(rnd["id"], UNIT, MEMBER)
    try:
        ok = client.put("/api/sales-contracts", headers=mh, json={
            **body, "id": cid, "deposits": [_dep(300, day=TODAY), _dep(200, day=TODAY)]})
        assert ok.status_code == 200, ok.text
        assert len(ok.json()["contract"]["deposits"]) == 2
        meta = client.get("/api/sales-contracts/meta", headers=mh).json()
        assert "deposits" in {f["key"] for f in meta["editable_when_locked"]}
    finally:
        data_lock_repo.delete_round(rnd["id"])


def test_delivery_instruction_lives_on_each_delivery(env) -> None:
    """Chỉ thị giao hàng: HĐ giao 1 lần mang trên chính nó; HĐ giao nhiều lần thì ở từng đợt."""
    h, cus = env
    later = (date.today() + timedelta(days=10)).isoformat()
    doc = {"file": "chi-thi-1.pdf", "filename": "chi thi.pdf"}
    one = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, instruction_date=later, instruction_place="Cảng Cát Lái", instruction_docs=[doc]))
    assert one.status_code == 200, one.text
    c = one.json()["contract"]
    assert (c["instruction_date"], c["instruction_place"]) == (later, "Cảng Cát Lái")
    from app.services import sales_contract_repo
    assert sales_contract_repo.companies_of_file("chi-thi-1.pdf") == {UNIT}

    multi = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, code="HD-NHIEU", delivery_type="multi", instruction_place="bỏ"))
    assert multi.json()["contract"]["instruction_place"] is None
    kid = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "parent_id": multi.json()["contract"]["id"], "code": "D1",
        "lines": [_line(qty=10.0)], "instruction_date": later, "instruction_place": "Kho Bình Dương"})
    assert kid.status_code == 200, kid.text
    assert kid.json()["contract"]["instruction_place"] == "Kho Bình Dương"


def test_old_client_without_new_keys_keeps_stored_values(env) -> None:
    """Web bản cũ / đề nghị gửi trước 07/10/2026 không có khoá cọc + chỉ thị → lưu KHÔNG xoá trắng."""
    from app.services import contract_compat

    h, cus = env
    made = client.put("/api/sales-contracts", headers=h, json=_contract(
        cus, deposits=[_dep(300, day=YESTERDAY)], instruction_place="Cảng Cát Lái")).json()["contract"]
    old_body = _contract(cus, id=made["id"], note="sửa ghi chú")
    r = client.put("/api/sales-contracts", headers=h, json=old_body)
    assert r.status_code == 200, r.text
    c = r.json()["contract"]
    assert [d["amount"] for d in c["deposits"]] == [300] and c["instruction_place"] == "Cảng Cát Lái"
    assert c["note"] == "sửa ghi chú"
    # Gửi khoá cọc tường minh = người gửi biết ô cọc → xoá được thật.
    cleared = client.put("/api/sales-contracts", headers=h,
                         json={**old_body, "deposits": []}).json()["contract"]
    assert cleared["deposits"] == [] and cleared["instruction_place"] == "Cảng Cát Lái"
    # Đường duyệt đề nghị: thân lưu trước khi có ô mới không mang khoá → giữ số đang lưu.
    kept = contract_compat.fill_missing({"id": made["id"]}, {"deposits": [_dep(7)]})
    assert kept["deposits"][0]["amount"] == 7 and kept["instruction_docs"] == []
