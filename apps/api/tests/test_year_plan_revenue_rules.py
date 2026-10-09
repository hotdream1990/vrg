"""Luật KH doanh thu tổng tự cộng + «Đề nghị sửa» kế hoạch năm sau khi thêm 11 ô (review 09/10/2026).

Khoá lại 3 lỗi reviewer tái hiện: (1) client CŨ gửi cả hàng (3 mục con null) xoá tổng của đơn vị chỉ có
tổng; (2) body chỉ có tổng làm tổng lệch khỏi mục con đã lưu; (3) bỏ qua ô mới khi so ảnh chụp làm đề
nghị MỚI mất cảnh báo 409. DB dev dùng chung: dữ liệu mang tiền tố `_zz_yrr_` / `_zz_er_`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import member_unit_repo, unit_daily_repo, user_repo
from app.services.unit_daily_repo import PLAN_SPLIT_FIELDS
from app.services.year_plan_totals import REVENUE_CHILDREN, revenue_total_to_save
from tests import edit_request_env
from tests.edit_request_env import OLD, approve, client, lock_round, login, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture «Đề nghị sửa» dùng chung

UNIT, ER_UNIT, YEAR = "_zz_yrr_unit", edit_request_env.UNIT, int(OLD[:4])
EXPLOIT, PURCHASE, GOODS = REVENUE_CHILDREN
TOTAL, STOCK_GOODS = "plan_revenue_ty", "plan_stock_goods_tonnes"


def _wipe_plans() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = ANY(:u)"), {"u": [UNIT, ER_UNIT]})


@pytest.fixture()
def admin():
    user_repo.seed_admin()
    _wipe_plans()
    member_unit_repo.add_unit(UNIT)
    try:
        yield login("admin", "admin")
    finally:
        _wipe_plans()
        member_unit_repo.delete_unit(UNIT)


@pytest.fixture(autouse=True)
def _clean_er_plans():
    yield
    _wipe_plans()   # fixture `env` không dọn bảng kế hoạch


def _put(hdr: dict, company: str = UNIT, **values):
    r = client.put("/api/unit-daily/plan", headers=hdr, json={"year": YEAR, "company": company, **values})
    assert r.status_code == 200, r.text


def _plan(company: str = UNIT) -> dict:
    return unit_daily_repo.year_plan(YEAR, [company])[company]


def test_revenue_total_to_save_pure() -> None:
    assert revenue_total_to_save({}, {TOTAL: 9}) == (False, None)                    # chỉ có tổng
    assert revenue_total_to_save({EXPLOIT: 3}, {TOTAL: 9}) == (True, 3)              # con thắng
    assert revenue_total_to_save({EXPLOIT: 3}, {GOODS: 1.5}) == (True, 4.5)
    assert revenue_total_to_save({EXPLOIT: 3}, {EXPLOIT: None}) == (True, None)      # xoá con cuối
    assert revenue_total_to_save({}, dict.fromkeys(REVENUE_CHILDREN)) == (False, None)   # null → null
    assert revenue_total_to_save({EXPLOIT: 3.0}, {EXPLOIT: 3, PURCHASE: None}) == (True, 3)


def test_old_client_full_row_keeps_legacy_total(admin) -> None:
    _put(admin, plan_revenue_ty=500, plan_tonnes=100)
    row = {**_plan(), "plan_tonnes": 120}             # bản web CŨ: PUT nguyên hàng 19 khoá vừa đọc
    assert len(row) == 19 and all(row[k] is None for k in REVENUE_CHILDREN)
    _put(admin, **row)
    assert (_plan()[TOTAL], _plan()["plan_tonnes"]) == (500, 120)
    _put(admin, plan_tonnes=130)                       # body không có khoá doanh thu nào → giữ nguyên
    assert _plan()[TOTAL] == 500


def test_total_follows_children_and_clears_with_last_child(admin) -> None:
    _put(admin, **{EXPLOIT: 300, PURCHASE: 100})
    assert _plan()[TOTAL] == 400
    for body in ({TOTAL: None}, {TOTAL: 999}, {**dict.fromkeys(PLAN_SPLIT_FIELDS[:5]), TOTAL: 1}):
        _put(admin, **body)                            # body chỉ có tổng / tổng kèm ô khác → con thắng
        assert _plan()[TOTAL] == 400, body
    _put(admin, **{EXPLOIT: None})
    assert _plan()[TOTAL] == 100
    _put(admin, **{PURCHASE: None, GOODS: None})       # xoá nốt mục con cuối → tổng trống
    assert _plan()[TOTAL] is None
    _put(admin, plan_revenue_ty=50)                    # hết mục con → lại nhập tổng như đơn vị cũ
    assert _plan()[TOTAL] == 50


def _detail(e: dict, rid: int) -> dict:
    return client.get(f"/api/edit-requests/{rid}", headers=e["editor"]).json()


def _request(e: dict, **values) -> int:
    res = send(e["member"], "year_plan", {"year": YEAR, "company": ER_UNIT, **values})
    assert res.status_code == 200, res.text
    return res.json()["request"]["id"]


def test_new_request_guards_all_fields_against_later_edits(env) -> None:
    e = env
    _put(e["admin"], ER_UNIT, **{STOCK_GOODS: 5, EXPLOIT: 3, PURCHASE: 1})
    lock_round(e["admin"], OLD)
    rid = _request(e, **{STOCK_GOODS: 6})
    _put(e["admin"], ER_UNIT, **{STOCK_GOODS: 8})      # Ban sửa đúng ô đó lúc đề nghị đang chờ
    assert _detail(e, rid)["changed_since_submit"] is True
    assert approve(e["editor"], rid).status_code == 409
    assert client.post(f"/api/member/edit-requests/{rid}/cancel", headers=e["member"]).status_code == 200

    rid = _request(e, plan_tonnes=120)
    _put(e["admin"], ER_UNIT, **{EXPLOIT: 1, PURCHASE: 3})   # mục con đổi chéo, tổng vẫn 4
    assert _plan(ER_UNIT)[TOTAL] == 4
    assert approve(e["editor"], rid).status_code == 409
    assert approve(e["editor"], rid, accept_changed=True).status_code == 200   # Ban xác nhận ghi đè
    assert _plan(ER_UNIT)["plan_tonnes"] == 120


def test_old_pending_request_without_new_keys_is_not_stale(env) -> None:
    e = env
    _put(e["admin"], ER_UNIT, plan_tonnes=100)
    lock_round(e["admin"], OLD)
    rid = _request(e, plan_tonnes=120)
    with session_scope() as db:   # ảnh chụp của đề nghị gửi TRƯỚC khi có cột mới: chỉ 8 khoá
        db.execute(text("UPDATE edit_request SET before = before - CAST(:k AS text[]) WHERE id = :i"),
                   {"k": list(PLAN_SPLIT_FIELDS), "i": rid})
    detail = _detail(e, rid)
    assert len(detail["request"]["before"]) == 8 and detail["changed_since_submit"] is False
    _put(e["admin"], ER_UNIT, plan_stock_exploit_tonnes=7)   # ô mới có số sau lúc gửi = đổi thật
    assert _detail(e, rid)["changed_since_submit"] is True
    _put(e["admin"], ER_UNIT, plan_stock_exploit_tonnes=None)
    ok = approve(e["editor"], rid)
    assert ok.status_code == 200, ok.text
    assert _plan(ER_UNIT)["plan_tonnes"] == 120
