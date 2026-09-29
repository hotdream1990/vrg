"""Ngày "không thu mua" không được đếm trùng ở đơn vị nhận sáp nhập (rà chéo 29/09/2026).

Lộc Ninh (nhận Bình Long) từng ra "201 ngày có số liệu · 154 ngày khai không thu mua" trong kỳ 272
ngày: cả hai đơn vị cùng khai "không mua" một ngày thì bị đếm 2 lần, và ngày bên này khai "không mua"
còn bên kia có mua vẫn bị đếm là ngày không mua.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core import edit_window
from app.core.db import db_healthy, session_scope
from app.services import member_unit_merge, member_unit_repo
from app.services import unit_daily_repo as udr
from app.services import unit_report_purchase as pur

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

OLD, NEW = "_zz_np_old", "_zz_np_new"
UNITS = [OLD, NEW]
TODAY = edit_window.today()
D1, D2, D_MERGE, D3 = ((TODAY - timedelta(days=n)).isoformat() for n in (20, 19, 10, 3))


def _cleanup() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = ANY(:u)"), {"u": UNITS})
        db.execute(text("UPDATE member_unit SET merged_into = NULL, merged_at = NULL "
                        "WHERE merged_into = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM member_unit WHERE name = ANY(:u)"), {"u": UNITS})


@pytest.fixture(autouse=True)
def _units():
    """D1: cả hai khai "không mua" · D2: OLD khai "không mua", NEW mua 10 t · D3: NEW khai "không mua"."""
    _cleanup()
    for n in UNITS:
        member_unit_repo.add_unit(n)
    no = {"no_purchase": True}
    udr.upsert("purchase", D1, OLD, no, "test")
    udr.upsert("purchase", D1, NEW, no, "test")
    udr.upsert("purchase", D2, OLD, no, "test")
    udr.upsert("purchase", D2, NEW, {"latex_wet": 10}, "test")
    member_unit_merge.merge(OLD, NEW, D_MERGE)
    udr.upsert("purchase", D3, NEW, no, "test")
    yield
    _cleanup()


def test_don_vi_nhan_sap_nhap_dem_ngay_khong_mua_khong_trung():
    rep = pur.purchase_report(D1, D3, companies=NEW)
    row = next(r for r in rep["rows"] if r["key"] == NEW)
    # D2 đã có số thu mua → không phải ngày "không mua"; D1 hai bên cùng khai → MỘT ngày.
    assert (row["days"], row["no_purchase_days"]) == (1, 2)       # trước đây: 1 + 4
    assert rep["totals"]["no_purchase_days"] == 2


def test_xem_tach_don_vi_cu_van_dem_rieng():
    rows = {r["key"]: r for r in pur.purchase_report(D1, D3, companies=f"{OLD},{NEW}",
                                                      split_merged=True)["rows"]}
    assert rows[OLD]["no_purchase_days"] == 2
    assert (rows[NEW]["days"], rows[NEW]["no_purchase_days"]) == (1, 2)


def test_theo_ngay_moi_ngay_mot_luot_don_vi():
    rows = {r["key"]: r for r in pur.purchase_report(D1, D3, companies=NEW, group_by="day")["rows"]}
    assert rows[D1]["no_purchase_days"] == 1
    assert rows[D2]["no_purchase_days"] is None and rows[D2]["days"] == 1


def test_ngay_khai_khong_mua_kem_o_0_tan_van_tinh_la_khong_mua():
    # Hà Tĩnh 29/09/2026: khai "không mua" nhưng ô sản lượng để 0 → dòng 0 tấn vẫn sinh ra; trừ ngày
    # đó như ngày CÓ mua là bỏ oan 41 ngày. Chỉ ngày có sản lượng > 0 mới là ngày có mua.
    udr.upsert("purchase", D3, OLD, {"no_purchase": True, "latex_wet": 0}, "test")
    rep = pur.purchase_report(D3, D3, companies=OLD, split_merged=True)
    row = next(r for r in rep["rows"] if r["key"] == OLD)
    assert row["no_purchase_days"] == 1
