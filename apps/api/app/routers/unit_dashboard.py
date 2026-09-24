"""Router màn "DASHBOARD ĐƠN VỊ" — bức tranh thu mua · tồn kho · tiêu thụ · chỉ tiêu của MỘT phạm vi.

Ai xem được gì (ép ở server, không tin client gửi lên):
- tài khoản có quyền `unit_daily` (quản trị · chuyên viên · lãnh đạo Tập đoàn) → mọi phạm vi:
  toàn Tập đoàn · một khu vực · một đơn vị;
- tài khoản đơn vị (`member` nhập liệu · `leader` lãnh đạo đơn vị) → CHỈ đơn vị được gán.

Chỉ có GET. Mỗi phần số liệu một endpoint để web tải song song, phần nào xong hiện phần đó.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.edit_window import today
from app.core.security import cap_or_member_scope
from app.routers.unit_scorecard import assert_dates, stock_day
from app.services import unit_dashboard as svc
from app.services import unit_dashboard_scope as scope_svc
from app.services import unit_dashboard_targets as targets_svc
from app.services import user_repo

router = APIRouter(prefix="/api/unit-dashboard", tags=["unit-dashboard"])
_access = cap_or_member_scope("unit_daily")

_SCOPE = "^(" + "|".join(scope_svc.SCOPES) + ")$"
_VIEW = "^(" + "|".join(svc.STOCK_VIEWS) + ")$"


def _viewer(access: tuple[str, list[str] | None] = Depends(_access)) -> list[str] | None:
    """Đơn vị ĐƯỢC GÁN của tài khoản đơn vị (không gồm đơn vị cũ đã sáp nhập vào — số của họ đã nằm
    trong dashboard của đơn vị nhận); `None` = tài khoản xem được mọi phạm vi."""
    username, units = access
    if units is None:
        return None
    return list((user_repo.get_user(username) or {}).get("member_units") or [])


def _params(scope: str = Query("group", pattern=_SCOPE),
            key: str | None = Query(None, description="Tên khu vực / đơn vị"),
            date_from: str = Query(..., description="Từ ngày YYYY-MM-DD"),
            date_to: str = Query(..., description="Đến ngày YYYY-MM-DD"),
            as_of: str | None = Query(None, description="Ngày chốt tồn kho; mặc định = đến ngày"),
            own: list[str] | None = Depends(_viewer)) -> dict[str, Any]:
    assert_dates(date_from, date_to, as_of)
    try:
        sc = scope_svc.resolve(scope, key, own)
    except scope_svc.ScopeDenied as exc:
        raise HTTPException(403, str(exc)) from exc
    except scope_svc.ScopeNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"sc": sc, "date_from": date_from, "date_to": date_to,
            "as_of": stock_day(date_to, as_of), "today": today().isoformat()}


@router.get("/scopes")
def scopes(own: list[str] | None = Depends(_viewer)) -> dict:
    """Danh mục cho ô chọn phạm vi — tài khoản đơn vị chỉ nhận lại đơn vị được gán."""
    try:
        cat = scope_svc.catalog(own)
    except scope_svc.ScopeDenied as exc:
        raise HTTPException(403, str(exc)) from exc
    return {**cat, "today": today().isoformat()}


@router.get("/purchase")
def purchase(q: dict = Depends(_params)) -> dict:
    """Thu mua trong kỳ: theo loại mủ · diễn biến · thành phẩm theo chủng loại · theo khu vực/đơn vị."""
    return svc.purchase_block(q["sc"], q["date_from"], q["date_to"], q["today"])


@router.get("/consumption")
def consumption(q: dict = Depends(_params)) -> dict:
    """Tiêu thụ trong kỳ: loại HĐ · hình thức · chủng loại · diễn biến · theo khu vực/đơn vị."""
    return svc.consumption_block(q["sc"], q["date_from"], q["date_to"], q["today"])


@router.get("/stock")
def stock(q: dict = Depends(_params)) -> dict:
    """Tồn kho TẠI ngày chốt (số thời điểm, không cộng dồn theo kỳ)."""
    return svc.stock_block(q["sc"], q["as_of"])


@router.get("/stock-series")
def stock_series(view: str = Query("warehouse", pattern=_VIEW),
                 q: dict = Depends(_params)) -> dict:
    """Diễn biến tồn kho theo ngày của phạm vi (tối đa 180 ngày, kết thúc ở hôm nay)."""
    return svc.stock_series_block(q["sc"], q["date_from"], q["date_to"], view, q["today"])


@router.get("/targets")
def targets(q: dict = Depends(_params)) -> dict:
    """Chỉ tiêu năm: thực hiện lũy kế từ 01/01 đến hết kỳ (không quá hôm nay) so với kế hoạch."""
    return targets_svc.targets_block(q["sc"], q["date_to"], q["today"])
