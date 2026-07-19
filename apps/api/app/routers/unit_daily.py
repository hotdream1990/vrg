"""Router báo cáo tiêu thụ–tồn kho theo NGÀY cho CHUYÊN VIÊN có quyền `unit_daily` — xem/sửa MỌI đơn vị (realtime).

Đơn vị thành viên tự nhập của mình qua `/api/member/daily-report` (router member_self).
Chuyên viên (editor được cấp quyền / admin) xem toàn bộ + sửa, áp cửa sổ sửa theo ngày của chuyên viên,
và cấu hình chỉ tiêu kế hoạch thu mua năm (để tính % thực hiện).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.core import edit_window
from app.core.security import assert_editor_window, require_cap
from app.schemas.unit_daily import PurchasePlanEdit, UnitDailyEdit
from app.services import (
    contract_files, member_unit_repo, unit_daily_repo, unit_period_excel, unit_period_report,
)

router = APIRouter(prefix="/api/unit-daily", tags=["unit-daily"])
_require = require_cap("unit_daily")


def _assert_range(date_from: str, date_to: str) -> None:
    """Chặn khoảng ngày sai định dạng / ngược đầu."""
    try:
        a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    if a > b:
        raise HTTPException(400, "Khoảng ngày không hợp lệ: từ ngày sau đến ngày.")


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
    entries = unit_daily_repo.recent(kind, date_from)
    unit_daily_repo.attach_purchase_prices(entries, kind)
    return {
        "today": today.isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),
        "plans": unit_daily_repo.plans_for_year(today.year),
        "entries": entries,
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
    units = member_unit_repo.active_names()
    return {
        "as_of": as_of,
        "today": edit_window.today().isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": units,
        "plans": unit_daily_repo.plans_for_year(_year_of(as_of)),
        "entries": unit_daily_repo.entries_on(kind, as_of),
        **unit_daily_repo.day_extras(kind, as_of, units),
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


@router.post("/contract-file")
def upload_contract_file(file: UploadFile, username: str = Depends(_require)) -> dict:
    """Upload file Hợp đồng (PDF/ảnh) cho tồn kho đã có HĐ — trả tên file lưu để gắn vào dòng."""
    return contract_files.save(file)


@router.get("/contract-file/{name}")
def get_contract_file(name: str, username: str = Depends(_require)):
    """Tải file Hợp đồng đã upload (tên lưu uuid)."""
    return FileResponse(str(contract_files.path_for(name)))


@router.get("/period-report")
def period_report(kind: str = Query(..., pattern="^(purchase|consumption)$"),
                  date_from: str = Query(..., description="Từ ngày 'YYYY-MM-DD'"),
                  date_to: str = Query(..., description="Đến ngày 'YYYY-MM-DD'"),
                  username: str = Depends(_require)) -> dict:
    """Báo cáo tổng hợp theo kỳ (tuần/tháng/năm/khoảng tự chọn) — MỌI đơn vị."""
    _assert_range(date_from, date_to)
    return unit_period_report.period_report(kind, date_from, date_to)


def _xlsx_response(rep: dict, kind: str, date_from: str, date_to: str) -> Response:
    """Đóng gói .xlsx kèm tên file theo loại biểu + kỳ báo cáo."""
    data = unit_period_excel.build_period_xlsx(rep)
    slug = "thu-mua" if kind == "purchase" else "tieu-thu-ton-kho"
    name = f"bao-cao-{slug}-{date_from}-den-{date_to}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )



@router.get("/period-report.xlsx")
def period_report_xlsx(kind: str = Query(..., pattern="^(purchase|consumption)$"),
                       date_from: str = Query(...), date_to: str = Query(...),
                       username: str = Depends(_require)):
    """Tải báo cáo kỳ dạng Excel (bám mẫu Biểu (1)/(2)) — MỌI đơn vị."""
    _assert_range(date_from, date_to)
    rep = unit_period_report.period_report(kind, date_from, date_to)
    return _xlsx_response(rep, kind, date_from, date_to)


@router.get("/plan")
def get_plan(year: int = Query(..., ge=2020, le=2100),
             username: str = Depends(_require)) -> dict:
    """Số liệu NĂM (kế hoạch thu mua + HĐ dài hạn đã ký) của MỌI đơn vị."""
    return {"year": year, "units": member_unit_repo.active_names(),
            "plans": unit_daily_repo.year_plan(year)}


@router.put("/plan")
def set_plan(body: PurchasePlanEdit, username: str = Depends(_require)) -> dict:
    """Đặt/xoá số liệu năm của 1 đơn vị (chuyên viên có quyền `unit_daily`)."""
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    unit_daily_repo.set_year_plan(body.year, body.company, body.plan_tonnes, body.signed_lt_tonnes,
                                  body.carry_lt_tonnes, body.carry_spot_tonnes, username)
    return {"ok": True}
