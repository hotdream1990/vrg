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


def _default_customer(h) -> int:
    """Khách mặc định của UNIT — tạo một lần rồi dùng lại (tên trùng trong đơn vị bị chặn)."""
    got = client.get("/api/customers", headers=h, params={"company": UNIT, "limit": 1}).json()
    return got["items"][0]["id"] if got["items"] else _customer(h)


def _annex(h, master_id: int | None, code="PL-01", **kw) -> dict:
    """Một HỢP ĐỒNG, có/không nối hồ sơ mẹ. Khách hàng LUÔN phải có — nối hồ sơ mẹ không thay
    khách (chốt 24/08/2026), nên mọi hợp đồng vẫn tự khai khách như trước."""
    body = {"company": UNIT, "code": code, "contract_type": "long_term", "sign_date": TODAY,
            "master_id": master_id,
            "customer_id": kw.pop("customer_id", None) or _default_customer(h),
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


def test_linking_a_master_never_touches_contract_data(env) -> None:
    """Nối hợp đồng mẹ CHỈ là liên kết hồ sơ (chốt 24/08/2026).

    Yêu cầu của khách: cấp hợp đồng mẹ phải ảnh hưởng ÍT NHẤT tới luồng hợp đồng & đợt giao cũ.
    Vì vậy hợp đồng giữ nguyên KHÁCH HÀNG của chính nó — đổi khách ở hồ sơ mẹ cũng không kéo theo.
    Bản đầu từng ghi đè khách theo hồ sơ: gắn một hợp đồng cũ vào hồ sơ là lặng lẽ đổi số liệu
    "theo khách hàng" của một kỳ đã chốt.
    """
    h = env
    cus, own = _customer(h), _customer(h, UNIT, "KH riêng của hợp đồng")
    m = _master(h, cus, code="HDDH-2026", master_type="long_term",
                price_formula="Giá SICOM TSR20 bình quân tuần trước + 30 USD/tấn")

    r = _annex(h, m["id"], customer_id=own)
    assert r.status_code == 200, r.text
    c = r.json()["contract"]
    assert c["master_id"] == m["id"] and c["customer_id"] == own

    # Đổi khách ở hợp đồng mẹ → hợp đồng KHÔNG đổi theo.
    moved = _customer(h, UNIT, "KH mới của hồ sơ")
    client.put("/api/master-contracts", headers=h,
               json={**m, "customer_id": moved, "lines": m["lines"]})
    detail = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()
    assert detail["contract"]["customer_id"] == own
    assert detail["master"]["code"] == "HDDH-2026"

    # Hợp đồng nối hồ sơ vẫn BẮT BUỘC tự khai khách hàng như mọi hợp đồng khác.
    no_cus = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "code": "PL-THIEU-KHACH", "contract_type": "long_term",
        "sign_date": TODAY, "master_id": m["id"],
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]})
    assert no_cus.status_code == 400 and "khách hàng" in no_cus.json()["detail"]

    # Danh sách hợp đồng kèm SỐ HỢP ĐỒNG MẸ để bảng hiện "phụ lục của HĐ …".
    row = next(x for x in client.get("/api/sales-contracts", headers=h,
                                     params={"company": UNIT}).json()["contracts"]
               if x["id"] == c["id"])
    assert row["master_code"] == "HDDH-2026"


def test_contract_without_master_still_needs_customer(env) -> None:
    h = env
    r = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "code": "HD-DOC-LAP", "contract_type": "long_term", "sign_date": TODAY,
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]})
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


def test_attach_existing_contract_only_sets_the_link(env) -> None:
    """Gắn hợp đồng ĐÃ CÓ vào hồ sơ — chỉ đổi liên kết, KHÔNG đụng số liệu của hợp đồng."""
    h = env
    own, master_cus = _customer(h, UNIT, "KH riêng của HĐ"), _customer(h)
    m = _master(h, master_cus, code="HDDH-GAN", master_type="long_term")
    c = _annex(h, None, code="HD-CO-SAN", customer_id=own).json()["contract"]
    assert c["master_id"] is None and c["customer_id"] == own

    r = _link(h, m["id"], [c["id"]])
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1 and len(r.json()["annexes"]) == 1
    after = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()["contract"]
    # Khách hàng + sản lượng của hợp đồng giữ NGUYÊN sau khi gắn.
    assert after["master_id"] == m["id"] and after["customer_id"] == own
    assert after["qty"] == pytest.approx(c["qty"])

    assert _link(h, m["id"], [c["id"]], attach=False).status_code == 200
    off = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()["contract"]
    assert off["master_id"] is None and off["customer_id"] == own


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


def test_renaming_a_unit_carries_its_master_contracts(env) -> None:
    """Đổi tên đơn vị phải kéo theo hồ sơ mẹ — bỏ sót thì hồ sơ mồ côi và phụ lục hết sửa được."""
    h = env
    m = _master(h, _customer(h), code="HDDH-DOI-TEN", master_type="long_term")
    annex = _annex(h, m["id"], code="PL-DOI-TEN").json()["contract"]
    new_name = f"{UNIT}_moi"
    try:
        r = client.put(f"/api/member-units/{UNIT}", json={"new_name": new_name}, headers=h)
        assert r.status_code == 200, r.text

        moved = client.get(f"/api/master-contracts/{m['id']}", headers=h).json()["master"]
        assert moved["company"] == new_name
        # Phụ lục vẫn sửa được: hồ sơ mẹ và hợp đồng phải cùng đơn vị sau khi đổi tên.
        again = client.put("/api/sales-contracts", headers=h, json={
            **annex, "company": new_name, "note": "sửa sau khi đổi tên"})
        assert again.status_code == 200, again.text
    finally:
        client.put(f"/api/member-units/{new_name}", json={"new_name": UNIT}, headers=h)


def test_customer_used_only_by_a_master_cannot_be_deleted(env) -> None:
    """Khách chỉ gắn ở HỒ SƠ MẸ (chưa có phụ lục) cũng phải chặn xoá, nếu không hồ sơ trỏ vào id ma."""
    h = env
    cus = _customer(h, UNIT, "KH chỉ ở hồ sơ mẹ")
    _master(h, cus, code="HDNT-KHOA-KHACH")
    r = client.delete(f"/api/customers/{cus}", headers=h)
    assert r.status_code == 400 and "hợp đồng mẹ" in r.json()["detail"]


def test_master_contract_respects_view_and_edit_levels(env) -> None:
    """Quyền `sales_contract` 2 cấp áp cho CẢ hồ sơ mẹ: mức Xem đọc được, mọi đường ghi 403."""
    h = env
    m = _master(h, _customer(h), code="HDNT-QUYEN")
    for u in ("mc_view", "mc_none"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/users", json={"username": "mc_view", "password": "pass123",
                                    "role": "editor", "permissions": ["sales_contract:view"]},
                headers=h)
    client.post("/api/users", json={"username": "mc_none", "password": "pass123",
                                    "role": "editor", "permissions": ["inventory"]}, headers=h)
    tok = lambda u: {"Authorization": "Bearer " + client.post(  # noqa: E731
        "/api/auth/login", json={"username": u, "password": "pass123"}).json()["access_token"]}
    vh, nh = tok("mc_view"), tok("mc_none")

    assert client.get("/api/master-contracts", headers=vh).status_code == 200
    assert client.get(f"/api/master-contracts/{m['id']}", headers=vh).status_code == 200
    body = {"company": UNIT, "code": "HDNT-LEN", "master_type": "principle",
            "customer_id": m["customer_id"], "lines": [{"grade": "SVR 10 / CSR 10"}]}
    assert client.put("/api/master-contracts", json=body, headers=vh).status_code == 403
    assert client.delete(f"/api/master-contracts/{m['id']}", headers=vh).status_code == 403
    assert client.put(f"/api/master-contracts/{m['id']}/annexes", headers=vh,
                      json={"contract_ids": [1]}).status_code == 403

    # Không có quyền `sales_contract` thì đọc cũng không được.
    assert client.get("/api/master-contracts", headers=nh).status_code == 403

    for u in ("mc_view", "mc_none"):
        client.delete(f"/api/users/{u}", headers=h)


def test_master_contract_scan_file_can_be_downloaded(env) -> None:
    """File scan của hồ sơ mẹ dùng chung endpoint với hợp đồng — thiếu hợp nhất owner là 404."""
    h = env
    pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    up = client.post("/api/sales-contracts/file", headers=h,
                     files={"file": ("hop-dong-me.pdf", pdf, "application/pdf")})
    assert up.status_code == 200, up.text
    doc = up.json()
    _master(h, _customer(h), code="HDDH-CO-FILE", master_type="long_term",
            files=[{"file": doc["file"], "filename": doc["filename"]}])

    got = client.get(f"/api/sales-contracts/file/{doc['file']}", headers=h)
    assert got.status_code == 200 and got.content == pdf


def test_member_account_manages_only_its_own_master_contracts(env) -> None:
    """Tài khoản ĐƠN VỊ THÀNH VIÊN tự lập hồ sơ mẹ của mình, nhưng không thấy/đụng được đơn vị khác."""
    h = env
    mine = _master(h, _customer(h), code="HDDH-CUA-TOI", master_type="long_term")
    other = _master(h, _customer(h, UNIT2, "KH đv2"), company=UNIT2, code="HDNT-CUA-DV-KHAC")

    client.delete("/api/users/_zz_mc_mem", headers=h)
    client.post("/api/users", json={"username": "_zz_mc_mem", "password": "pass123",
                                    "role": "member", "member_units": [UNIT]}, headers=h)
    tok = client.post("/api/auth/login",
                      json={"username": "_zz_mc_mem", "password": "pass123"}).json()["access_token"]
    mh = {"Authorization": f"Bearer {tok}"}
    try:
        seen = client.get("/api/master-contracts", headers=mh).json()
        codes = {m["code"] for m in seen["items"]}
        assert "HDDH-CUA-TOI" in codes and "HDNT-CUA-DV-KHAC" not in codes

        # Hồ sơ của đơn vị khác: không xem được, không sửa được.
        assert client.get(f"/api/master-contracts/{other['id']}", headers=mh).status_code == 404
        assert client.put("/api/master-contracts", headers=mh, json={
            **other, "note": "cố sửa"}).status_code == 403

        # Hồ sơ của chính mình thì tự lập được (đơn vị ký hợp đồng thì đơn vị khai hồ sơ).
        made = client.put("/api/master-contracts", headers=mh, json={
            "company": UNIT, "code": "HDNT-MEM-TU-LAP", "master_type": "principle",
            "customer_id": mine["customer_id"], "lines": [{"grade": "SVR 10 / CSR 10"}]})
        assert made.status_code == 200, made.text
    finally:
        client.delete("/api/users/_zz_mc_mem", headers=h)
