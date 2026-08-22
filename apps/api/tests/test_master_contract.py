"""Test HỢP ĐỒNG MẸ (HĐNT/HĐDH) + nối PHỤ LỤC về hợp đồng mẹ.

Khoá 3 điều dễ vỡ nhất:
  1. Phụ lục THỪA KẾ khách hàng của hợp đồng mẹ (client gửi khách khác cũng không được ghi đè) —
     nếu không, báo cáo theo khách hàng sẽ rơi hết vào rổ "chưa gán".
  2. Hợp đồng mẹ KHÔNG góp sản lượng vào tiêu thụ / "đã ký HĐ chưa giao" (cộng cả 2 cấp = đếm đôi).
  3. Phạm vi đơn vị: không nối được phụ lục vào hợp đồng mẹ của đơn vị khác.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

UNIT = "_zz_mc_unit"
UNIT2 = "_zz_mc_unit2"
TODAY = date.today().isoformat()


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup(h: dict[str, str]) -> None:
    units = [UNIT, UNIT2]
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = ANY(:u)"), {"u": units})
        db.execute(text("DELETE FROM master_contract WHERE company = ANY(:u)"), {"u": units})
        db.execute(text("DELETE FROM unit_customer WHERE company = ANY(:u)"), {"u": units})
    for n in units:
        client.delete(f"/api/member-units/{n}", headers=h)


@pytest.fixture()
def env():
    h = _admin()
    _cleanup(h)
    for n in (UNIT, UNIT2):
        client.post("/api/member-units", json={"name": n}, headers=h)
    yield h
    _cleanup(h)


def _customer(h, company=UNIT, name="KH hợp đồng mẹ") -> int:
    return client.put("/api/customers", json={"company": company, "name": name},
                      headers=h).json()["id"]


def _master(h, cus: int, company=UNIT, code="HDNT-01", master_type="principle", **kw) -> dict:
    body = {"company": company, "code": code, "master_type": master_type, "customer_id": cus,
            "sign_date": TODAY, "lines": [{"grade": "SVR 10 / CSR 10", "qty": 500.0}], **kw}
    r = client.put("/api/master-contracts", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["master"]


def _annex(h, master_id: int | None, code="PL-01", **kw) -> dict:
    body = {"company": UNIT, "code": code, "contract_type": "long_term", "sign_date": TODAY,
            "master_id": master_id,
            "lines": [{"grade": "SVR 10 / CSR 10", "qty": 100.0, "price": 40.0, "ccy": "VND"}],
            **kw}
    return client.put("/api/sales-contracts", json=body, headers=h)


def test_master_requires_customer_type_and_grade(env) -> None:
    h = env
    cus = _customer(h)
    base = {"company": UNIT, "code": "HDNT-X", "master_type": "principle", "customer_id": cus,
            "lines": [{"grade": "SVR 10 / CSR 10"}]}

    no_type = client.put("/api/master-contracts", json={**base, "master_type": ""}, headers=h)
    assert no_type.status_code == 400 and "loại hợp đồng mẹ" in no_type.json()["detail"]

    no_cus = client.put("/api/master-contracts", json={**base, "customer_id": None}, headers=h)
    assert no_cus.status_code == 400 and "khách hàng" in no_cus.json()["detail"]

    no_line = client.put("/api/master-contracts", json={**base, "lines": []}, headers=h)
    assert no_line.status_code == 400 and "ít nhất một chủng loại" in no_line.json()["detail"]

    bad_grade = client.put("/api/master-contracts",
                           json={**base, "lines": [{"grade": "SVR 999"}]}, headers=h)
    assert bad_grade.status_code == 400 and "không có trong danh mục" in bad_grade.json()["detail"]

    # HĐ nguyên tắc thường KHÔNG chốt số lượng/đơn giá → chỉ chủng loại vẫn lưu được.
    assert client.put("/api/master-contracts", json=base, headers=h).status_code == 200


def test_master_price_needs_fx_only_when_priced(env) -> None:
    h = env
    cus = _customer(h)
    base = {"company": UNIT, "code": "HDDH-FX", "master_type": "long_term", "customer_id": cus}

    # Đơn giá USD mà thiếu tỷ giá → chặn (giống dòng hợp đồng bán).
    bad = client.put("/api/master-contracts", headers=h, json={
        **base, "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10, "price": 1600, "ccy": "USD"}]})
    assert bad.status_code == 400 and "tỷ giá" in bad.json()["detail"]

    # Chưa có đơn giá thì chưa cần tỷ giá — chưa có gì để quy đổi.
    ok = client.put("/api/master-contracts", headers=h, json={
        **base, "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10, "ccy": "USD"}]})
    assert ok.status_code == 200, ok.text

    # Loại tiền ngoài danh mục phải BÁO LỖI, không lặng lẽ quy về VNĐ (đơn giá 1.600 EUR/tấn đọc
    # thành 1.600 TRIỆU đ/tấn là sai ~38 lần).
    ccy = client.put("/api/master-contracts", headers=h, json={
        **base, "code": "HDDH-FX2",
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10, "price": 5, "ccy": "EUR"}]})
    assert ccy.status_code == 400 and "loại tiền" in ccy.json()["detail"]


def test_master_code_unique_per_unit(env) -> None:
    h = env
    _master(h, _customer(h))
    dup = client.put("/api/master-contracts", headers=h, json={
        "company": UNIT, "code": "hdnt-01", "master_type": "long_term",
        "customer_id": _customer(h, UNIT, "KH khác"),
        "lines": [{"grade": "SVR 10 / CSR 10"}]})
    assert dup.status_code == 400 and "đã có hợp đồng mẹ" in dup.json()["detail"]
    # Đơn vị KHÁC trùng số → cho phép (hồ sơ tách riêng theo đơn vị).
    assert _master(h, _customer(h, UNIT2, "KH đv2"), company=UNIT2)["code"] == "HDNT-01"


def test_annex_inherits_customer_from_master(env) -> None:
    h = env
    cus, other = _customer(h), _customer(h, UNIT, "KH KHÔNG được dùng")
    m = _master(h, cus, code="HDDH-2026", master_type="long_term",
                price_formula="Giá SICOM TSR20 bình quân tuần trước + 30 USD/tấn")

    # Client cố gửi khách hàng KHÁC → server vẫn ghi khách của hợp đồng mẹ.
    r = _annex(h, m["id"], customer_id=other)
    assert r.status_code == 200, r.text
    c = r.json()["contract"]
    assert c["master_id"] == m["id"] and c["customer_id"] == cus

    # Đổi khách ở hợp đồng mẹ → phụ lục đi theo (không để phụ lục mang khách cũ).
    moved = _customer(h, UNIT, "KH chuyển sang")
    client.put("/api/master-contracts", headers=h,
               json={**m, "customer_id": moved, "lines": m["lines"]})
    detail = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()
    assert detail["contract"]["customer_id"] == moved
    assert detail["master"]["code"] == "HDDH-2026"
    assert "SICOM" in detail["master"]["price_formula"]

    # Danh sách hợp đồng kèm SỐ HỢP ĐỒNG MẸ để bảng hiện "phụ lục của HĐ …".
    row = next(x for x in client.get("/api/sales-contracts", headers=h,
                                     params={"company": UNIT}).json()["contracts"]
               if x["id"] == c["id"])
    assert row["master_code"] == "HDDH-2026"


def test_annex_without_master_still_needs_customer(env) -> None:
    h = env
    r = _annex(h, None, code="HD-DOC-LAP")
    assert r.status_code == 400 and "khách hàng" in r.json()["detail"]
    assert _annex(h, None, code="HD-DOC-LAP", customer_id=_customer(h)).status_code == 200


def test_master_of_other_unit_is_rejected(env) -> None:
    h = env
    m2 = _master(h, _customer(h, UNIT2, "KH đv2"), company=UNIT2, code="HDNT-DV2")
    r = _annex(h, m2["id"], code="PL-CHEO")
    assert r.status_code == 400 and "đơn vị khác" in r.json()["detail"]


def test_master_tracks_annexes_and_blocks_delete(env) -> None:
    h = env
    m = _master(h, _customer(h), code="HDDH-TD", master_type="long_term")
    for i in (1, 2):
        assert _annex(h, m["id"], code=f"PL-{i}").status_code == 200

    detail = client.get(f"/api/master-contracts/{m['id']}", headers=h).json()
    assert len(detail["annexes"]) == 2 and detail["annex_qty"] == pytest.approx(200.0)
    row = client.get("/api/master-contracts", headers=h,
                     params={"company": UNIT}).json()["items"][0]
    assert row["annexes"] == 2 and row["annex_qty"] == pytest.approx(200.0)
    assert row["qty"] == pytest.approx(500.0)   # cam kết ghi trên hợp đồng mẹ

    dele = client.delete(f"/api/master-contracts/{m['id']}", headers=h)
    assert dele.status_code == 400 and "2 phụ lục" in dele.json()["detail"]


def test_master_qty_stays_out_of_consumption(env) -> None:
    """Hợp đồng mẹ cam kết 500 t nhưng CHỈ phụ lục mới vào tiêu thụ / khối 3 (không đếm đôi)."""
    h = env
    m = _master(h, _customer(h), code="HDDH-KHONG-DEM", master_type="long_term")
    assert _annex(h, m["id"], code="PL-GIAO", delivered_at=TODAY,
                  channel="domestic").status_code == 200

    rep = client.get("/api/sales-contracts/consumption", headers=h,
                     params={"date_from": TODAY, "date_to": TODAY, "company": UNIT}).json()
    assert rep["by_company"][UNIT]["qty"] == pytest.approx(100.0)
    assert rep["undelivered"].get(UNIT, {"qty": 0})["qty"] == pytest.approx(0.0)


def test_batch_never_links_to_master(env) -> None:
    """ĐỢT GIAO nằm trong phụ lục — nối thẳng vào hợp đồng mẹ sẽ cộng đôi sản lượng đã ký."""
    h = env
    m = _master(h, _customer(h), code="HDDH-DOT", master_type="long_term")
    parent = _annex(h, m["id"], code="PL-MULTI", delivery_type="multi").json()["contract"]
    batch = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "parent_id": parent["id"], "master_id": m["id"], "code": "Đợt 1",
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 50.0, "price": 40.0, "ccy": "VND"}]})
    assert batch.status_code == 200, batch.text
    assert batch.json()["contract"]["master_id"] is None
    detail = client.get(f"/api/master-contracts/{m['id']}", headers=h).json()
    assert detail["annex_qty"] == pytest.approx(100.0)   # chỉ phụ lục, không cộng đợt giao


def _link(h, master_id: int, ids: list[int], attach: bool = True):
    return client.put(f"/api/master-contracts/{master_id}/annexes", headers=h,
                      json={"contract_ids": ids, "attach": attach})


def test_attach_existing_contract_takes_master_customer(env) -> None:
    """Gắn hợp đồng ĐÃ CÓ vào hợp đồng mẹ — đường dọn hồ sơ cũ (chiều ngược của ô ở form)."""
    h = env
    own, master_cus = _customer(h, UNIT, "KH riêng của HĐ"), _customer(h)
    m = _master(h, master_cus, code="HDDH-GAN", master_type="long_term")
    c = _annex(h, None, code="HD-CO-SAN", customer_id=own).json()["contract"]
    assert c["master_id"] is None and c["customer_id"] == own

    r = _link(h, m["id"], [c["id"]])
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1 and len(r.json()["annexes"]) == 1
    after = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()["contract"]
    # Gắn vào = thừa kế khách của hợp đồng mẹ (ghi đè khách riêng đang có).
    assert after["master_id"] == m["id"] and after["customer_id"] == master_cus

    # Gỡ ra: GIỮ khách đang có — hợp đồng bắt buộc có khách, xoá đi là bản ghi hỏng.
    assert _link(h, m["id"], [c["id"]], attach=False).status_code == 200
    off = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()["contract"]
    assert off["master_id"] is None and off["customer_id"] == master_cus


def test_attach_rejects_other_unit_batch_and_taken_contract(env) -> None:
    h = env
    m = _master(h, _customer(h), code="HDNT-CHECK")

    # Hợp đồng của đơn vị khác → chặn.
    other = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT2, "code": "HD-DV2", "contract_type": "spot", "sign_date": TODAY,
        "customer_id": _customer(h, UNIT2, "KH đv2 khác"),
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}],
    }).json()["contract"]
    bad = _link(h, m["id"], [other["id"]])
    assert bad.status_code == 400 and "đơn vị khác" in bad.json()["detail"]

    # ĐỢT GIAO không gắn thẳng vào hợp đồng mẹ (sẽ cộng đôi sản lượng đã ký).
    parent = _annex(h, None, code="HD-MULTI", delivery_type="multi",
                    customer_id=_customer(h, UNIT, "KH multi")).json()["contract"]
    batch = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "parent_id": parent["id"], "code": "Đợt 1",
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 20.0, "price": 40.0, "ccy": "VND"}],
    }).json()["contract"]
    is_batch = _link(h, m["id"], [batch["id"]])
    assert is_batch.status_code == 400 and "ĐỢT GIAO" in is_batch.json()["detail"]

    # Hợp đồng đang thuộc hồ sơ khác → chặn, không lặng lẽ kéo sang hồ sơ này.
    mine = _annex(h, m["id"], code="PL-CUA-M1").json()["contract"]
    m3 = _master(h, _customer(h, UNIT, "KH hồ sơ 3"), code="HDNT-3")
    moved = _link(h, m3["id"], [mine["id"]])
    assert moved.status_code == 400 and "hợp đồng mẹ khác" in moved.json()["detail"]

    # Gỡ một hợp đồng không thuộc hồ sơ này → chặn.
    off = _link(h, m3["id"], [mine["id"]], attach=False)
    assert off.status_code == 400 and "không phải phụ lục" in off.json()["detail"]


def test_unlinked_filter_feeds_the_annex_picker(env) -> None:
    """Ô chọn phụ lục chỉ bày hợp đồng CHƯA có hợp đồng mẹ."""
    h = env
    m = _master(h, _customer(h), code="HDNT-LOC")
    free = _annex(h, None, code="HD-TU-DO",
                  customer_id=_customer(h, UNIT, "KH tự do")).json()["contract"]
    taken = _annex(h, m["id"], code="PL-DA-GAN").json()["contract"]

    rows = client.get("/api/sales-contracts", headers=h,
                      params={"company": UNIT, "unlinked": "true"}).json()["contracts"]
    ids = {r["id"] for r in rows}
    assert free["id"] in ids and taken["id"] not in ids


def test_price_formula_belongs_to_long_term_only(env) -> None:
    """HĐ nguyên tắc KHÔNG có công thức giá — form ẩn ô, server cũng phải bỏ chữ client gửi lên."""
    h = env
    cus = _customer(h)
    body = {"company": UNIT, "customer_id": cus, "lines": [{"grade": "SVR 10 / CSR 10"}],
            "price_formula": "SICOM + 30 USD/tấn"}

    nt = client.put("/api/master-contracts", headers=h,
                    json={**body, "code": "HDNT-CT", "master_type": "principle"})
    assert nt.status_code == 200 and nt.json()["master"]["price_formula"] is None

    dh = client.put("/api/master-contracts", headers=h,
                    json={**body, "code": "HDDH-CT", "master_type": "long_term"})
    assert dh.json()["master"]["price_formula"] == "SICOM + 30 USD/tấn"

    # Đổi HĐ dài hạn → nguyên tắc thì công thức cũ phải rơi ra, không nằm lại trong bản ghi.
    back = client.put("/api/master-contracts", headers=h,
                      json={**dh.json()["master"], "master_type": "principle"})
    assert back.json()["master"]["price_formula"] is None


def test_contract_list_filters_by_master(env) -> None:
    """Màn Hợp đồng lọc được theo HỒ SƠ MẸ, và lọc ngược "chưa gắn hồ sơ" để rà bản ghi còn sót."""
    h = env
    m = _master(h, _customer(h), code="HDDH-LOC-DS", master_type="long_term")
    annex = _annex(h, m["id"], code="PL-TRONG-HO-SO").json()["contract"]
    free = _annex(h, None, code="HD-NGOAI-HO-SO",
                  customer_id=_customer(h, UNIT, "KH ngoài hồ sơ")).json()["contract"]

    only = client.get("/api/sales-contracts", headers=h,
                      params={"company": UNIT, "master_id": m["id"]}).json()
    assert {r["id"] for r in only["contracts"]} == {annex["id"]}
    assert only["total"] == 1
    # Dòng tổng cộng phải cộng theo ĐÚNG bộ lọc, không phải toàn bộ đơn vị.
    assert only["totals"]["qty"] == pytest.approx(annex["qty"])

    rest = client.get("/api/sales-contracts", headers=h,
                      params={"company": UNIT, "unlinked": "true"}).json()
    ids = {r["id"] for r in rest["contracts"]}
    assert free["id"] in ids and annex["id"] not in ids
