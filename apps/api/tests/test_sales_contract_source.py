"""NGUỒN TIÊU THỤ của lần giao — khai thác / thu mua (chốt 03/10/2026).

Luật: hợp đồng chưa giao chưa bắt buộc khai; có NGÀY GIAO (chốt thành tiêu thụ) là phải chọn
nguồn — ở chính hợp đồng giao 1 lần, hoặc ở từng đợt giao của hợp đồng giao nhiều lần. Báo cáo
tiêu thụ tách được sản lượng theo nguồn.
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

UNIT = "_zz_src_unit"
TODAY = date.today().isoformat()


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
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH nguồn"},
                     headers=h).json()["id"]
    yield h, cus
    _cleanup(h)


def _line(qty: float) -> dict:
    return {"grade": "SVR 10 / CSR 10", "qty": qty, "price": 40.0, "ccy": "VND"}


def _put(h: dict[str, str], body: dict):
    return client.put("/api/sales-contracts", json={"company": UNIT, **body}, headers=h)


def _single(cus: int, code: str, qty: float, **kw) -> dict:
    return {"code": code, "customer_id": cus, "delivery_type": "single", "contract_type": "spot",
            "sign_date": TODAY, "lines": [_line(qty)], **kw}


def test_delivery_requires_a_valid_source(env) -> None:
    h, cus = env
    # Chưa giao: chưa bắt buộc — hợp đồng khai lúc ký không cần biết hàng lấy từ đâu.
    pending = _put(h, _single(cus, "HD-SRC-0", 10.0))
    assert pending.status_code == 200, pending.text
    assert pending.json()["contract"]["source"] is None

    # Có ngày giao mà thiếu nguồn → chặn, KHÔNG tự gán mặc định.
    miss = _put(h, _single(cus, "HD-SRC-1", 10.0, delivered_at=TODAY, channel="domestic"))
    assert miss.status_code == 400 and "nguồn tiêu thụ" in miss.json()["detail"]

    bad = _put(h, _single(cus, "HD-SRC-2", 10.0, delivered_at=TODAY, channel="domestic",
                          source="khai_thac"))
    assert bad.status_code == 400 and "không hợp lệ" in bad.json()["detail"]

    ok = _put(h, _single(cus, "HD-SRC-3", 10.0, delivered_at=TODAY, channel="domestic",
                         source="purchase"))
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract"]["source"] == "purchase"


def test_batches_carry_the_source_and_consumption_splits_by_it(env) -> None:
    h, cus = env
    parent = _put(h, {"code": "HD-SRC-M", "customer_id": cus, "delivery_type": "multi",
                      "contract_type": "spot", "sign_date": TODAY, "lines": [_line(100.0)],
                      # Hợp đồng giao nhiều lần không mang nguồn — khai ở từng đợt giao.
                      "source": "exploit"})
    assert parent.status_code == 200, parent.text
    pid = parent.json()["contract"]["id"]
    assert parent.json()["contract"]["source"] is None

    no_src = _put(h, {"parent_id": pid, "code": "1", "delivered_at": TODAY, "channel": "export",
                      "lines": [_line(30.0)]})
    assert no_src.status_code == 400 and "nguồn tiêu thụ" in no_src.json()["detail"]
    for code, qty, src in (("1", 30.0, "exploit"), ("2", 20.0, "purchase")):
        r = _put(h, {"parent_id": pid, "code": code, "delivered_at": TODAY, "channel": "export",
                     "source": src, "lines": [_line(qty)]})
        assert r.status_code == 200, r.text

    params = {"date_from": TODAY, "date_to": TODAY, "company": UNIT}
    rep = client.get("/api/sales-contracts/consumption", headers=h, params=params).json()
    by_source = rep["by_company"][UNIT]["by_source"]
    assert by_source == {"exploit": pytest.approx(30.0), "purchase": pytest.approx(20.0)}

    hist = client.get("/api/sales-contracts/consumption/deliveries", headers=h,
                      params=params).json()
    assert sorted(r["source"] for r in hist["rows"]) == ["Khai thác", "Thu mua"]

    # Màn Thống kê tiêu thụ đọc cùng nguồn: lọc theo nguồn chỉ còn phần thu mua.
    stats = client.get("/api/unit-daily/analytics/consumption", headers=h, params={
        "date_from": TODAY, "date_to": TODAY, "companies": UNIT, "source": "purchase",
        "group_by": "company", "split_merged": "true"}).json()
    assert stats["totals"]["qty"] == pytest.approx(20.0)
    assert stats["totals"]["qty_purchase"] == pytest.approx(20.0)


def test_completing_a_single_contract_asks_for_the_source(env) -> None:
    h, cus = env
    cid = _put(h, _single(cus, "HD-SRC-C", 15.0)).json()["contract"]["id"]
    url = f"/api/sales-contracts/{cid}/completion"
    miss = client.put(url, headers=h, json={"completed_at": TODAY, "channel": "domestic"})
    assert miss.status_code == 400 and "Nguồn tiêu thụ" in miss.json()["detail"]

    ok = client.put(url, headers=h, json={"completed_at": TODAY, "channel": "domestic",
                                          "source": "purchase"})
    assert ok.status_code == 200, ok.text
    c = ok.json()["contract"]
    assert (c["delivered_at"], c["source"]) == (TODAY, "purchase")


def test_switching_to_multi_moves_the_source_to_the_first_batch(env) -> None:
    h, cus = env
    cid = _put(h, _single(cus, "HD-SRC-S", 12.0, delivered_at=TODAY, channel="domestic",
                          source="purchase")).json()["contract"]["id"]
    r = client.put(f"/api/sales-contracts/{cid}/delivery-type", headers=h,
                   json={"delivery_type": "multi"})
    assert r.status_code == 200, r.text
    assert r.json()["contract"]["source"] is None
    kids = client.get(f"/api/sales-contracts/{cid}", headers=h).json()["children"]
    assert [k["source"] for k in kids] == ["purchase"]


def test_legacy_edit_request_payload_keeps_the_stored_source(env) -> None:
    """Đề nghị sửa gửi TRƯỚC khi có ô nguồn không mang khoá `source` — Ban duyệt vẫn qua được."""
    from app.services.edit_request_ops_contract import _legacy_source

    h, cus = env
    c = _put(h, _single(cus, "HD-SRC-L", 8.0, delivered_at=TODAY, channel="domestic",
                        source="purchase")).json()["contract"]
    legacy = {k: v for k, v in c.items() if k != "source"}
    assert _legacy_source(legacy)["source"] == "purchase"
    # Bản ghi mới (chưa có id) có ngày giao → tính khai thác như mọi lần giao cũ.
    assert _legacy_source({"delivered_at": TODAY})["source"] == "exploit"
    # Payload mới luôn mang khoá — giữ nguyên, kể cả khi để trống (luật bắt buộc vẫn áp).
    assert _legacy_source({**c, "source": None})["source"] is None
    # Chưa giao thì không đoán gì.
    assert "source" not in _legacy_source({"code": "x"})
