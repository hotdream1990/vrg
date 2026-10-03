"""Thao tác «Đề nghị sửa» cho KẾ HOẠCH NĂM (`year_plan`) — chỉ tiêu năm đã chốt CÙNG ĐỢT chốt số liệu.

Payload = body `PUT /api/member/plan` (`PurchasePlanEdit`): chỉ ô CÓ trong body được ghi (null = xoá
ô đó), ô vắng mặt giữ nguyên. Hàng rào = `data_lock.assert_plan_not_locked` (kế hoạch năm không có
cửa sổ ngày). Ô ngoài loại nhập liệu của tài khoản bị bỏ lúc gửi (`plan_values_allowed`, cùng luật ghi
thẳng). Duyệt: ghi `save_year_plan` rồi gỡ xác nhận chốt của đơn vị ở các đợt CHƯA HUỶ trong ĐÚNG năm
đó (`unlock_until`) — chỉ tiêu đổi nên đơn vị rà và xác nhận lại; đợt của năm sau giữ nguyên.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core import data_lock
from app.core.entry_types import plan_values_allowed
from app.core.unit_guard import assert_unit_can_enter
from app.schemas.unit_daily import PurchasePlanEdit
from app.services import unit_daily_repo
from app.services.edit_request_ops import Op, assert_assigned, collect_blocked, parse


def values_of(p: dict) -> dict[str, float | None]:
    """Các ô kế hoạch có trong payload (kể cả null = xoá ô)."""
    return {k: p[k] for k in unit_daily_repo.PLAN_FIELDS if k in p}


def _validate(payload: Any) -> dict:
    m = parse(PurchasePlanEdit, payload)
    values = m.plan_values()
    if not values:
        raise HTTPException(400, "Đề nghị chưa có ô kế hoạch nào để sửa.")
    return {"year": m.year, "company": m.company, **values}


def _restrict(user: dict, p: dict) -> dict:
    return {"year": p["year"], "company": p["company"], **plan_values_allowed(user, values_of(p))}


def _snapshot(p: dict) -> dict | None:
    row = unit_daily_repo.year_plan(int(p["year"]), [p["company"]]).get(p["company"])
    return dict(row) if row else None


def _scope(user: dict, company: str, p: dict) -> None:
    """Như `member_self._assert_company` của PUT /plan: đơn vị được gán + luật sáp nhập (mốc 01/01)."""
    assert_assigned(user, company)
    assert_unit_can_enter(company, f"{p['year']}-01-01", require_known=False)


def _blocked(_username: str, p: dict, _before: dict | None) -> list[str]:
    return collect_blocked(lambda: data_lock.assert_plan_not_locked(p["company"], int(p["year"])))


def _apply(p: dict, requester: str, company: str) -> dict:
    unit_daily_repo.save_year_plan(int(p["year"]), company, values_of(p), requester)
    return {"ok": True}


OPS: dict[str, Op] = {
    "year_plan": Op(
        label=lambda _p: "Kế hoạch năm",
        validate=_validate, restrict=_restrict, snapshot=_snapshot,
        company=lambda p, _b: p["company"], check_scope=_scope,
        target_key=lambda p: f"plan:{p['year']}",
        title=lambda p, _b: f"Kế hoạch năm {p['year']}",
        # Ngày "bị ảnh hưởng" = cả năm: popup cảnh báo gỡ chốt từ 01/01; gỡ chỉ tới hết năm đó.
        dates=lambda p, _b: [f"{p['year']}-01-01"],
        unlock_until=lambda p: f"{p['year']}-12-31",
        blocked=_blocked, apply=_apply),
}
