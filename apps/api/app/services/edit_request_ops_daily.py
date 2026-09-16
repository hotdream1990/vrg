"""Thao tác «Đề nghị sửa» cho số liệu THEO NGÀY: biểu Thu mua/Tồn kho · đổi ngày biểu · nhu cầu thị trường.

Hàng rào gọi lại đúng như `routers/member_self.py`: cửa sổ sửa của đơn vị (`member_window`) + chốt
số liệu (nhu cầu thị trường chỉ có cửa sổ). Khi duyệt: ghi thẳng repo, `updated_by` = người GỬI.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from app.core import data_lock, edit_window, request_ctx
from app.core.db import ensure_schema, session_scope
from app.core.market_meta import PURCHASE_PRICE_TYPES, PURCHASE_SOURCE_UNIT
from app.core.unit_guard import assert_unit_can_enter
from app.schemas.edit_request import DailyReportRequest
from app.schemas.market_demand import MarketDemandEdit
from app.schemas.unit_daily import UnitDailyMove
from app.services import (
    market_demand_repo, price_repo, unit_daily_fields, unit_daily_repo, unit_purchase_price,
)
from app.services.edit_request_ops import (
    Op, assert_assigned, collect_blocked, dmy, iso_date, parse,
)

_KIND = {"purchase": "Biểu Thu mua", "consumption": "Biểu Tồn kho"}
_MOVE = {"purchase": "Đổi ngày biểu Thu mua", "consumption": "Đổi ngày biểu Tồn kho"}


def _day_fields(kind: str, as_of: str, company: str) -> dict[str, Any] | None:
    """Payload ĐÃ LƯU của 1 ngày (không gắn khối 3 tự tính như `entries_on`) — None = chưa có dòng."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM unit_daily_report "
                              "WHERE kind = :k AND as_of = CAST(:d AS date) AND company = :c"),
                         {"k": kind, "d": as_of, "c": company}).first()
    return dict(row[0] or {}) if row else None


def _unit_prices(as_of: str, company: str) -> dict[str, float]:
    """Đơn giá lớp đơn vị tự khai đúng ngày — chỉ loại đang có giá."""
    got = {pt: price_repo.purchase_by_company_on_date(as_of, pt, PURCHASE_SOURCE_UNIT).get(company)
           for pt in PURCHASE_PRICE_TYPES}
    return {pt: v for pt, v in got.items() if v is not None}


def _window(as_of: str):
    return lambda: edit_window.assert_editable(as_of, edit_window.member_window())


def _lock(company: str, *dates: str):
    return lambda: data_lock.assert_not_locked(company, *dates)


def _scope_on(date_key: str):
    """Quyền theo đơn vị y như `member_self._assert_company` (đơn vị được gán + luật sáp nhập)."""
    def check(user: dict, company: str, p: dict) -> None:
        assert_assigned(user, company)
        assert_unit_can_enter(company, p[date_key], require_known=False)
    return check


# ── Biểu Thu mua / Tồn kho ────────────────────────────────────────────────────
def _report_validate(payload: Any) -> dict:
    m = parse(DailyReportRequest, payload)
    out = {"kind": m.kind, "company": m.company, "as_of": iso_date(m.as_of),
           "fields": unit_daily_fields.clean_fields(m.kind, m.fields)}
    if m.kind == "purchase" and m.prices is not None:
        out["prices"] = {k: v for k, v in m.prices.model_dump().items() if v is not None}
    return {**out, "create_only": True} if m.create_only else out


def _report_snapshot(p: dict) -> dict:
    prices = _unit_prices(p["as_of"], p["company"]) if p["kind"] == "purchase" else {}
    return {"fields": _day_fields(p["kind"], p["as_of"], p["company"]), "prices": prices}


def _report_precheck(p: dict, before: dict | None) -> None:
    """Nút Thêm mà ngày đó đã có số ⇒ đúng câu 409 của API ghi thẳng (`member_self.upsert_my_daily`)."""
    if p.get("create_only") and (before or {}).get("fields") is not None:
        raise HTTPException(409, "Đơn vị này đã có số liệu cho ngày này — vui lòng dùng chức năng Sửa.")


def _report_apply(p: dict, requester: str, company: str) -> dict:
    note = request_ctx.default_note()
    unit_daily_repo.upsert(p["kind"], p["as_of"], company, p["fields"], requester,
                           note=f"{_KIND[p['kind']]} — {note}" if note else None)
    for price_type, price in (p.get("prices") or {}).items():
        unit_purchase_price.save(company, p["as_of"], price_type, price)
    return {"ok": True}


# ── Đổi ngày biểu ────────────────────────────────────────────────────────────
def _move_validate(payload: Any) -> dict:
    m = parse(UnitDailyMove, payload)
    out = {"kind": m.kind, "company": m.company, "as_of": iso_date(m.as_of),
           "to_date": iso_date(m.to_date, "Ngày mới")}
    if out["to_date"] == out["as_of"]:
        raise HTTPException(400, "Ngày mới trùng ngày hiện tại của bản ghi.")
    return out


def _move_snapshot(p: dict) -> dict:
    return {"fields": _day_fields(p["kind"], p["as_of"], p["company"]),
            "to_date_has_entry": _day_fields(p["kind"], p["to_date"], p["company"]) is not None}


def _move_precheck(p: dict, before: dict | None) -> None:
    """Cùng luật với `unit_daily_repo.move_day` — báo ngay lúc gửi thay vì để Ban duyệt mới lỗi."""
    if not before or before.get("fields") is None:
        raise HTTPException(400, "Không tìm thấy số liệu của ngày cần đổi.")
    if before.get("to_date_has_entry"):
        raise HTTPException(400, f"Ngày {dmy(p['to_date'])} đã có số liệu của {p['company']} — "
                                 "xoá số ngày đó hoặc chọn ngày khác.")


def _move_apply(p: dict, requester: str, company: str) -> dict:
    try:
        return {"ok": True, **unit_daily_repo.move_day(p["kind"], company, p["as_of"],
                                                       p["to_date"], requester)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# ── Nhu cầu thị trường ───────────────────────────────────────────────────────
def _demand_validate(payload: Any) -> dict:
    m = parse(MarketDemandEdit, payload)
    out = {"company": m.company, "as_of": iso_date(m.as_of), "content": m.content.strip()}
    return {**out, "create_only": True} if m.create_only else out


def _demand_precheck(p: dict, before: dict | None) -> None:
    if p.get("create_only") and str((before or {}).get("content") or "").strip():
        raise HTTPException(409, "Đơn vị này đã có nhu cầu cho ngày này — vui lòng dùng chức năng Sửa.")


def _demand_apply(p: dict, requester: str, company: str) -> dict:
    market_demand_repo.upsert(p["as_of"], company, p["content"], requester)
    return {"ok": True}


def _company(p: dict, _before: dict | None) -> str:
    return p["company"]


OPS: dict[str, Op] = {
    "daily_report": Op(
        label=lambda p: _KIND[p["kind"]],
        validate=_report_validate, snapshot=_report_snapshot, company=_company,
        check_scope=_scope_on("as_of"), precheck=_report_precheck,
        target_key=lambda p: f"daily:{p['kind']}:{p['as_of']}",
        title=lambda p, _b: f"{_KIND[p['kind']]} ngày {dmy(p['as_of'])}",
        dates=lambda p, _b: [p["as_of"]],
        blocked=lambda _u, p, _b: collect_blocked(_window(p["as_of"]),
                                                  _lock(p["company"], p["as_of"])),
        apply=_report_apply),
    "daily_move": Op(
        label=lambda p: _MOVE[p["kind"]],
        validate=_move_validate, snapshot=_move_snapshot, company=_company,
        # Ngày ĐÍCH là ngày số liệu nằm sau khi dời — đúng mốc router gốc dùng.
        check_scope=_scope_on("to_date"), precheck=_move_precheck,
        # Khoá RIÊNG: đề nghị đổi ngày không được đè đề nghị sửa nội dung cùng ngày (và ngược lại).
        target_key=lambda p: f"daily_move:{p['kind']}:{p['as_of']}",
        title=lambda p, _b: f"{_MOVE[p['kind']]} {dmy(p['as_of'])} → {dmy(p['to_date'])}",
        dates=lambda p, _b: sorted({p["as_of"], p["to_date"]}),
        blocked=lambda _u, p, _b: collect_blocked(
            _window(p["as_of"]), _window(p["to_date"]),
            _lock(p["company"], p["as_of"], p["to_date"])),
        apply=_move_apply),
    "market_demand": Op(
        label=lambda _p: "Nhu cầu thị trường",
        validate=_demand_validate,
        snapshot=lambda p: {"content": market_demand_repo.entries_on(p["as_of"]).get(p["company"], "")},
        company=_company, check_scope=_scope_on("as_of"), precheck=_demand_precheck,
        target_key=lambda p: f"demand:{p['as_of']}",
        title=lambda p, _b: f"Nhu cầu thị trường ngày {dmy(p['as_of'])}",
        dates=lambda p, _b: [p["as_of"]],
        blocked=lambda _u, p, _b: collect_blocked(_window(p["as_of"])),
        apply=_demand_apply, lockable=False),   # nhu cầu thị trường không nằm trong chốt số liệu
}
