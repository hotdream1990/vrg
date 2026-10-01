"""Loại nhập liệu của tài khoản đơn vị (chốt 01/10/2026): Thu mua · Tồn kho · Hợp đồng & tiêu thụ.

Server chặn GHI ngoài loại được giao; đọc số liệu chính đơn vị mình không chặn; lãnh đạo đơn vị và
Tập đoàn không bị ảnh hưởng. DB dev dùng chung (bản sao prod): mọi dữ liệu mang tiền tố `_zz_et_`,
dọn trước và sau mỗi test.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core import edit_window
from app.core.db import db_healthy, session_scope
from app.core.entry_types import ENTRY_TYPES
from app.services import (
    config_repo, edit_request_ops, member_checklist, member_unit_repo, unit_daily_repo, user_repo,
)
from app.services.unit_daily_fields import CONSUMPTION_SALES_KEYS
from tests import edit_request_env
from tests.edit_request_env import OLD, approve, client, demand, send

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
env = edit_request_env.env   # fixture «Đề nghị sửa số liệu» dùng chung

UNIT = "_zz_et_unit"
ALL3 = list(ENTRY_TYPES)
ACCOUNTS = {"pur": ("member", ["purchase"]), "stk": ("member", ["stock"]),
            "con": ("member", ["contract"]), "lead": ("leader", None)}
TODAY = edit_window.today()
DEMAND_URL = "/api/member/market-demand/items"
DENIED = "không được giao nhập liệu"


def _bearer(username: str, password: str = "pass123") -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": username, "password": password}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cleanup(h: dict[str, str]) -> None:
    for name in [*ACCOUNTS, "crud"]:
        client.delete(f"/api/users/_zz_et_{name}", headers=h)
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "market_demand_item", "sales_contract",
                    "unit_customer", "unit_stock_contract", "edit_request"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = :u"), {"u": UNIT})
        db.execute(text("DELETE FROM fact_price WHERE grade = :u"), {"u": UNIT})
    member_unit_repo.delete_unit(UNIT)


@pytest.fixture()
def et():
    user_repo.seed_admin()
    h = _bearer("admin", "admin")
    _cleanup(h)
    member_unit_repo.add_unit(UNIT)
    for name, (role, types) in ACCOUNTS.items():
        body = {"username": f"_zz_et_{name}", "password": "pass123", "role": role, "member_units": [UNIT]}
        r = client.post("/api/users", json={**body, **({"entry_types": types} if types else {})}, headers=h)
        assert r.status_code == 200, r.text
    try:
        yield {"admin": h, **{name: _bearer(f"_zz_et_{name}") for name in ACCOUNTS}}
    finally:
        _cleanup(h)


def _daily(hdr: dict, kind: str, fields: dict):
    return client.put("/api/member/daily-report", headers=hdr,
                      json={"kind": kind, "company": UNIT, "as_of": TODAY.isoformat(), "fields": fields})


def _denied(r, label: str) -> bool:
    return r.status_code == 403 and DENIED in r.json()["detail"] and label in r.json()["detail"]


#: Ô TIÊU THỤ CŨ còn nằm trong bản ghi Tồn kho (trước khi chuyển sang hợp đồng 30/07/2026).
LEGACY = {"sales": [{"code": "HD-CU", "grade": "SVR 10", "qty": 5, "price": 40}],
          "revenue": 200_000_000, "purchased_sold_qty": 7, "sales_ccy": "VND"}
FORGED = {"stock_material": 3, "sales": [], "revenue": 1, "purchased_sold_qty": 99,
          "finished_sold_qty": 5, "sales_ccy": "USD", "sales_migrated": True}


def _stored(day: str, company: str = UNIT) -> dict:
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM unit_daily_report WHERE kind = 'consumption' "
                              "AND as_of = CAST(:d AS date) AND company = :c"),
                         {"d": day, "c": company}).scalar()
    return dict(row or {})


def _sales_part(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if k in CONSUMPTION_SALES_KEYS}


def test_user_crud_carries_entry_types(et) -> None:
    h, name = et["admin"], "_zz_et_crud"
    base = {"username": name, "password": "pass123", "role": "member", "member_units": [UNIT]}
    for bad in ([], ["bogus"]):
        r = client.post("/api/users", json={**base, "entry_types": bad}, headers=h)
        assert r.status_code == 400 and r.json()["detail"] == user_repo.ENTRY_TYPES_REQUIRED
    made = client.post("/api/users", json=base, headers=h)
    assert made.status_code == 200 and made.json()["entry_types"] == ALL3      # không gửi = đủ 3 loại
    put = lambda body: client.put(f"/api/users/{name}", json=body, headers=h)   # noqa: E731
    # Lộn thứ tự + trùng → lưu theo thứ tự chuẩn của danh mục.
    assert put({"entry_types": ["contract", "purchase", "contract"]}).json()["entry_types"] == [
        "purchase", "contract"]
    r = put({"entry_types": []})
    assert r.status_code == 400 and r.json()["detail"] == user_repo.ENTRY_TYPES_REQUIRED
    assert put({"full_name": "ZZ"}).json()["entry_types"] == ["purchase", "contract"]   # giữ nguyên

    login = client.post("/api/auth/login", json={"username": name, "password": "pass123"}).json()
    assert login["user"]["entry_types"] == ["purchase", "contract"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert me.json()["entry_types"] == ["purchase", "contract"]
    imp = client.post("/api/auth/impersonate", json={"username": "_zz_et_pur"}, headers=h)
    assert imp.status_code == 200 and imp.json()["user"]["entry_types"] == ["purchase"]
    listed = client.get("/api/users", headers=h).json()
    assert {u["username"]: u["entry_types"] for u in listed}[name] == ["purchase", "contract"]
    assert all(u["entry_types"] == [] for u in listed if u["role"] != "member")

    # Vai trò khác không mang loại; quay lại member mà không gửi loại → đủ 3 loại.
    assert put({"role": "leader"}).json()["entry_types"] == []
    assert put({"role": "member"}).json()["entry_types"] == ALL3
    assert client.get("/api/auth/me", headers=et["lead"]).json()["entry_types"] == []


def test_purchase_only_account_writes_only_purchase(et) -> None:
    pur, day = et["pur"], TODAY.isoformat()
    assert _daily(pur, "purchase", {"latex_wet": 1}).status_code == 200
    assert _denied(_daily(pur, "consumption", {"stock_material": 1}), "Tồn kho")
    move = client.put("/api/member/daily-report/move-date", headers=pur, json={
        "kind": "consumption", "company": UNIT, "as_of": day,
        "to_date": (TODAY - timedelta(days=1)).isoformat()})
    assert _denied(move, "Tồn kho")
    price = {"company": UNIT, "as_of": day, "price_type": "purchase"}
    assert client.put("/api/member/prices", json={**price, "price": 300}, headers=pur).status_code == 200
    assert client.delete("/api/member/prices", params=price, headers=pur).status_code == 200

    writes = [
        ("PUT", DEMAND_URL, {"company": UNIT, "as_of": day, "customer": "KH", "grade": "LATEX"}, "Hợp đồng"),
        ("DELETE", f"{DEMAND_URL}/2000000000", None, "Hợp đồng"),
        ("PUT", "/api/customers", {"company": UNIT, "name": "KH thử"}, "Hợp đồng"),
        ("PUT", "/api/sales-contracts", {"company": UNIT}, "Hợp đồng"),
        ("PUT", "/api/master-contracts", {"company": UNIT}, "Hợp đồng"),
        ("PUT", "/api/member/stock-contracts",
         {"company": UNIT, "grade": "Chủng loại khác", "qty": 1, "start_date": day}, "Tồn kho"),
        ("DELETE", "/api/member/stock-contracts/2000000000", None, "Tồn kho"),
    ]
    for method, url, body, label in writes:
        r = client.request(method, url, json=body, headers=pur)
        assert _denied(r, label), f"{method} {url} → {r.status_code} {r.text[:200]}"
    up = client.post("/api/member/daily-report/contract-file", headers=pur,
                     files={"file": ("hd.pdf", b"%PDF-1.4", "application/pdf")})
    assert _denied(up, "Tồn kho")
    # ĐỌC số liệu chính đơn vị mình thì không chặn theo loại.
    for url in (f"/api/member/daily-report?kind=consumption&as_of={day}", DEMAND_URL,
                "/api/member/stock-contracts", "/api/customers", "/api/sales-contracts"):
        assert client.get(url, headers=pur).status_code == 200, url


def test_stock_and_contract_accounts(et) -> None:
    stk, con, day = et["stk"], et["con"], TODAY.isoformat()
    assert _daily(stk, "consumption", {"stock_material": 2}).status_code == 200
    assert _denied(_daily(stk, "purchase", {"latex_wet": 1}), "Thu mua")
    sc = client.put("/api/member/stock-contracts", headers=stk,
                    json={"company": UNIT, "grade": "Chủng loại khác", "qty": 1, "start_date": day})
    assert sc.status_code == 200, sc.text

    assert _denied(_daily(con, "purchase", {"latex_wet": 1}), "Thu mua")
    assert _denied(client.put("/api/member/prices", headers=con, json={
        "company": UNIT, "as_of": day, "price_type": "purchase", "price": 300}), "Thu mua")
    assert client.put("/api/customers", json={"company": UNIT, "name": "ZZ KH"}, headers=con).status_code == 200
    item = client.put(DEMAND_URL, headers=con,
                      json={"company": UNIT, "as_of": day, "customer": "KH", "grade": "LATEX"})
    assert item.status_code == 200, item.text
    assert client.delete(f"{DEMAND_URL}/{item.json()['item']['id']}", headers=con).status_code == 200
    # Tập đoàn (admin) không bị ràng buộc theo loại.
    assert client.put("/api/customers", json={"company": UNIT, "name": "ZZ KH admin"},
                      headers=et["admin"]).status_code == 200


def test_year_plan_drops_fields_outside_entry_types(et) -> None:
    year = TODAY.year
    unit_daily_repo.set_year_plan(year, UNIT, 100.0, 50.0, None, None, None, 9.0, "admin")
    plan = lambda: unit_daily_repo.year_plan(year, [UNIT])[UNIT]   # noqa: E731
    put = lambda who, **v: client.put("/api/member/plan", headers=et[who],   # noqa: E731
                                      json={"year": year, "company": UNIT, **v})
    full = {"plan_tonnes": 111, "signed_lt_tonnes": 222, "plan_revenue_ty": 333}

    assert put("pur", **full).status_code == 200            # web gửi cả form: chỉ ô Thu mua được ghi
    assert (plan()["plan_tonnes"], plan()["signed_lt_tonnes"], plan()["plan_revenue_ty"]) == (111, 50, 9)
    assert put("con", **full).status_code == 200
    assert (plan()["plan_tonnes"], plan()["signed_lt_tonnes"], plan()["plan_revenue_ty"]) == (111, 222, 333)
    assert put("con", plan_tonnes=None, plan_revenue_ty=None).status_code == 200   # null chỉ xoá ô của mình
    assert plan()["plan_tonnes"] == 111 and plan()["plan_revenue_ty"] is None
    # Gửi toàn ô ngoài loại → 403, không âm thầm "lưu thành công" mà chẳng ghi gì.
    assert _denied(put("pur", signed_lt_tonnes=1), "Hợp đồng")
    assert _denied(put("con", plan_tonnes=1), "Thu mua")
    assert _denied(put("stk", **full), "Thu mua")
    assert plan()["signed_lt_tonnes"] == 222


def test_checklist_shows_only_own_entry_types(et) -> None:
    before = config_repo.get_value(edit_window.ALERT_KEY)
    config_repo.set_config({edit_window.ALERT_KEY: "5"}, "test")
    usd = {"grade": "SVR 3L", "qty": 20.0, "price": 1800.0, "ccy": "USD", "fx": None}
    try:
        with session_scope() as db:   # lần giao ngoại tệ thiếu tỷ giá → nhóm Hợp đồng & tiêu thụ
            db.execute(text("INSERT INTO sales_contract (company, code, delivered, delivered_at, lines) "
                            "VALUES (:c, 'ZZ-ET-USD', true, CAST(:d AS date), CAST(:l AS jsonb))"),
                       {"c": UNIT, "d": date(TODAY.year, 1, 1).isoformat(), "l": json.dumps([usd])})
        got = {who: client.get("/api/member/checklist", headers=et[who]).json() for who in ACCOUNTS}
        lead, pur, stk, con = (got[w]["units"][0] for w in ("lead", "pur", "stk", "con"))
        assert len(lead["stock_missing"]) == 5 and lead["year_plan_missing"] and len(lead["missing_fx"]) == 1

        assert pur["stock_missing"] == [] and pur["missing_fx"] == [] and pur["year_plan_missing"] is True
        assert stk["stock_missing"] == lead["stock_missing"] and stk["year_plan_missing"] is False
        assert stk["missing_fx"] == [] and got["stk"]["total_missing"] == 5
        assert con["stock_missing"] == [] and con["year_plan_missing"] is False and len(con["missing_fx"]) == 1
        assert pur["data_checks"] == [] and stk["data_checks"] == []
        assert all(c["kind"] == "contract" for c in con["data_checks"])
        assert got["con"]["total_missing"] == 1 + len(con["data_checks"])
        assert got["lead"]["total_missing"] == 5 + 1 + 1 + len(lead["data_checks"])
    finally:
        config_repo.set_config({edit_window.ALERT_KEY: before or "__CLEAR__"}, "test")


def test_checklist_filter_helpers() -> None:
    row = {"company": "X", "needs_purchase": True, "purchase_missing": ["d"], "stock_missing": ["d"],
           "year_plan_missing": True, "year": 2026, "pending_batches": [{}], "missing_fx": [{}],
           "completed_no_delivery": [{}],
           "data_checks": [{"kind": "purchase"}, {"kind": "stock"}, {"kind": "contract"}]}
    out = member_checklist._only_types(row, {"stock"})
    assert out["needs_purchase"] is False and out["purchase_missing"] == [] and out["year_plan_missing"] is False
    assert out["stock_missing"] == ["d"] and [c["kind"] for c in out["data_checks"]] == ["stock"]
    assert out["pending_batches"] == out["missing_fx"] == out["completed_no_delivery"] == []
    assert member_checklist._row_total(out) == 2 and member_checklist._row_total(row) == 9


def test_leader_is_not_restricted_by_entry_types(et) -> None:
    r = _daily(et["lead"], "purchase", {"latex_wet": 1})
    assert r.status_code == 403 and "lãnh đạo" in r.json()["detail"].lower() and DENIED not in r.json()["detail"]


def test_every_edit_request_op_has_entry_type() -> None:
    """Op mới thêm mà quên khai loại → test này đỏ (prepare ném KeyError = đóng chặt)."""
    for key in edit_request_ops._registry():
        for kind in ("purchase", "consumption"):
            assert edit_request_ops.entry_type_of(key, {"kind": kind}) in ENTRY_TYPES


def test_edit_request_follows_entry_types(env) -> None:
    e, unit = env, edit_request_env.UNIT
    member = "/api/users/_zz_er_member"
    assert client.put(member, json={"entry_types": ["purchase"]}, headers=e["admin"]).status_code == 200
    older = (date.fromisoformat(OLD) - timedelta(days=1)).isoformat()
    stock = {"kind": "consumption", "company": unit, "as_of": OLD}
    assert _denied(send(e["member"], "daily_report", {**stock, "fields": {"stock_material": 3}}), "Tồn kho")
    assert _denied(send(e["member"], "daily_move", {**stock, "to_date": older}), "Tồn kho")
    assert _denied(send(e["member"], "demand_save", demand()), "Hợp đồng")
    assert _denied(send(e["member"], "contract_delete", {"id": 2_000_000_000}), "Hợp đồng")

    ok = send(e["member"], "daily_report",
              {"kind": "purchase", "company": unit, "as_of": OLD, "fields": {"latex_wet": 5}})
    assert ok.status_code == 200, ok.text
    # Ban duyệt KHÔNG xét loại nhập liệu: đổi loại sau khi gửi vẫn duyệt được.
    assert client.put(member, json={"entry_types": ["stock"]}, headers=e["admin"]).status_code == 200
    done = approve(e["editor"], ok.json()["request"]["id"])
    assert done.status_code == 200, done.text


def test_sales_keys_cover_legacy_consumption_fields() -> None:
    assert {"sales", "sales_own", "revenue", "sales_ccy", "sales_migrated", "purchased_sold_qty",
            "purchased_sold_revenue", "finished_sold_qty", "finished_sold_ccy"} <= CONSUMPTION_SALES_KEYS
    assert not CONSUMPTION_SALES_KEYS & {"fx_revenue", "stock_material", "stock_ccy", "no_stock",
                                         "stock_warehoused", "stock_not_warehoused"}


def test_stock_only_cannot_change_legacy_sales(et) -> None:
    """CV Tồn kho gửi ô tiêu thụ cũ → server giữ đúng số ĐANG LƯU (không 403, vì web gửi lại nguyên)."""
    day = TODAY.isoformat()
    unit_daily_repo.upsert("consumption", day, UNIT, {**LEGACY, "stock_material": 1}, "admin")
    legacy = _sales_part(_stored(day))
    assert legacy["revenue"] == 200_000_000 and legacy["sales"][0]["code"] == "HD-CU"

    assert _daily(et["stk"], "consumption", FORGED).status_code == 200
    got = _stored(day)
    assert got["stock_material"] == 3 and _sales_part(got) == legacy   # ô chưa lưu (finished_*) bị bỏ
    assert _daily(et["stk"], "consumption", {**got, "stock_material": 4}).status_code == 200
    assert _stored(day)["stock_material"] == 4 and _sales_part(_stored(day)) == legacy

    # Được giao thêm Hợp đồng & tiêu thụ → đổi được ô tiêu thụ cũ như trước.
    r = client.put("/api/users/_zz_et_stk", json={"entry_types": ["stock", "contract"]},
                   headers=et["admin"])
    assert r.status_code == 200
    assert _daily(et["stk"], "consumption", FORGED).status_code == 200
    assert (_stored(day)["purchased_sold_qty"], _stored(day)["sales"]) == (99, [])


def test_edit_request_stock_only_carries_stored_sales(env) -> None:
    """Đề nghị sửa biểu Tồn kho của CV Tồn kho: nội dung chờ duyệt mang ô tiêu thụ ĐANG LƯU."""
    e, unit = env, edit_request_env.UNIT
    assert client.put("/api/users/_zz_er_member", json={"entry_types": ["stock"]},
                      headers=e["admin"]).status_code == 200
    unit_daily_repo.upsert("consumption", OLD, unit, {**LEGACY, "stock_material": 1}, "admin")
    legacy = _sales_part(_stored(OLD, unit))
    r = send(e["member"], "daily_report",
             {"kind": "consumption", "company": unit, "as_of": OLD, "fields": FORGED})
    assert r.status_code == 200, r.text
    fields = r.json()["request"]["payload"]["fields"]
    assert fields["stock_material"] == 3 and _sales_part(fields) == legacy

    done = approve(e["editor"], r.json()["request"]["id"])
    assert done.status_code == 200, done.text
    assert _stored(OLD, unit)["stock_material"] == 3 and _sales_part(_stored(OLD, unit)) == legacy


def test_cancel_edit_request_follows_entry_types(env) -> None:
    """Cùng đơn vị nhưng khác phần việc → không huỷ được đề nghị của đồng nghiệp."""
    e, unit = env, edit_request_env.UNIT
    ok = send(e["member"], "daily_report",
              {"kind": "purchase", "company": unit, "as_of": OLD, "fields": {"latex_wet": 5}})
    assert ok.status_code == 200, ok.text
    cancel = f"/api/member/edit-requests/{ok.json()['request']['id']}/cancel"
    user_url = "/api/users/_zz_er_member"
    assert client.put(user_url, json={"entry_types": ["stock"]}, headers=e["admin"]).status_code == 200
    assert _denied(client.post(cancel, headers=e["member"]), "Thu mua")
    assert client.put(user_url, json={"entry_types": ["purchase"]}, headers=e["admin"]).status_code == 200
    r = client.post(cancel, headers=e["member"])
    assert r.status_code == 200 and r.json()["request"]["status"] == "cancelled"
