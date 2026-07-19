"""Router tài khoản ĐƠN VỊ THÀNH VIÊN — tự xem/nhập giá mủ nước + mủ chén của CÁC đơn vị được gán.

Gác bằng `get_current_member` (role=member, đã gán ≥1 đơn vị). Mỗi thao tác ghi phải kèm `company`
và server kiểm tra company thuộc danh sách gán của tài khoản → không thể đụng đơn vị khác. Chỉ
nhập/sửa được HÔM NAY + N ngày gần nhất (server ép); ngày cũ hơn chỉ để xem.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.core import edit_window
from app.core.security import get_current_member
from app.schemas.market_demand import MarketDemandEdit
from app.schemas.member_self import MemberPriceEdit
from app.schemas.unit_daily import ExcelImportCommit, PurchasePlanEdit, UnitDailyEdit
from app.services import (
    contract_files, market_demand_repo, price_repo, unit_daily_excel_io, unit_daily_repo,
)

router = APIRouter(prefix="/api/member", tags=["member-self"])

_UNIT = {"purchase": "đồng/độ TSC", "purchase_cup": "đồng/độ TSC"}


def _assert_company(member: dict, company: str) -> None:
    """Chặn ghi cho đơn vị không được gán cho tài khoản này."""
    if company not in (member.get("member_units") or []):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


@router.get("/prices")
def my_prices(days: int = Query(30, ge=1, le=180),
              member: dict = Depends(get_current_member)) -> dict:
    """Lịch sử giá mủ nước + mủ chén của TỪNG đơn vị được gán (dựng lưới xem/nhập)."""
    units = list(member["member_units"])
    sheets = {u: price_repo.member_price_history(u, days) for u in units}
    return {"units": units, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(), "sheets": sheets}


@router.put("/prices")
def upsert_my_price(body: MemberPriceEdit,
                    member: dict = Depends(get_current_member)) -> dict:
    """Nhập/sửa 1 ô giá (mủ nước hoặc mủ chén) cho 1 đơn vị được gán, trong cửa sổ cho phép."""
    _assert_company(member, body.company)
    edit_window.assert_editable(body.as_of, edit_window.member_window())
    price_repo.upsert_record({
        "as_of": body.as_of, "source": "vrg", "grade": body.company, "contract": "",
        "price_type": body.price_type, "price": float(body.price),
        "currency": "VND", "unit": _UNIT[body.price_type],
    })
    return {"ok": True}


@router.delete("/prices")
def clear_my_price(
    company: str = Query(...),
    as_of: str = Query(..., description="YYYY-MM-DD"),
    price_type: str = Query(..., description="purchase | purchase_cup"),
    member: dict = Depends(get_current_member),
) -> dict:
    """Xoá 1 ô giá của 1 đơn vị được gán (trong cửa sổ cho phép)."""
    _assert_company(member, company)
    if price_type not in _UNIT:
        raise HTTPException(400, "Loại giá không hợp lệ.")
    edit_window.assert_editable(as_of, edit_window.member_window())
    price_repo.delete_record(as_of, "vrg", company, "", price_type)
    return {"deleted": True}


# ── Nhu cầu thị trường (free text theo đơn vị / ngày) ──
@router.get("/market-demand/timeline")
def my_market_demand_timeline(days: int = Query(90, ge=1, le=730),
                              member: dict = Depends(get_current_member)) -> dict:
    """Timeline nhu cầu — CHỈ các đơn vị được gán của tài khoản (đa đơn vị), ẩn ngày trống."""
    units = list(member["member_units"])
    date_from = (edit_window.today() - timedelta(days=days)).isoformat()
    return {"units": units, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(),
            "entries": market_demand_repo.recent(date_from, companies=units)}


@router.get("/market-demand")
def my_market_demand(as_of: str = Query(..., description="YYYY-MM-DD"),
                     member: dict = Depends(get_current_member)) -> dict:
    """Nhu cầu thị trường của CÁC đơn vị được gán cho 1 ngày (chỉ đơn vị của tài khoản)."""
    units = list(member["member_units"])
    entries = market_demand_repo.entries_on(as_of)
    return {"units": units, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(),
            "entries": {u: entries.get(u, "") for u in units}}


@router.put("/market-demand")
def upsert_my_market_demand(body: MarketDemandEdit,
                            member: dict = Depends(get_current_member)) -> dict:
    """Ghi/sửa nhu cầu 1 đơn vị được gán, trong cửa sổ cho phép. create_only → chống ghi trùng."""
    _assert_company(member, body.company)
    edit_window.assert_editable(body.as_of, edit_window.member_window())
    if body.create_only and market_demand_repo.entries_on(body.as_of).get(body.company, "").strip():
        raise HTTPException(409, "Đơn vị này đã có nhu cầu cho ngày này — vui lòng dùng chức năng Sửa.")
    market_demand_repo.upsert(body.as_of, body.company, body.content.strip(), member.get("username"))
    return {"ok": True}


# ── Báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho) ──
@router.get("/daily-report/timeline")
def my_daily_timeline(kind: str = Query(..., pattern="^(purchase|consumption)$"),
                      days: int = Query(90, ge=1, le=730),
                      member: dict = Depends(get_current_member)) -> dict:
    """Timeline báo cáo — CHỈ các đơn vị được gán (đa đơn vị), ẩn ngày trống."""
    units = list(member["member_units"])
    today = edit_window.today()
    date_from = (today - timedelta(days=days)).isoformat()
    entries = unit_daily_repo.recent(kind, date_from, companies=units)
    unit_daily_repo.attach_purchase_prices(entries, kind)
    return {"today": today.isoformat(), "edit_window_days": edit_window.member_window(),
            "units": units, "plans": unit_daily_repo.plans_for_year(today.year),
            "entries": entries}


@router.get("/daily-report")
def my_daily(kind: str = Query(..., pattern="^(purchase|consumption)$"),
             as_of: str = Query(..., description="Ngày 'YYYY-MM-DD'"),
             member: dict = Depends(get_current_member)) -> dict:
    """Số liệu báo cáo của CÁC đơn vị được gán cho 1 ngày."""
    units = list(member["member_units"])
    try:
        year = date.fromisoformat(as_of).year
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    entries = unit_daily_repo.entries_on(kind, as_of)
    return {"as_of": as_of, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(), "units": units,
            "plans": unit_daily_repo.plans_for_year(year),
            "entries": {u: entries.get(u) for u in units},
            **unit_daily_repo.day_extras(kind, as_of, units)}


# ── Số liệu NĂM (kế hoạch thu mua + HĐ dài hạn đã ký) — nhập 1 lần, cập nhật khi có thay đổi ──
@router.get("/plan")
def my_year_plan(year: int = Query(..., ge=2020, le=2100),
                 member: dict = Depends(get_current_member)) -> dict:
    """Số liệu năm của CÁC đơn vị được gán cho tài khoản này."""
    units = list(member["member_units"])
    return {"year": year, "units": units, "plans": unit_daily_repo.year_plan(year, companies=units)}


@router.put("/plan")
def upsert_my_year_plan(body: PurchasePlanEdit,
                        member: dict = Depends(get_current_member)) -> dict:
    """Đơn vị tự cập nhật số liệu năm của mình (không giới hạn cửa sổ ngày — số liệu năm)."""
    _assert_company(member, body.company)
    unit_daily_repo.set_year_plan(body.year, body.company, body.plan_tonnes, body.signed_lt_tonnes,
                                  body.carry_lt_tonnes, body.carry_spot_tonnes, member.get("username"))
    return {"ok": True}


@router.put("/daily-report")
def upsert_my_daily(body: UnitDailyEdit,
                    member: dict = Depends(get_current_member)) -> dict:
    """Ghi/sửa số liệu 1 đơn vị được gán cho 1 ngày, trong cửa sổ cho phép. create_only → chống ghi trùng."""
    _assert_company(member, body.company)
    edit_window.assert_editable(body.as_of, edit_window.member_window())
    if body.create_only and unit_daily_repo.has_entry(body.kind, body.as_of, body.company):
        raise HTTPException(409, "Đơn vị này đã có số liệu cho ngày này — vui lòng dùng chức năng Sửa.")
    unit_daily_repo.upsert(body.kind, body.as_of, body.company, body.fields, member.get("username"))
    return {"ok": True}


@router.post("/daily-report/contract-file")
def upload_my_contract_file(file: UploadFile, member: dict = Depends(get_current_member)) -> dict:
    """Upload file Hợp đồng (PDF/ảnh) cho tồn kho đã có HĐ — trả tên file lưu để gắn vào dòng."""
    return contract_files.save(file)


@router.get("/daily-report/contract-file/{name}")
def get_my_contract_file(name: str, member: dict = Depends(get_current_member)):
    """Tải file Hợp đồng đã upload (tên lưu uuid)."""
    return FileResponse(str(contract_files.path_for(name)))


# ── Nhập liệu bằng Excel — CHỈ các đơn vị được gán cho tài khoản ──
@router.get("/import/template")
def my_import_template(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                       member: dict = Depends(get_current_member)):
    """Tải file Excel MẪU."""
    data = unit_daily_excel_io.build_template(kind)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mau-nhap-{kind}.xlsx"'})


@router.post("/import/preview")
async def my_import_preview(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                            file: UploadFile = File(...),
                            member: dict = Depends(get_current_member)) -> dict:
    """Xem trước file nộp — dòng của đơn vị khác bị đánh dấu lỗi."""
    try:
        return unit_daily_excel_io.parse_upload(kind, await file.read(),
                                                allowed_units=list(member["member_units"]))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import/commit")
def my_import_commit(body: ExcelImportCommit,
                     member: dict = Depends(get_current_member)) -> dict:
    """Ghi các dòng hợp lệ — server ép lại đơn vị thuộc quyền tài khoản."""
    return unit_daily_excel_io.commit_rows(body.kind, body.rows, member.get("username"),
                                           allowed_units=list(member["member_units"]))

