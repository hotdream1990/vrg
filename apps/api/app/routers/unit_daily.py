"""Router báo cáo tiêu thụ–tồn kho theo NGÀY cho CHUYÊN VIÊN có quyền `unit_daily` — xem/sửa MỌI đơn vị (realtime).

Đơn vị thành viên tự nhập của mình qua `/api/member/daily-report` (router member_self).
Chuyên viên (editor được cấp quyền / admin) xem toàn bộ + sửa, áp cửa sổ sửa theo ngày của chuyên viên,
và cấu hình chỉ tiêu kế hoạch thu mua năm (để tính % thực hiện).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import edit_window
from app.core.security import assert_editor_window, require_cap
from app.schemas.unit_daily import PurchasePlanEdit, UnitDailyEdit
from app.services import member_unit_repo, unit_daily_repo

router = APIRouter(prefix="/api/unit-daily", tags=["unit-daily"])
_require = require_cap("unit_daily")


def _year_of(as_of: str) -> int:
    """Năm dương lịch của ngày báo cáo — dùng khớp chỉ tiêu kế hoạch năm."""
    return date.fromisoformat(as_of).year


@router.get("/timeline")
def timeline(kind: str = Query(..., pattern="^(purchase|consumption)$"),
             days: int = Query(90, ge=1, le=730),
             username: str = Depends(_require)) -> dict:
    """Timeline tổng quát: các bản ghi ĐÃ có số liệu (ẩn ngày trống) trong `days` ngày gần nhất."""
    today = edit_window.today()
    date_from = (today - timedelta(days=days)).isoformat()
    return {
        "today": today.isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),
        "plans": unit_daily_repo.plans_for_year(today.year),
        "entries": unit_daily_repo.recent(kind, date_from),
    }


@router.get("/day")
def day(kind: str = Query(..., pattern="^(purchase|consumption)$"),
        as_of: str = Query(..., description="Ngày 'YYYY-MM-DD'"),
        username: str = Depends(_require)) -> dict:
    """Số liệu MỌI đơn vị cho 1 ngày → lưới xem/sửa cho chuyên viên."""
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    return {
        "as_of": as_of,
        "today": edit_window.today().isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),
        "plans": unit_daily_repo.plans_for_year(_year_of(as_of)),
        "entries": unit_daily_repo.entries_on(kind, as_of),
    }


@router.put("/report")
def upsert(body: UnitDailyEdit, username: str = Depends(_require)) -> dict:
    """Ghi/sửa số liệu 1 đơn vị (trong cửa sổ sửa theo ngày của chuyên viên; admin miễn).

    `create_only=True` (nút Thêm) → 409 nếu (ngày, đơn vị, loại) đã có số (chống ghi trùng).
    """
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    assert_editor_window(username, body.as_of)
    if body.create_only and unit_daily_repo.has_entry(body.kind, body.as_of, body.company):
        raise HTTPException(409, "Đơn vị này đã có số liệu cho ngày này — vui lòng dùng chức năng Sửa.")
    unit_daily_repo.upsert(body.kind, body.as_of, body.company, body.fields, username)
    return {"ok": True}


@router.get("/plan")
def get_plan(year: int = Query(..., ge=2020, le=2100),
             username: str = Depends(_require)) -> dict:
    """Chỉ tiêu kế hoạch thu mua năm cho mọi đơn vị (để tính % + cấu hình)."""
    return {"year": year, "units": member_unit_repo.active_names(),
            "plans": unit_daily_repo.plans_for_year(year)}


@router.put("/plan")
def set_plan(body: PurchasePlanEdit, username: str = Depends(_require)) -> dict:
    """Đặt/xoá chỉ tiêu kế hoạch thu mua năm cho 1 đơn vị."""
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    unit_daily_repo.set_plan(body.year, body.company, body.plan_tonnes, username)
    return {"ok": True}
