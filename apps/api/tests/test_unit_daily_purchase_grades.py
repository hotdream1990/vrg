"""Test CHỦNG LOẠI cho mủ nguyên liệu ở biểu Thu mua (chốt 20/09/2026).

Luật phải giữ:
- Có bảng chủng loại ⇒ ô tổng là số SUY RA = tổng các dòng (người dùng không gõ tay ô tổng nữa).
- Không có bảng ⇒ ô tổng hoạt động y như cũ — hơn 7.000 bản ghi cũ phải còn nguyên giá trị.
- Dòng trùng chủng loại được GỘP; dòng thiếu chủng loại hoặc thiếu sản lượng bị bỏ.
- Đơn giá KHÔNG đi theo dòng: vẫn một giá cho cả loại mủ trong ngày.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo
from app.services.unit_daily_fields import (
    MATERIAL_GRADE_TABLES, clean_fields, has_data,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_pg_unit"
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


# ── Phần thuần hàm (không cần DB) ────────────────────────────────────────────
def test_o_tong_la_so_suy_ra_tu_cac_dong():
    out = clean_fields("purchase", {
        "latex_wet": 999,           # số người dùng gõ tay — phải bị ghi đè
        "latex_grades": [{"grade": "SVR 3L", "qty": 10}, {"grade": "SVR 5", "qty": 5}],
    })
    assert out["latex_wet"] == pytest.approx(15.0)


def test_dong_trung_chung_loai_duoc_gop():
    out = clean_fields("purchase", {
        "cup_grades": [{"grade": "SVR 10 / CSR 10", "qty": 3},
                       {"grade": "SVR 10 / CSR 10", "qty": 4}],
    })
    assert out["cup_grades"] == [{"grade": "SVR 10 / CSR 10", "qty": 7.0}]
    assert out["coagulum"] == pytest.approx(7.0)


def test_dong_thieu_chung_loai_hoac_san_luong_bi_bo():
    out = clean_fields("purchase", {
        "lace_grades": [{"grade": "", "qty": 5}, {"grade": "SVR 5", "qty": None},
                        {"grade": "SVR 5", "qty": 2}],
    })
    assert out["lace_grades"] == [{"grade": "SVR 5", "qty": 2.0}]
    assert out["lace"] == pytest.approx(2.0)


def test_khong_co_bang_thi_o_tong_giu_nguyen_cach_cu():
    """Bản ghi cũ (chỉ có ô tổng) phải còn nguyên — đây là điều kiện để không phải migration."""
    assert clean_fields("purchase", {"latex_wet": 12})["latex_wet"] == pytest.approx(12.0)
    # Bảng RỖNG cũng không được xoá số tổng đang có.
    out = clean_fields("purchase", {"latex_wet": 12, "latex_grades": []})
    assert out["latex_wet"] == pytest.approx(12.0) and out["latex_grades"] == []


def test_ngay_chi_co_bang_chung_loai_van_tinh_la_da_nop():
    assert has_data("purchase", {"lace_grades": [{"grade": "SVR 5", "qty": 1}]}) is True
    assert has_data("purchase", {"lace_grades": []}) is False


def test_don_gia_khong_di_theo_dong():
    """Đơn giá nằm ở kho giá riêng — dòng chủng loại chỉ giữ chủng loại + sản lượng."""
    out = clean_fields("purchase", {
        "latex_grades": [{"grade": "SVR 3L", "qty": 10, "price": 500}],
    })
    assert out["latex_grades"] == [{"grade": "SVR 3L", "qty": 10.0}]


def test_ba_loai_mu_deu_co_bang_rieng():
    assert set(MATERIAL_GRADE_TABLES) == {"latex", "cup", "lace"}
    assert [t for t, _ in MATERIAL_GRADE_TABLES.values()] == [
        "latex_grades", "cup_grades", "lace_grades"]


# ── Đi qua API thật (lưu → đọc lại) ──────────────────────────────────────────
@pytest.fixture()
def unit():
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    _wipe(h)
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    client.put("/api/unit-daily/plan",
               json={"year": date.today().year, "company": UNIT, "plan_tonnes": 100}, headers=h)
    yield h
    _wipe(h)


def _wipe(h: dict[str, str]) -> None:
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = :u"), {"u": UNIT})
    client.delete(f"/api/member-units/{UNIT}", headers=h)


def _save(h: dict, as_of: str, fields: dict) -> None:
    res = client.put("/api/unit-daily/report", headers=h,
                     json={"kind": "purchase", "company": UNIT, "as_of": as_of, "fields": fields})
    assert res.status_code == 200, res.text


def _read(h: dict, as_of: str) -> dict:
    res = client.get("/api/unit-daily/day", headers=h,
                     params={"kind": "purchase", "as_of": as_of, "companies": UNIT})
    assert res.status_code == 200, res.text
    return res.json()["entries"].get(UNIT, {}).get("fields", {})


def test_luu_roi_doc_lai_giu_nguyen_chung_loai(unit):
    _save(unit, TODAY, {"latex_grades": [{"grade": "SVR 3L", "qty": 8},
                                         {"grade": "SVR 10 / CSR 10", "qty": 2}]})
    got = _read(unit, TODAY)
    assert {r["grade"]: r["qty"] for r in got["latex_grades"]} == {"SVR 3L": 8.0,
                                                                   "SVR 10 / CSR 10": 2.0}
    assert got["latex_wet"] == pytest.approx(10.0)


def test_ban_ghi_cu_chi_co_o_tong_van_doc_duoc(unit):
    """Mô phỏng dữ liệu cũ: lưu ô tổng, không gửi bảng → đọc lại phải còn nguyên."""
    _save(unit, YESTERDAY, {"latex_wet": 25, "coagulum": 4})
    got = _read(unit, YESTERDAY)
    assert got["latex_wet"] == pytest.approx(25.0)
    assert got["coagulum"] == pytest.approx(4.0)
    assert not got.get("latex_grades")
