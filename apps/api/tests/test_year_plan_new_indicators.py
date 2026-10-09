"""Kế hoạch năm — 11 chỉ tiêu tách theo nguồn (chốt 09/10/2026, plans/261009-ke-hoach-nam-chi-tieu-moi).

Khoá lại: ghi/xoá từng ô mới ở cả 2 cửa (Ban · đơn vị), số bẩn → 422, ô vắng mặt giữ nguyên; KH doanh
thu tổng do server cộng từ 3 mục con (con thắng; client cũ chỉ gửi tổng vẫn như cũ); loại nhập liệu;
«Đề nghị sửa» kế hoạch năm với ô mới. DB dev dùng chung: dữ liệu mang tiền tố `_zz_ypn_` / `_zz_er_`.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import member_unit_repo, unit_daily_repo, user_repo
from app.services.unit_daily_repo import PLAN_FIELDS, PLAN_SPLIT_FIELDS
from app.services.year_plan_totals import REVENUE_CHILDREN, revenue_total
from tests import edit_request_env
from tests.edit_request_env import OLD, approve, client, lock_round, login, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture «Đề nghị sửa» dùng chung

UNIT, YEAR = "_zz_ypn_unit", date.today().year
ER_UNIT, ER_YEAR = edit_request_env.UNIT, int(OLD[:4])
USERS = {"all": None, "pur": ["purchase"]}   # tài khoản đủ 3 loại · chỉ Thu mua
EXPLOIT, PURCHASE, GOODS = REVENUE_CHILDREN
TOTAL = "plan_revenue_ty"


def _drop(h: dict[str, str]) -> None:
    for name in USERS:
        client.delete(f"/api/users/_zz_ypn_{name}", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = ANY(:u)"), {"u": [UNIT, ER_UNIT]})
    member_unit_repo.delete_unit(UNIT)


@pytest.fixture()
def ctx():
    user_repo.seed_admin()
    h = login("admin", "admin")
    _drop(h)
    member_unit_repo.add_unit(UNIT)
    for name, types in USERS.items():
        body = {"username": f"_zz_ypn_{name}", "password": "pass123", "role": "member", "member_units": [UNIT]}
        r = client.post("/api/users", headers=h, json={**body, **({"entry_types": types} if types else {})})
        assert r.status_code == 200, r.text
    try:
        yield {"admin": h, **{n: login(f"_zz_ypn_{n}") for n in USERS}}
    finally:
        _drop(h)


@pytest.fixture(autouse=True)
def _clean_er_plans():
    yield
    with session_scope() as db:   # fixture `env` không dọn bảng kế hoạch
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :u"), {"u": ER_UNIT})


def _door(ctx: dict, door: str) -> tuple[str, dict]:
    return ("/api/unit-daily/plan", ctx["admin"]) if door == "admin" else ("/api/member/plan", ctx["all"])


def _put(ctx: dict, door: str, **values):
    path, hdr = _door(ctx, door)
    return client.put(path, headers=hdr, json={"year": YEAR, "company": UNIT, **values})


def _row(ctx: dict) -> dict:
    return client.get(f"/api/unit-daily/plan?year={YEAR}", headers=ctx["admin"]).json()["plans"][UNIT]


def test_revenue_total_pure() -> None:
    assert revenue_total({}) is None
    assert revenue_total({EXPLOIT: None, PURCHASE: None, GOODS: None, TOTAL: 9}) is None
    assert revenue_total({EXPLOIT: 0.1, PURCHASE: 0.2}) == 0.3      # làm tròn 6 số lẻ
    assert revenue_total({EXPLOIT: 0, GOODS: None}) == 0             # 0 là số thật, không phải trống


@pytest.mark.parametrize("door", ["admin", "member"])
def test_each_new_key_saves_clears_and_keeps_absent_keys(ctx, door) -> None:
    assert _put(ctx, door, plan_tonnes=800, plan_exploit_tonnes=2500).status_code == 200
    for i, key in enumerate(PLAN_SPLIT_FIELDS, start=1):
        assert _put(ctx, door, **{key: i * 1.5}).status_code == 200, key
        got = _row(ctx)
        assert got[key] == i * 1.5 and got["plan_tonnes"] == 800 and got["plan_exploit_tonnes"] == 2500, key
    got = _row(ctx)
    assert set(got) == set(PLAN_FIELDS) and len(got) == 19
    assert all(got[k] == i * 1.5 for i, k in enumerate(PLAN_SPLIT_FIELDS, start=1))   # ô vắng mặt giữ nguyên
    for key in PLAN_SPLIT_FIELDS:
        assert _put(ctx, door, **{key: None}).status_code == 200, key
        assert _row(ctx)[key] is None, key
    got = _row(ctx)
    assert got["plan_tonnes"] == 800 and got[TOTAL] is None


@pytest.mark.parametrize("door", ["admin", "member"])
def test_new_keys_reject_non_finite_and_negative(ctx, door) -> None:
    path, hdr = _door(ctx, door)
    assert _put(ctx, door, plan_consume_goods_tonnes=3, **{GOODS: 4}).status_code == 200
    for key in ("plan_consume_goods_tonnes", GOODS, "plan_stock_exploit_tonnes"):
        for bad in ('"NaN"', '"-inf"', '"Infinity"', "-1"):
            r = client.put(path, headers={**hdr, "Content-Type": "application/json"},
                           content=f'{{"year": {YEAR}, "company": "{UNIT}", "{key}": {bad}}}')
            assert r.status_code == 422, (key, bad)
    got = _row(ctx)
    assert (got["plan_consume_goods_tonnes"], got[GOODS], got[TOTAL]) == (3, 4, 4)
    assert got["plan_stock_exploit_tonnes"] is None


def test_revenue_total_is_summed_from_children(ctx) -> None:
    def check(expected: float | None, **v) -> None:
        assert _put(ctx, "admin", **v).status_code == 200, v
        assert _row(ctx)[TOTAL] == expected, v

    check(42, plan_revenue_ty=42)                         # (c) client cũ chỉ gửi tổng → ghi như cũ
    check(42, plan_tonnes=5, plan_stock_goods_tonnes=1)   # (e) sửa ô khác → không đụng tổng
    check(0.1, **{EXPLOIT: 0.1})                          # (a) 1 mục con → tổng = mục con
    check(0.3, **{PURCHASE: 0.2})                         # (f) mục con đã lưu + mục mới → cộng cả hai
    check(6, **{EXPLOIT: 1, PURCHASE: 2, GOODS: 3})       # (a) đủ 3 mục một lúc
    check(7, plan_revenue_ty=999, **{GOODS: 4})           # (d) gửi cả tổng lẫn mục con → con thắng
    check(7, plan_consume_exploit_tonnes=8)               # (e)
    check(4, **{EXPLOIT: None, PURCHASE: None})           # (b) xoá dần: còn mục nào thì tổng = mục đó
    check(None, **{GOODS: None})                          # (b) xoá nốt mục con cuối → tổng trống, không phải 0
    # Không còn mục con nào và body không xoá mục con nào (con null vốn đã null) → tổng theo body.
    check(5, plan_revenue_ty=5, **{EXPLOIT: None})


def test_purchase_only_account_drops_new_keys(ctx) -> None:
    def put(**v):
        return client.put("/api/member/plan", headers=ctx["pur"], json={"year": YEAR, "company": UNIT, **v})

    assert _put(ctx, "admin", plan_process_purchase_tonnes=70).status_code == 200
    assert put(plan_tonnes=9, plan_process_purchase_tonnes=1, **{GOODS: 2}).status_code == 200
    got = _row(ctx)
    assert got["plan_tonnes"] == 9 and got["plan_process_purchase_tonnes"] == 70
    assert got[GOODS] is None and got[TOTAL] is None
    r = put(plan_process_purchase_tonnes=1, plan_stock_goods_tonnes=2)
    assert r.status_code == 403 and "Hợp đồng" in r.json()["detail"]
    assert _row(ctx)["plan_process_purchase_tonnes"] == 70


def _er_put(hdr: dict, **values):
    return client.put("/api/unit-daily/plan", headers=hdr, json={"year": ER_YEAR, "company": ER_UNIT, **values})


def _er_plan() -> dict:
    return unit_daily_repo.year_plan(ER_YEAR, [ER_UNIT])[ER_UNIT]


def test_edit_request_writes_new_keys_and_recomputes_revenue(env) -> None:
    e = env
    assert _er_put(e["admin"], plan_tonnes=100, **{EXPLOIT: 3}).status_code == 200
    lock_round(e["admin"], OLD)
    body = {"year": ER_YEAR, "company": ER_UNIT, GOODS: 2, "plan_stock_goods_tonnes": 5}
    assert client.put("/api/member/plan", headers=e["member"], json=body).status_code == 403   # đã chốt
    res = send(e["member"], "year_plan", body)
    assert res.status_code == 200, res.text
    req = res.json()["request"]
    assert set(req["payload"]) == set(body) and req["before"][EXPLOIT] == 3
    assert req["before"]["plan_stock_goods_tonnes"] is None
    ok = approve(e["editor"], req["id"])
    assert ok.status_code == 200, ok.text
    got = _er_plan()
    assert (got[GOODS], got["plan_stock_goods_tonnes"], got[TOTAL], got["plan_tonnes"]) == (2, 5, 5, 100)

