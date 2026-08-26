"""HÀNG CÓ CHỨNG CHỈ + PREMIUM trên hợp đồng gốc và hợp đồng bán (chốt 26/08/2026).

Bốn điều dễ vỡ, khoá lại bằng test:
  - Chọn nhiều chứng chỉ, lưu rồi đọc lên phải nguyên vẹn (cả 2 loại hợp đồng).
  - Không có premium → để TRỐNG cả số tiền lẫn loại tiền (không đọng loại tiền mồ côi).
  - Chứng chỉ ngoài danh mục / loại tiền ngoài USD-VND phải BÁO LỖI, không lặng lẽ bỏ.
  - ĐỢT GIAO không mang chứng chỉ riêng — thừa kế của hợp đồng cha.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import member_unit_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_ZZ Cert Test"
TODAY = date.today().isoformat()
LINE = [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login",
                      json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _cleanup() -> None:
    with session_scope() as db:
        for tbl in ("sales_contract", "master_contract", "unit_customer"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = :c"), {"c": UNIT})
    member_unit_repo.delete_unit(UNIT)


@pytest.fixture()
def env():
    h = _admin()
    _cleanup()
    member_unit_repo.add_unit(UNIT)
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH chứng chỉ"},
                     headers=h).json()["id"]
    yield h, cus
    _cleanup()


def _master(h, cus, **kw):
    body = {"company": UNIT, "code": "HDDH-CERT", "master_type": "long_term", "customer_id": cus,
            "sign_date": TODAY, "lines": [{"grade": "SVR 10 / CSR 10"}], **kw}
    return client.put("/api/master-contracts", json=body, headers=h)


def _contract(h, cus, **kw):
    body = {"company": UNIT, "code": "HD-CERT", "customer_id": cus, "contract_type": "spot",
            "delivery_type": "single", "sign_date": TODAY, "lines": LINE, **kw}
    return client.put("/api/sales-contracts", json=body, headers=h)


def test_meta_offers_the_catalog(env) -> None:
    h, _ = env
    meta = client.get("/api/sales-contracts/meta", headers=h).json()
    assert meta["certs"] == ["PEFC", "EUDR", "VRG GREEN"]
    assert meta["premium_currencies"] == ["USD", "VND"]


def test_master_contract_keeps_certs_and_premium(env) -> None:
    h, cus = env
    r = _master(h, cus, certs=["EUDR", "PEFC"], premium=120, premium_ccy="usd")
    assert r.status_code == 200, r.text
    m = r.json()["master"]
    # Thứ tự theo DANH MỤC (không theo thứ tự người dùng bấm) + loại tiền chuẩn hoá hoa.
    assert m["certs"] == ["PEFC", "EUDR"] and m["premium"] == 120.0 and m["premium_ccy"] == "USD"

    got = client.get(f"/api/master-contracts/{m['id']}", headers=h).json()["master"]
    assert got["certs"] == ["PEFC", "EUDR"] and got["premium_ccy"] == "USD"


def test_sales_contract_keeps_certs_and_premium_in_vnd(env) -> None:
    h, cus = env
    r = _contract(h, cus, certs=["VRG GREEN"], premium=1500000, premium_ccy="VND")
    assert r.status_code == 200, r.text
    c = r.json()["contract"]
    assert c["certs"] == ["VRG GREEN"] and c["premium"] == 1500000.0 and c["premium_ccy"] == "VND"

    row = client.get(f"/api/sales-contracts/{c['id']}", headers=h).json()["contract"]
    assert row["certs"] == ["VRG GREEN"] and row["premium"] == 1500000.0


def test_no_premium_leaves_both_fields_empty(env) -> None:
    """Không chọn premium thì để trống — và KHÔNG đọng lại loại tiền mồ côi."""
    h, cus = env
    c = _contract(h, cus, certs=["PEFC"], premium=None, premium_ccy="USD").json()["contract"]
    assert c["certs"] == ["PEFC"] and c["premium"] is None and c["premium_ccy"] is None

    # Premium = 0 cũng là "không có" (cùng quy ước giá 0 = không có giá).
    z = _contract(h, cus, id=c["id"], certs=["PEFC"], premium=0, premium_ccy="USD").json()["contract"]
    assert z["premium"] is None and z["premium_ccy"] is None

    # Không khai gì cả → danh sách rỗng, không phải null.
    plain = _contract(h, cus, code="HD-CERT-2").json()["contract"]
    assert plain["certs"] == [] and plain["premium"] is None


def test_bad_cert_or_currency_is_rejected(env) -> None:
    h, cus = env
    bad = _contract(h, cus, certs=["FSC"])
    assert bad.status_code == 400 and "không có trong danh mục" in bad.json()["detail"]

    ccy = _contract(h, cus, premium=50, premium_ccy="LAK")
    assert ccy.status_code == 400 and "USD hoặc VND" in ccy.json()["detail"]

    neg = _contract(h, cus, premium=-5, premium_ccy="USD")
    assert neg.status_code == 400 and "không được âm" in neg.json()["detail"]

    m = _master(h, cus, certs=["EUDR", "SAI"])
    assert m.status_code == 400 and "không có trong danh mục" in m.json()["detail"]


def test_delivery_batch_does_not_carry_its_own_certs(env) -> None:
    """Đợt giao thừa kế của hợp đồng — khai riêng ở đợt là cùng lô hàng có 2 câu trả lời."""
    h, cus = env
    parent = _contract(h, cus, code="HD-CERT-MULTI", delivery_type="multi",
                       certs=["EUDR"], premium=95, premium_ccy="USD").json()["contract"]
    batch = client.put("/api/sales-contracts", headers=h, json={
        "company": UNIT, "parent_id": parent["id"], "code": "DG-01", "customer_id": cus,
        "delivery_type": "single", "delivered_at": TODAY, "channel": "export",
        "certs": ["PEFC"], "premium": 999, "premium_ccy": "USD", "lines": LINE})
    assert batch.status_code == 200, batch.text
    assert batch.json()["contract"]["certs"] == []
    assert batch.json()["contract"]["premium"] is None
    # Hợp đồng cha giữ nguyên phần đã khai.
    still = client.get(f"/api/sales-contracts/{parent['id']}", headers=h).json()["contract"]
    assert still["certs"] == ["EUDR"] and still["premium"] == 95.0
