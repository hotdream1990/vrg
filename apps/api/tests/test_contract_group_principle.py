"""Nhóm báo cáo HĐ chuyến · HĐ nguyên tắc · HĐ dài hạn xếp theo HỒ SƠ MẸ (chốt 01/10/2026).

Phản ánh Dầu Tiếng Việt Lào: 10 đơn hàng thuộc 3 HĐNT, 7 cái lưu "HĐ chuyến", 3 cái lưu "Phụ lục"
→ Dashboard hiện "Dài hạn 420 · chuyến 5.794" dù đơn vị không có HĐDH nào. Khoá lại:
  1. Gắn HĐNT → nhóm HĐNT, bất kể loại tự khai; gắn HĐDH → dài hạn; không gắn → loại tự khai.
  2. Đợt giao của phụ lục theo hồ sơ của phụ lục (đợt giao không mang hồ sơ).
  3. % KH tiêu thụ HĐ chuyến chỉ tính HĐ chuyến thật.
  4. Báo cáo kỳ tách 3 nhóm; biểu mẫu Ban TTKD gộp HĐNT vào cột chuyến.
Dữ liệu dựng thẳng bằng SQL (như `test_contract_backlog`) — luật form nhập không liên quan ở đây.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import sales_contract_report as scr
from app.services import unit_period_report as upr
from app.services import unit_report_consumption as urc
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_grp_a"
D1, D2 = "2026-03-10", "2026-03-20"
SVR = "SVR 10 / CSR 10"


def _ln(qty: float) -> list[dict]:
    return [{"grade": SVR, "qty": qty, "price": 40.0, "ccy": "VND"}]


def _master(code: str, mtype: str) -> int:
    with session_scope() as db:
        return db.execute(text(
            "INSERT INTO master_contract (company, code, master_type, sign_date, lines) "
            "VALUES (:c, :code, :t, '2026-01-05', CAST(:l AS jsonb)) RETURNING id"),
            {"c": UNIT, "code": code, "t": mtype, "l": json.dumps(_ln(1000))}).scalar()


def _contract(code: str, qty: float, ctype: str | None, *, master_id: int | None = None,
              parent_id: int | None = None, delivered_at: str | None = D1,
              channel: str = "export") -> int:
    with session_scope() as db:
        return db.execute(text(
            "INSERT INTO sales_contract (company, parent_id, code, delivery_type, contract_type, "
            "  sign_date, lines, delivered, delivered_at, master_id, channel) "
            "VALUES (:c, :p, :code, 'single', :t, '2026-02-01', CAST(:l AS jsonb), :dd, :d, :m, :ch) "
            "RETURNING id"),
            {"c": UNIT, "p": parent_id, "code": code, "t": ctype, "l": json.dumps(_ln(qty)),
             "dd": delivered_at is not None, "d": delivered_at, "m": master_id,
             "ch": channel}).scalar()


def _wipe() -> None:
    with session_scope() as db:
        for tbl in ("sales_contract", "master_contract", "unit_purchase_plan"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = :u"), {"u": UNIT})


def _admin() -> dict[str, str]:
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


@pytest.fixture()
def seeded():
    """Một đơn vị đủ 5 kiểu hợp đồng — số tấn khác nhau để cộng sai là lộ ngay."""
    h = _admin()
    _wipe()
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    nt, dh = _master("NT-1", "principle"), _master("DH-1", "long_term")
    _contract("CH-LE", 1, "spot")                                       # HĐ chuyến thật
    _contract("CH-NT", 10, "spot", master_id=nt)                        # "chuyến" gắn HĐNT
    pl = _contract("PL-NT", 0, "long_term", master_id=nt, delivered_at=None)
    _contract("PL-NT/1", 100, None, parent_id=pl, channel="domestic")   # đợt giao của phụ lục HĐNT
    _contract("PL-DH", 1000, "long_term", master_id=dh, delivered_at=D2)
    _contract("PL-CU", 10000, "long_term")                              # phụ lục cũ chưa gắn hồ sơ
    with session_scope() as db:
        db.execute(text("INSERT INTO unit_purchase_plan (year, company, plan_sales_spot_tonnes) "
                        "VALUES (2026, :u, 4)"), {"u": UNIT})
    yield h
    _wipe()
    client.delete(f"/api/member-units/{UNIT}", headers=h)


def test_nhom_theo_ho_so_me(seeded) -> None:
    got = {d["code"]: (d["contract_type"], d["contract_group"])
           for d in scr.deliveries("2026-01-01", "2026-12-31", [UNIT])}
    assert got == {"CH-LE": ("spot", "spot"), "CH-NT": ("spot", "principle"),
                   "PL-NT/1": ("long_term", "principle"), "PL-DH": ("long_term", "long_term"),
                   "PL-CU": ("long_term", "long_term")}
    by_type = scr.consumption("2026-01-01", "2026-12-31", [UNIT])[UNIT]["by_type"]
    assert by_type == {"spot": 1, "principle": 110, "long_term": 11000}


def test_thong_ke_tach_3_nhom_va_kh_chi_tinh_chuyen_that(seeded) -> None:
    rep = urc.consumption_report("2026-01-01", "2026-12-31", companies=UNIT)
    t = rep["totals"]
    assert (t["qty_spot"], t["qty_principle"], t["qty_long_term"]) == (1, 110, 11000)
    assert t["qty_unknown_type"] is None and t["qty"] == 11111
    # KH chuyến 4 t: tử số CHỈ là 1 t HĐ chuyến thật, không cộng 110 t HĐNT.
    assert t["pct_plan_sales_spot"] == pytest.approx(25)
    by_contract = urc.consumption_report("2026-01-01", "2026-12-31", companies=UNIT,
                                         group_by="contract")
    assert {r["key"]: r["qty"] for r in by_contract["rows"]} == {
        "HĐ chuyến": 1, "HĐ nguyên tắc": 110, "HĐ dài hạn": 11000}
    only = urc.consumption_report("2026-01-01", "2026-12-31", companies=UNIT, contract="principle")
    assert only["totals"]["qty"] == 110


def test_bao_cao_ky_tach_hdnt_va_mau_ban_ttkd_gop_vao_chuyen(seeded) -> None:
    row = next(r for r in upr.period_report("consumption", "2026-01-01", "2026-12-31",
                                            companies=[UNIT])["rows"] if r["company"] == UNIT)
    assert (row["spot_export"], row["spot_total"]) == (1, 1)
    assert (row["principle_export"], row["principle_domestic"], row["principle_total"]) == (
        10, 100, 110)
    assert (row["lt_export"], row["lt_total"]) == (11000, 11000)
    assert row["pct_plan_sales_spot"] == pytest.approx(25)
    ttkd = upr.ban_ttkd_view(row)
    assert (ttkd["spot_export"], ttkd["spot_domestic"], ttkd["spot_total"]) == (11, 100, 111)
    assert ttkd["lt_export"] == 11000 and ttkd["pct_plan_sales_spot"] == pytest.approx(25)
