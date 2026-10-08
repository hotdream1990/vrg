"""Tiền ngoại tệ 2 số lẻ + DOANH THU VNĐ THEO KẾ TOÁN của dòng hợp đồng (08/10/2026).

Đơn vị đề nghị: số tiền USD thống nhất 2 số lẻ; doanh thu VNĐ của đơn hàng xuất khẩu cho điều chỉnh
để khớp báo cáo kế toán (kế toán ghi phần cọc theo tỷ giá ngày nhận cọc). Ba công thức doanh thu
(Python · SQL dòng tổng · thống kê tiêu thụ) phải cùng ra một số.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.db import db_healthy
from app.services import sales_contract_calc as calc
from app.services import sales_contract_lifecycle, sales_contract_repo, unit_report_rows
from tests import edit_request_env
from tests.edit_request_env import OLD, TODAY, UNIT, client

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture dùng chung (admin · member · cửa sổ sửa 3 ngày)

NOW = TODAY.isoformat()
SIGN = (TODAY - timedelta(days=20)).isoformat()
USD = {"grade": "SVR 10 / CSR 10", "qty": 19.957, "price": 1725.0, "ccy": "USD", "fx": 26215.5,
       "source": "exploit"}
AUTO = 902_490_346.0        # round(round(19,957 × 1.725; 2) × 26.215,5) = round(34.425,83 × 26.215,5)


def test_foreign_amount_rounds_half_up_like_an_invoice() -> None:
    assert 19.957 * 1725 == pytest.approx(34425.825)             # float ra 34.425,824999…
    assert calc.line_amount(USD) == 34425.83
    assert calc.computed_revenue_vnd(USD) == AUTO == calc.line_revenue_vnd(USD)
    assert calc.line_revenue_vnd({**USD, "revenue_vnd": 900_000_000}) == 900_000_000
    vnd = {"grade": "SVR 10 / CSR 10", "qty": 20.16, "price": 51.05, "ccy": "VND"}
    assert calc.line_amount(vnd) == pytest.approx(1029.168)        # VNĐ: triệu đồng, không làm tròn 2 số
    assert calc.line_revenue_vnd({**vnd, "revenue_vnd": 1}) == 1_029_168_000   # dòng VNĐ bỏ qua ô


def _save(e, hdr=None, **kw):
    if "cus" not in e:          # một khách cho cả test — tạo lại cùng tên thì bị báo trùng
        e["cus"] = client.put("/api/customers", json={"company": UNIT, "name": "KH xuất khẩu"},
                              headers=e["admin"]).json()["id"]
    body = {"company": UNIT, "code": "XK-01", "customer_id": e["cus"], "contract_type": "spot",
            "delivery_type": "single", "sign_date": SIGN, "delivered_at": NOW, "channel": "export",
            "lines": [USD], **kw}
    return client.put("/api/sales-contracts", headers=hdr or e["admin"], json=body)


def test_override_replaces_revenue_everywhere(env) -> None:
    e = env
    res = _save(e, lines=[{**USD, "revenue_vnd": 900_000_000.4}])
    assert res.status_code == 200, res.text
    c = res.json()["contract"]
    assert c["lines"][0]["revenue_vnd"] == 900_000_000           # làm tròn về đồng
    assert c["revenue"] == 900_000_000

    listed = client.get(f"/api/sales-contracts?company={UNIT}", headers=e["admin"]).json()
    assert listed["totals"]["revenue"] == pytest.approx(900_000_000)            # SQL dòng tổng
    rows = unit_report_rows.consumption_rows(NOW, NOW, [UNIT])["rows"]          # thống kê tiêu thụ
    assert [r["revenue_vnd"] for r in rows] == [900_000_000]

    cleared = _save(e, id=c["id"], lines=[{**USD, "revenue_vnd": None}]).json()["contract"]
    assert "revenue_vnd" not in cleared["lines"][0] and cleared["revenue"] == AUTO
    listed = client.get(f"/api/sales-contracts?company={UNIT}", headers=e["admin"]).json()
    assert listed["totals"]["revenue"] == pytest.approx(AUTO)


@pytest.mark.parametrize("line,extra,msg", [
    ({**USD, "revenue_vnd": AUTO * 1.11}, {}, "lệch quá 10%"),
    ({**USD, "revenue_vnd": 0}, {}, "phải lớn hơn 0"),
    ({**USD, "ccy": "VND", "price": 51.0, "fx": None, "revenue_vnd": 1e9}, {}, "dòng bán bằng VNĐ"),
    ({**USD, "source": None, "revenue_vnd": AUTO}, {"delivered_at": None, "channel": None},
     "chỉ nhập khi đã có ngày giao"),
    ({**USD, "price": None, "revenue_vnd": 1e30}, {}, "nhập đơn giá và tỷ giá trước"),
    ({**USD, "price": 1725.125}, {}, "chỉ lấy tối đa 2 số lẻ"),
])
def test_override_is_refused_when_it_cannot_be_right(env, line, extra, msg) -> None:
    res = _save(env, lines=[line], **extra)
    assert res.status_code == 400 and msg in res.json()["detail"], res.text


def test_override_is_a_number_but_old_clients_keep_it(env) -> None:
    """Ô này là SỐ LIỆU: quá cửa sổ sửa thì đổi nó phải đi «Đề nghị sửa». Web bản cũ (không biết ô)
    sửa ghi chú của lần giao đó thì vẫn lưu thẳng được và KHÔNG xoá mất số kế toán."""
    e = env
    c = _save(e, delivered_at=OLD, lines=[{**USD, "revenue_vnd": AUTO + 1000}]).json()["contract"]
    body = {k: c[k] for k in ("id", "company", "code", "customer_id", "contract_type", "delivery_type",
                              "sign_date", "delivered_at", "channel")}
    changed = client.put("/api/sales-contracts", headers=e["member"],
                         json={**body, "lines": [{**USD, "revenue_vnd": AUTO + 2000}]})
    assert changed.status_code == 403 and changed.headers.get("X-Edit-Blocked") == "window"

    old_client = client.put("/api/sales-contracts", headers=e["member"],
                            json={**body, "note": "bổ sung chứng từ", "lines": [USD]})
    assert old_client.status_code == 200, old_client.text
    assert sales_contract_repo.get(c["id"])["lines"][0]["revenue_vnd"] == AUTO + 1000

    # Web cũ BỎ ngày giao: không được nhét lại số kế toán rồi báo lỗi về một ô nó không thấy.
    undelivered = client.put("/api/sales-contracts", headers=e["admin"], json={
        **body, "delivered_at": None, "channel": None, "lines": [{**USD, "source": None}]})
    assert undelivered.status_code == 200, undelivered.text
    assert "revenue_vnd" not in sales_contract_repo.get(c["id"])["lines"][0]


def test_override_moves_with_the_delivery_when_switching_to_batches(env) -> None:
    e = env
    c = _save(e, lines=[{**USD, "revenue_vnd": AUTO - 5000}]).json()["contract"]
    sales_contract_lifecycle.set_delivery_type(c["id"], "multi", None, "admin")
    parent = sales_contract_repo.get(c["id"])
    batch = sales_contract_repo.children(c["id"])[0]
    assert "revenue_vnd" not in parent["lines"][0]                 # hợp đồng cha chỉ giữ cam kết
    assert batch["lines"][0]["revenue_vnd"] == AUTO - 5000 and batch["revenue"] == AUTO - 5000
