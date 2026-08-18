"""Bảng nhắc "đơn vị còn thiếu gì" — chỉ tính phần CÒN SỬA ĐƯỢC và ĐÚNG luật của màn theo dõi.

Ba điều dễ vỡ, khoá lại bằng test:
  - Bản ghi RỖNG không tính là đã nộp (giống `Theo dõi nộp báo cáo`), nếu không đơn vị yên tâm nhầm.
  - Đơn vị KHÔNG có kế hoạch thu mua thì không bị đòi biểu Thu mua (họ còn không thấy màn đó).
  - Chỉ nhắc ngày trong cửa sổ nhập liệu; ngày đã khoá chỉ-xem thì nhắc cũng không sửa được.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import member_unit_repo, unit_daily_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_ZZ Checklist Test"
USER = "zz_checklist"


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _member() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": USER, "password": "pass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def today_year() -> int:
    return date.today().year


def _cleanup(h: dict[str, str]) -> None:
    client.delete(f"/api/users/{USER}", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c"), {"c": UNIT})
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :c"), {"c": UNIT})
    member_unit_repo.delete_unit(UNIT)


def test_checklist_lists_only_fixable_days_and_respects_purchase_plan() -> None:
    h = _admin()
    _cleanup(h)
    member_unit_repo.add_unit(UNIT)
    assert client.post("/api/users", json={"username": USER, "password": "pass123",
                                           "role": "member", "member_units": [UNIT]},
                       headers=h).status_code == 200
    mh = _member()

    today = date.today()
    d1 = (today - timedelta(days=1)).isoformat()
    old = (today - timedelta(days=60)).isoformat()

    try:
        # 1) Chưa khai gì: đòi đủ biểu Tồn kho, KHÔNG đòi Thu mua (đơn vị chưa có kế hoạch thu mua).
        r = client.get("/api/member/checklist", headers=mh)
        assert r.status_code == 200
        u = r.json()["units"][0]
        assert u["company"] == UNIT and u["needs_purchase"] is False
        assert u["purchase_missing"] == []
        assert u["stock_missing"] == r.json()["days"]        # đúng bằng cửa sổ, không hơn
        assert u["year_plan_missing"] is True
        assert old not in u["stock_missing"]                  # ngày đã khoá thì không nhắc

        # 2) Có kế hoạch thu mua → mới bị đòi biểu Thu mua.
        unit_daily_repo.set_year_plan(today.year, UNIT, 1000.0, None, None, None, None, "admin")
        u = client.get("/api/member/checklist", headers=mh).json()["units"][0]
        assert u["needs_purchase"] is True and u["year_plan_missing"] is False
        assert len(u["purchase_missing"]) == len(u["stock_missing"])

        # 3) Bản ghi RỖNG không tính là đã nộp — phải còn nguyên trong danh sách thiếu.
        unit_daily_repo.upsert("consumption", d1, UNIT, {}, "admin")
        assert d1 in client.get("/api/member/checklist", headers=mh).json()["units"][0]["stock_missing"]

        # 4) Có số liệu thật → ngày đó biến mất khỏi danh sách thiếu.
        unit_daily_repo.upsert("consumption", d1, UNIT, {"stock_material": 12.5}, "admin")
        u = client.get("/api/member/checklist", headers=mh).json()["units"][0]
        assert d1 not in u["stock_missing"]

        # 5) Tích "không tổ chức thu mua" cũng là ĐÃ NỘP (đơn vị đã báo, không phải bỏ trống).
        unit_daily_repo.upsert("purchase", d1, UNIT, {"no_purchase": True}, "admin")
        u = client.get("/api/member/checklist", headers=mh).json()["units"][0]
        assert d1 not in u["purchase_missing"]
    finally:
        _cleanup(h)


def test_missing_fx_deliveries_are_flagged_for_the_whole_year() -> None:
    """Lần giao ngoại tệ bỏ trống tỷ giá = doanh thu bị hụt → nhắc, và nhắc CẢ NĂM.

    Cửa sổ `alert_days` không áp cho nhóm này: lần giao từ tháng 1 vẫn phải hiện, chỉ đánh dấu
    `editable=False` để giao diện không mời bấm sửa một thứ server sẽ chặn.
    """
    h = _admin()
    _cleanup(h)
    member_unit_repo.add_unit(UNIT)
    assert client.post("/api/users", json={"username": USER, "password": "pass123",
                                           "role": "member", "member_units": [UNIT]},
                       headers=h).status_code == 200
    mh = _member()
    today = date.today()
    long_ago = date(today.year, 1, 15).isoformat()
    usd = {"grade": "SVR 3L", "qty": 20.0, "price": 1800.0, "ccy": "USD", "fx": None}
    try:
        with session_scope() as db:
            db.execute(text(
                "INSERT INTO sales_contract (company, code, delivered, delivered_at, lines) "
                "VALUES (:c, 'ZZ-USD', true, CAST(:d AS date), CAST(:l AS jsonb)), "
                "       (:c, 'ZZ-USD-OK', true, CAST(:d AS date), CAST(:ok AS jsonb)), "
                "       (:c, 'ZZ-VND', true, CAST(:d AS date), CAST(:v AS jsonb))"),
                {"c": UNIT, "d": long_ago,
                 "l": json.dumps([usd]),
                 "ok": json.dumps([{**usd, "fx": 26000.0}]),
                 "v": json.dumps([{"grade": "SVR 3L", "qty": 5.0, "price": 45.0, "ccy": "VND"}])})

        r = client.get("/api/member/checklist", headers=mh).json()
        u = r["units"][0]
        # Chỉ dòng USD bỏ trống tỷ giá bị nhắc — dòng đã có tỷ giá và dòng VNĐ thì không.
        assert [d["code"] for d in u["missing_fx"]] == ["ZZ-USD"]
        row = u["missing_fx"][0]
        assert row["qty"] == 20.0 and row["ccy"] == "USD"
        assert row["delivered_at"] == long_ago and row["editable"] is False
        # Phải cộng vào tổng, nếu không banner báo "Đã nhập đủ" và mục này biến mất khỏi màn hình.
        assert r["total_missing"] >= 1

        # Điền tỷ giá → hết nhắc.
        with session_scope() as db:
            db.execute(text("UPDATE sales_contract SET lines = CAST(:l AS jsonb) "
                            " WHERE company = :c AND code = 'ZZ-USD'"),
                       {"c": UNIT, "l": json.dumps([{**usd, "fx": 26000.0}])})
        assert client.get("/api/member/checklist", headers=mh).json()["units"][0]["missing_fx"] == []
    finally:
        with session_scope() as db:
            db.execute(text("DELETE FROM sales_contract WHERE company = :c"), {"c": UNIT})
        _cleanup(h)


def test_year_plan_counts_toward_total() -> None:
    """`total_missing` = 0 làm banner chuyển sang "Đã nhập đủ" VÀ ẩn phần chi tiết → mọi việc còn
    thiếu đều phải được cộng vào tổng, nếu không nó biến mất khỏi màn hình."""
    h = _admin()
    _cleanup(h)
    member_unit_repo.add_unit(UNIT)
    assert client.post("/api/users", json={"username": USER, "password": "pass123",
                                           "role": "member", "member_units": [UNIT]},
                       headers=h).status_code == 200
    mh = _member()
    try:
        # Khai đủ MỌI ngày trong cửa sổ cho biểu Tồn kho → chỉ còn thiếu kế hoạch năm.
        r = client.get("/api/member/checklist", headers=mh).json()
        for d in r["days"]:
            unit_daily_repo.upsert("consumption", d, UNIT, {"no_stock": True}, "admin")
        r = client.get("/api/member/checklist", headers=mh).json()
        u = r["units"][0]
        assert u["stock_missing"] == [] and u["purchase_missing"] == []
        assert u["year_plan_missing"] is True
        assert r["total_missing"] == 1        # KHÔNG được là 0 — còn nợ kế hoạch năm

        # Khai 0 = "đơn vị không tổ chức thu mua": đã khai nên hết nợ, và cũng không bị đòi biểu
        # Thu mua (khai số > 0 mới bật màn đó — lúc ấy lại thiếu đúng các ngày chưa nhập).
        unit_daily_repo.set_year_plan(today_year(), UNIT, 0.0, None, None, None, None, "admin")
        assert client.get("/api/member/checklist", headers=mh).json()["total_missing"] == 0
    finally:
        _cleanup(h)


def test_alert_days_is_configurable_and_zero_turns_it_off() -> None:
    """Admin chỉnh `MEMBER_ALERT_DAYS`: đổi phạm vi rà, đặt 0 là TẮT hẳn cảnh báo."""
    h = _admin()
    _cleanup(h)
    member_unit_repo.add_unit(UNIT)
    assert client.post("/api/users", json={"username": USER, "password": "pass123",
                                           "role": "member", "member_units": [UNIT]},
                       headers=h).status_code == 200
    mh = _member()
    try:
        # Mặc định 14 ngày (tính cả hôm nay) khi chưa cấu hình.
        client.put("/api/config", json={"MEMBER_ALERT_DAYS": "__CLEAR__"}, headers=h)
        r = client.get("/api/member/checklist", headers=mh).json()
        assert r["enabled"] is True and r["alert_days"] == 14 and len(r["days"]) == 14

        # Rà xa hơn cửa sổ sửa → vẫn liệt kê, nhưng có mốc `editable_from` để UI tách ngày đã khoá.
        client.put("/api/config", json={"MEMBER_ALERT_DAYS": "30"}, headers=h)
        r = client.get("/api/member/checklist", headers=mh).json()
        assert r["alert_days"] == 30 and len(r["days"]) == 30
        assert len(r["units"][0]["stock_missing"]) == 30
        assert r["editable_from"] > r["days"][-1]      # ngày cũ nhất nằm ngoài cửa sổ sửa

        # Số âm = cấu hình sai → quay về mặc định, KHÔNG tắt nhầm cảnh báo.
        client.put("/api/config", json={"MEMBER_ALERT_DAYS": "-5"}, headers=h)
        assert client.get("/api/member/checklist", headers=mh).json()["alert_days"] == 14

        # 0 = tắt: không rà ngày nào, không báo việc nào.
        client.put("/api/config", json={"MEMBER_ALERT_DAYS": "0"}, headers=h)
        r = client.get("/api/member/checklist", headers=mh).json()
        assert r["enabled"] is False and r["total_missing"] == 0 and r["days"] == []
    finally:
        client.put("/api/config", json={"MEMBER_ALERT_DAYS": "__CLEAR__"}, headers=h)
        _cleanup(h)


def test_checklist_needs_member_role() -> None:
    """Chuyên viên/admin không có "đơn vị của mình" → endpoint này không dành cho họ."""
    assert client.get("/api/member/checklist", headers=_admin()).status_code == 403
    assert client.get("/api/member/checklist").status_code == 401
