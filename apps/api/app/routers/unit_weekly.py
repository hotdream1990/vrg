"""Router báo cáo tuần đơn vị cho CHUYÊN VIÊN có quyền `unit_weekly` — xem/sửa MỌI đơn vị (realtime).

Đơn vị thành viên tự nhập của mình qua `/api/member/weekly-report` (router member_self).
Chuyên viên (editor được cấp quyền / admin) xem toàn bộ + sửa, áp cửa sổ sửa TUẦN của chuyên viên,
và cấu hình chỉ tiêu kế hoạch thu mua năm (để tính % thực hiện).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import edit_window
from app.core.security import assert_editor_week, require_cap
from app.schemas.unit_weekly import PurchasePlanEdit, UnitWeeklyEdit
from app.services import member_unit_repo, unit_weekly_repo

router = APIRouter(prefix="/api/unit-weekly", tags=["unit-weekly"])
_require = require_cap("unit_weekly")


def _monday(d: date) -> str:
    """Ngày Thứ 2 (ISO) của tuần chứa `d` → 'YYYY-MM-DD'."""
    return (d - timedelta(days=d.weekday())).isoformat()


def _year_of(week_key: str) -> int:
    """Năm dương lịch của ngày Thứ 2 — dùng khớp chỉ tiêu kế hoạch năm."""
    return date.fromisoformat(week_key).year


@router.get("/timeline")
def timeline(kind: str = Query(..., pattern="^(purchase|consumption)$"),
             weeks: int = Query(16, ge=1, le=104),
             username: str = Depends(_require)) -> dict:
    """Timeline tổng quát: các bản ghi ĐÃ có số liệu (ẩn tuần trống) trong `weeks` tuần gần nhất."""
    today = edit_window.today()
    week_from = _monday(today - timedelta(weeks=weeks))
    return {
        "today_week": _monday(today),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),
        "plans": unit_weekly_repo.plans_for_year(today.year),
        "entries": unit_weekly_repo.recent(kind, week_from),
    }


@router.get("/week")
def week(kind: str = Query(..., pattern="^(purchase|consumption)$"),
         week_key: str = Query(..., description="Thứ 2 ISO 'YYYY-MM-DD'"),
         username: str = Depends(_require)) -> dict:
    """Số liệu MỌI đơn vị cho 1 tuần → lưới xem/sửa cho chuyên viên."""
    try:
        wk = _monday(date.fromisoformat(week_key))
    except ValueError as exc:
        raise HTTPException(400, "Tuần không hợp lệ (YYYY-MM-DD).") from exc
    return {
        "week_key": wk,
        "today_week": _monday(edit_window.today()),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),
        "plans": unit_weekly_repo.plans_for_year(_year_of(wk)),
        "entries": unit_weekly_repo.week_entries(kind, wk),
    }


@router.put("/report")
def upsert(body: UnitWeeklyEdit, username: str = Depends(_require)) -> dict:
    """Ghi/sửa số liệu 1 đơn vị (trong cửa sổ sửa tuần của chuyên viên; admin miễn).

    `create_only=True` (nút Thêm) → 409 nếu (tuần, đơn vị, loại) đã có số (chống ghi trùng).
    """
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    assert_editor_week(username, body.week_key)
    if body.create_only and unit_weekly_repo.has_entry(body.kind, body.week_key, body.company):
        raise HTTPException(409, "Đơn vị này đã có số liệu cho tuần này — vui lòng dùng chức năng Sửa.")
    unit_weekly_repo.upsert(body.kind, body.week_key, body.company, body.fields, username)
    return {"ok": True}


@router.get("/plan")
def get_plan(year: int = Query(..., ge=2020, le=2100),
             username: str = Depends(_require)) -> dict:
    """Chỉ tiêu kế hoạch thu mua năm cho mọi đơn vị (để tính % + cấu hình)."""
    return {"year": year, "units": member_unit_repo.active_names(),
            "plans": unit_weekly_repo.plans_for_year(year)}


@router.put("/plan")
def set_plan(body: PurchasePlanEdit, username: str = Depends(_require)) -> dict:
    """Đặt/xoá chỉ tiêu kế hoạch thu mua năm cho 1 đơn vị."""
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    unit_weekly_repo.set_plan(body.year, body.company, body.plan_tonnes, username)
    return {"ok": True}
