"""Router màn "DASHBOARD ĐƠN VỊ" — bức tranh thu mua · tồn kho · tiêu thụ · chỉ tiêu của MỘT phạm vi.

Ai xem được gì (ép ở server, không tin client gửi lên):
- tài khoản có quyền `unit_daily` (quản trị · chuyên viên · lãnh đạo Tập đoàn) → mọi phạm vi:
  toàn Tập đoàn · một khu vực · một đơn vị;
- tài khoản đơn vị (`member` nhập liệu · `leader` lãnh đạo đơn vị) → CHỈ đơn vị được gán.

Chỉ có GET. Mỗi phần số liệu một endpoint để web tải song song, phần nào xong hiện phần đó.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.edit_window import today
from app.core.security import cap_or_member_scope
from app.routers.unit_scorecard import assert_dates
from app.services import unit_dashboard as svc
from app.services import unit_dashboard_outlook as outlook_svc
from app.services import unit_dashboard_scope as scope_svc
from app.services import unit_dashboard_targets as targets_svc
from app.services import user_repo

router = APIRouter(prefix="/api/unit-dashboard", tags=["unit-dashboard"])
_access = cap_or_member_scope("unit_daily")

_SCOPE = "^(" + "|".join(scope_svc.SCOPES) + ")$"
#: Chỉ nhận đúng YYYY-MM-DD: `date.fromisoformat` còn nhận "20260805" hay "2026-W01-1", mà phía sau
#: so ngày bằng CHUỖI (kẹp về hôm nay…) → số sai lặng lẽ hoặc lỗi 500.
_DATE = r"^\d{4}-\d{2}-\d{2}$"
#: Kỳ xem tối đa ~3 năm — chuỗi diễn biến dựng mọi mốc trong kỳ, kỳ vô hạn là hàng chục nghìn dòng.
MAX_PERIOD_DAYS = 366 * 3
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
            date_from: str = Query(..., pattern=_DATE, description="Từ ngày YYYY-MM-DD"),
            date_to: str = Query(..., pattern=_DATE, description="Đến ngày YYYY-MM-DD"),
            as_of: str | None = Query(None, pattern=_DATE,
                                      description="Ngày chốt tồn kho; trống = ngày cuối của biểu "
                                                  "đồ diễn biến (đã đủ đơn vị khai)"),
            own: list[str] | None = Depends(_viewer)) -> dict[str, Any]:
    assert_dates(date_from, date_to, as_of)
    if (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days >= MAX_PERIOD_DAYS:
        raise HTTPException(400, "Kỳ xem dài quá 3 năm — chọn kỳ ngắn hơn.")
    try:
        sc = scope_svc.resolve(scope, key, own)
    except scope_svc.ScopeDenied as exc:
        raise HTTPException(403, str(exc)) from exc
    except scope_svc.ScopeNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"sc": sc, "date_from": date_from, "date_to": date_to, "as_of": as_of,
            "today": today().isoformat()}


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
    """Tồn kho TẠI ngày chốt (số thời điểm, không cộng dồn theo kỳ) — trống = tự lấy, xem `stock_day`."""
    day, auto = svc.stock_day(q["sc"], q["date_from"], q["date_to"], q["as_of"], q["today"])
    return svc.stock_block(q["sc"], day, auto)


@router.get("/stock-series")
def stock_series(view: str = Query("warehouse", pattern=_VIEW),
                 q: dict = Depends(_params)) -> dict:
    """Diễn biến tồn kho theo ngày của phạm vi (tối đa 180 ngày, kết thúc ở hôm nay)."""
    return svc.stock_series_block(q["sc"], q["date_from"], q["date_to"], view, q["today"])


@router.get("/targets")
def targets(q: dict = Depends(_params)) -> dict:
    """Chỉ tiêu năm: thực hiện lũy kế từ 01/01 đến hết kỳ (không quá hôm nay) so với kế hoạch."""
    return targets_svc.targets_block(q["sc"], q["date_to"], q["today"])


@router.get("/outlook")
def outlook(q: dict = Depends(_params)) -> dict:
    """Tiến độ bán hàng năm: HĐ dài hạn theo HĐ mẹ · còn phải giao · so KH bán hàng · DT dự kiến."""
    return outlook_svc.outlook_block(q["sc"], q["date_to"], q["today"])
