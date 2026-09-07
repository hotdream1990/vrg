"""Test "đơn vị khai RÕ là ngày đó không có đơn giá" (gõ 0) ≠ "đơn vị quên khai đơn giá".

Đơn giá 0 không được lưu thành một mức giá (xem `core/market_meta`), nên trước đây sau khi lưu
không còn dấu vết nào của lời khai — các bảng soát cứ nhắc "chưa nhập đơn giá" cho những ngày
sản lượng chênh lệch sau chế biến (đơn vị Bà Rịa - Kampong Thom phản ánh 07/09/2026).
Nay lời khai được giữ bằng cờ `no_price_*` trong phiếu, và bản ghi CŨ của đơn vị nước ngoài
(đơn giá nội tệ = 0) cũng được đọc như một lời khai.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import unit_daily_fields, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_nop_unit"
DAY = (date.today() - timedelta(days=1)).isoformat()
API = "/api/unit-daily/analytics"


@pytest.fixture()
def unit():
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.post("/api/member-units", json={"name": UNIT}, headers=h)
    client.put("/api/unit-daily/plan",
               json={"year": date.today().year, "company": UNIT, "plan_tonnes": 100}, headers=h)
    yield h
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c"), {"c": UNIT})
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :c"), {"c": UNIT})
        db.execute(text("DELETE FROM fact_price WHERE grade = :c"), {"c": UNIT})
    client.delete(f"/api/member-units/{UNIT}", headers=h)


def _put(h: dict, fields: dict) -> None:
    res = client.put("/api/unit-daily/report", headers=h,
                     json={"kind": "purchase", "company": UNIT, "as_of": DAY, "fields": fields})
    assert res.status_code == 200, res.text


def _warnings(h: dict) -> list[str]:
    res = client.get(f"{API}/purchase", headers=h,
                     params={"date_from": DAY, "date_to": DAY, "companies": UNIT})
    assert res.status_code == 200, res.text
    return res.json()["warnings"]


# ── Hai hàm đọc lời khai (dùng chung cho mọi bảng soát) ───────────────────────────────────────
def test_flag_is_read_as_a_declaration() -> None:
    f = {"latex_wet": 4.88, "no_price_latex": True}
    assert unit_daily_fields.declared_no_price(f) == {"latex"}
    assert unit_daily_fields.missing_price_materials(f) == set()


def test_old_foreign_entry_counts_as_declaration() -> None:
    """Bản ghi CŨ chưa có cờ: đơn vị nước ngoài gõ 0 vào ô nội tệ — đó chính là lời khai."""
    f = {"coagulum": 28.88, "price_cup_local": 0.0, "fx_purchase": 6.7}
    assert unit_daily_fields.declared_no_price(f) == {"cup"}
    assert unit_daily_fields.missing_price_materials(f) == set()


def test_no_declaration_at_all_is_still_missing() -> None:
    """Có sản lượng mà không nói gì về giá → vẫn phải nhắc (không được nới tay quá)."""
    f = {"latex_wet": 4.88}
    assert unit_daily_fields.declared_no_price(f) == set()
    assert unit_daily_fields.missing_price_materials(f) == {"latex"}


def test_flag_survives_payload_cleaning(unit) -> None:
    """Cờ phải qua được allowlist của payload, nếu không lưu xong là mất."""
    _put(unit, {"latex_wet": 4.88, "no_price_latex": True})
    res = client.get("/api/unit-daily/day", headers=unit,
                     params={"kind": "purchase", "as_of": DAY, "companies": UNIT})
    fields = res.json()["entries"][UNIT]["fields"]
    assert fields["no_price_latex"] is True
    assert fields["latex_wet"] == 4.88


# ── Cảnh báo của báo cáo Thu mua ─────────────────────────────────────────────────────────────
def test_report_warns_when_price_never_declared(unit) -> None:
    _put(unit, {"latex_wet": 4.88})
    assert any("chưa có đơn giá" in w for w in _warnings(unit))


def test_report_stops_warning_after_declaration(unit) -> None:
    """Đơn vị khai 0 → thôi nhắc "chưa có đơn giá", chuyển sang câu ghi nhận đúng bản chất."""
    _put(unit, {"latex_wet": 4.88, "no_price_latex": True})
    ws = _warnings(unit)
    assert not any("chưa có đơn giá" in w for w in ws)
    assert any("khai không có đơn giá" in w for w in ws)


def test_declaration_of_one_material_does_not_cover_the_other(unit) -> None:
    """Khai mủ nước không có giá thì mủ chén vẫn phải nhắc — mỗi loại một lời khai riêng."""
    _put(unit, {"latex_wet": 4.88, "coagulum": 2.0, "no_price_latex": True})
    assert any("chưa có đơn giá" in w for w in _warnings(unit))
