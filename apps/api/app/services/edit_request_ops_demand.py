"""Thao tác «Đề nghị sửa» cho phiếu NHU CẦU THỊ TRƯỜNG: thêm-sửa (`demand_save`) · xoá (`demand_delete`).

Hàng rào = `market_demand_item_policy.fence_dates` (đúng luật router đơn vị dùng) với cửa sổ ĐƠN VỊ:
chỉ đổi ô theo dõi thì không bị chặn nên không cần đề nghị. Nhu cầu không nằm trong chốt số liệu
(`lockable=False`) — duyệt không gỡ đợt chốt nào.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core import edit_window
from app.core.market_demand_meta import CURRENCIES, DATA_FIELDS, QTY_UNITS
from app.core.unit_guard import assert_unit_can_enter
from app.schemas.market_demand_item import DemandDeleteIn, DemandItemIn
from app.services import market_demand_item_policy as policy
from app.services import market_demand_item_repo as repo
from app.services.edit_request_ops import (
    Op, assert_assigned, collect_blocked, dmy, parse, uniq_dates,
)

_NOT_FOUND = "Không tìm thấy phiếu nhu cầu trong phạm vi tài khoản."
_LABELS = {"qty_unit": QTY_UNITS, "currency": CURRENCIES}


def _window(as_of: str):
    return lambda: edit_window.assert_editable(as_of, edit_window.member_window())


def _snapshot(item_id: int | None) -> dict | None:
    """Ảnh chụp CHỈ các ô dữ liệu (không mốc thời gian) — người duyệt so trước/sau cho gọn."""
    row = repo.get(item_id) if item_id else None
    return {"id": row["id"], **{f: row[f] for f in DATA_FIELDS}} if row else None


def _title(prefix: str, row: dict) -> str:
    return f"{prefix} {row['customer']} · {row['grade']} ngày {dmy(row['as_of'])}"


# ── Thêm / sửa ───────────────────────────────────────────────────────────────
def _save_validate(payload: Any) -> dict:
    return policy.clean(parse(DemandItemIn, payload).model_dump())


def _save_company(p: dict, before: dict | None) -> str:
    if p.get("id") and before is None:
        raise HTTPException(404, _NOT_FOUND)
    # Đổi đơn vị của phiếu cũ qua đề nghị thì phải kiểm quyền với CẢ hai đơn vị — không mở đường đó.
    if before and before["company"] != p["company"]:
        raise HTTPException(403, "Phiếu nhu cầu thuộc đơn vị khác.")
    return p["company"]


def _save_scope(user: dict, company: str, p: dict) -> None:
    """Y như `member_self._assert_company`: đơn vị được gán + luật sáp nhập theo ngày nhận."""
    assert_assigned(user, company)
    assert_unit_can_enter(company, p["as_of"], require_known=False)


def _save_key(p: dict) -> str:
    if p.get("id"):
        return f"demand:{p['id']}"
    return f"demand:new:{p['company']}:{p['as_of']}:{p['customer'].lower()}:{p['grade']}"


def _save_blocked(_username: str, p: dict, before: dict | None) -> list[str]:
    return collect_blocked(*(_window(d) for d in policy.fence_dates(before, p)))


def _save_apply(p: dict, requester: str, company: str) -> dict:
    saved = repo.save({**p, "company": company}, requester)
    if saved is None:
        raise HTTPException(404, _NOT_FOUND)
    return {"item": saved}


# ── Xoá ──────────────────────────────────────────────────────────────────────
def _delete_company(_p: dict, before: dict | None) -> str:
    if before is None:
        raise HTTPException(404, _NOT_FOUND)
    return before["company"]


def _delete_blocked(_username: str, _p: dict, before: dict | None) -> list[str]:
    if before is None:
        raise HTTPException(404, _NOT_FOUND)
    return collect_blocked(_window(before["as_of"]))


def _delete_apply(p: dict, _requester: str, company: str) -> dict:
    if not repo.delete(int(p["id"]), [company]):
        raise HTTPException(404, _NOT_FOUND)
    return {"ok": True}


OPS: dict[str, Op] = {
    "demand_save": Op(
        label=lambda _p: "Nhu cầu thị trường",
        validate=_save_validate, snapshot=lambda p: _snapshot(p.get("id")),
        company=_save_company, check_scope=_save_scope,
        # Duyệt sau vài ngày: kiểm lại luật (vd chủng loại còn trong danh mục).
        precheck=lambda p, _b: policy.clean(p),
        target_key=_save_key, labels=lambda _rows: _LABELS,
        title=lambda p, _b: _title("Nhu cầu", p),
        dates=lambda p, b: uniq_dates((b or {}).get("as_of"), p["as_of"]),
        blocked=_save_blocked, apply=_save_apply, lockable=False),
    "demand_delete": Op(
        label=lambda _p: "Xoá nhu cầu thị trường",
        validate=lambda payload: {"id": parse(DemandDeleteIn, payload).id},
        snapshot=lambda p: _snapshot(p["id"]),
        company=_delete_company, check_scope=lambda user, company, _p: assert_assigned(user, company),
        target_key=lambda p: f"demand:{p['id']}", labels=lambda _rows: _LABELS,
        title=lambda p, b: _title("Xoá nhu cầu", b) if b else f"Xoá nhu cầu #{p['id']}",
        dates=lambda _p, b: uniq_dates((b or {}).get("as_of")),
        blocked=_delete_blocked, apply=_delete_apply, lockable=False),
}
