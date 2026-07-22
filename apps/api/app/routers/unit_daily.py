"""Router báo cáo tiêu thụ–tồn kho theo NGÀY cho CHUYÊN VIÊN có quyền `unit_daily` — xem/sửa MỌI đơn vị (realtime).

Đơn vị thành viên tự nhập của mình qua `/api/member/daily-report` (router member_self).
Chuyên viên (editor được cấp quyền / admin) xem toàn bộ + sửa, áp cửa sổ sửa theo ngày của chuyên viên,
và cấu hình chỉ tiêu kế hoạch thu mua năm (để tính % thực hiện).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.core import edit_window
from app.core.security import assert_editor_window, require_cap, require_cap_edit
from app.schemas.unit_daily import (
    ExcelImportCommit, PurchasePlanEdit, StockContractEdit, UnitDailyEdit,
)
from app.services import (
    contract_files, member_unit_repo, unit_daily_excel_io, unit_daily_repo,
    unit_period_excel, unit_period_report, unit_stock_contract_repo,
)

router = APIRouter(prefix="/api/unit-daily", tags=["unit-daily"])
_require = require_cap("unit_daily")            # đọc: mức Xem là đủ
_require_edit = require_cap_edit("unit_daily")  # ghi: bắt buộc mức Sửa


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


# ── Tồn kho ĐÃ KÝ HỢP ĐỒNG — bản ghi có vòng đời riêng, KHÔNG nhập lại mỗi ngày ──
@router.get("/stock-contracts")
def list_stock_contracts(as_of: str | None = Query(None, description="Chỉ HĐ đang tồn ngày này"),
                         company: str | None = Query(None),
                         username: str = Depends(_require)) -> dict:
    """Hợp đồng đã ký: `as_of` → chỉ các HĐ còn nằm trong tồn kho ngày đó; không có → toàn bộ."""
    if as_of:
        try:
            date.fromisoformat(as_of)
        except ValueError as exc:
            raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    companies = [company] if company else None
    return {"as_of": as_of,
            "contracts": unit_stock_contract_repo.list_contracts(companies=companies, as_of=as_of)}


@router.put("/stock-contracts")
def save_stock_contract(body: StockContractEdit, username: str = Depends(_require_edit)) -> dict:
    """Thêm mới / cập nhật 1 hợp đồng (kể cả điền NGÀY GIAO khi đã xuất kho)."""
    try:
        return {"contract": unit_stock_contract_repo.save(
            body.model_dump(), body.company, username)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/stock-contracts/{contract_id}")
def delete_stock_contract(contract_id: int, username: str = Depends(_require_edit)) -> dict:
    """Xoá 1 hợp đồng (nhập nhầm)."""
    if not unit_stock_contract_repo.delete(contract_id, None):
        raise HTTPException(404, "Không tìm thấy hợp đồng này.")
    return {"ok": True}


@router.get("/prev-stock")
def prev_stock(company: str = Query(...),
               before: str = Query(..., description="Ngày 'YYYY-MM-DD' — lấy tồn kho TRƯỚC ngày này"),
               username: str = Depends(_require)) -> dict:
    """Tồn kho của ngày gần nhất trước `before` (nút 'Lấy tồn ngày trước'). Không có → found=false."""
    try:
        date.fromisoformat(before)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    got = unit_daily_repo.prev_stock(company, before)
    return {"found": got is not None, **(got or {})}


@router.put("/report")
def upsert(body: UnitDailyEdit, username: str = Depends(_require_edit)) -> dict:
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
def upload_contract_file(file: UploadFile, username: str = Depends(_require_edit)) -> dict:
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
    """Số liệu NĂM (kế hoạch thu mua + HĐ dài hạn đã ký) — chỉ đơn vị CÓ giao kế hoạch thu mua."""
    return {"year": year, "units": member_unit_repo.plan_names(),
            "plans": unit_daily_repo.year_plan(year)}


@router.put("/plan")
def set_plan(body: PurchasePlanEdit, username: str = Depends(_require_edit)) -> dict:
    """Đặt/xoá số liệu năm của 1 đơn vị (chuyên viên có quyền `unit_daily`)."""
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    unit_daily_repo.set_year_plan(body.year, body.company, body.plan_tonnes, body.signed_lt_tonnes,
                                  body.carry_lt_tonnes, body.carry_spot_tonnes, username)
    return {"ok": True}


# ── Nhập liệu bằng Excel (tải mẫu · xem trước · ghi) ──
@router.get("/import/template")
def import_template(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                    username: str = Depends(_require)):
    """Tải file Excel MẪU của 1 loại biểu (có sẵn dropdown đơn vị / danh mục)."""
    data = unit_daily_excel_io.build_template(kind)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mau-nhap-{kind}.xlsx"'})


@router.post("/import/preview")
async def import_preview(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                         file: UploadFile = File(...),
                         username: str = Depends(_require_edit)) -> dict:
    """Đọc file người dùng nộp → trả các dòng + lỗi để XEM TRƯỚC (chưa ghi gì)."""
    try:
        return unit_daily_excel_io.parse_upload(kind, await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import/commit")
def import_commit(body: ExcelImportCommit,
                  username: str = Depends(_require_edit)) -> dict:
    """Ghi các dòng hợp lệ đã xem trước (bỏ qua dòng lỗi)."""
    return unit_daily_excel_io.commit_rows(body.kind, body.rows, username)

