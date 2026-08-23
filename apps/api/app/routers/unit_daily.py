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
from app.core.feature_flags import require_excel_import
from app.core.market_meta import UNIT_GRADES
from app.core.security import assert_editor_window, require_cap, require_cap_edit
from app.schemas.unit_daily import (
    ExcelImportCommit, PurchasePlanEdit, StockContractEdit, UnitDailyEdit, UnitDailyMove,
)
from app.services import (
    contract_files, member_region_repo, member_unit_repo, unit_daily_contract_consumption,
    unit_daily_excel_io, unit_daily_repo, unit_daily_timeline_totals, unit_period_excel,
    unit_period_report, unit_stock_contract_repo,
)
from app.services.unit_report_query import split_csv

router = APIRouter(prefix="/api/unit-daily", tags=["unit-daily"])
_require = require_cap("unit_daily")            # đọc: mức Xem là đủ
_require_edit = require_cap_edit("unit_daily")  # ghi: bắt buộc mức Sửa
_excel = [Depends(require_excel_import)]        # nhập Excel đang tạm tắt (app/core/feature_flags.py)


def _assert_range(date_from: str, date_to: str) -> None:
    """Chặn khoảng ngày sai định dạng / ngược đầu."""
    try:
        a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    if a > b:
        raise HTTPException(400, "Khoảng ngày không hợp lệ: từ ngày sau đến ngày.")


def resolve_timeline_range(days: int, date_from: str | None, date_to: str | None,
                           today: date) -> tuple[str, str | None]:
    """Khoảng ngày cho timeline: đủ cả date_from+date_to → khoảng TỰ CHỌN (đã kiểm tra);
    thiếu → mặc định `days` ngày gần nhất (không chặn trên). Dùng chung cho router chuyên viên & member."""
    if date_from and date_to:
        _assert_range(date_from, date_to)
        return date_from, date_to
    return (today - timedelta(days=days)).isoformat(), None


def timeline_page(kind: str, d_from: str, d_to: str | None, companies: list[str] | None,
                  page: int, page_size: int) -> dict:
    """Lấy MỘT TRANG timeline (dùng chung cho chuyên viên & đơn vị thành viên).

    Biểu **Thu mua** cố ý lấy TRỌN khoảng: mỗi bản ghi chỉ là mấy con số (cả lịch sử chưa tới
    130 KB) và bảng có dòng "Lũy kế (khoảng đang xem)" — cắt trang sẽ làm lũy kế chỉ còn đúng cho
    trang đang xem, tức là báo sai. Biểu **Tiêu thụ – Tồn kho** nặng gấp ~14 lần (mảng dòng bán +
    danh sách file) nên vẫn cắt trang, bù lại lũy kế của nó do SERVER cộng trên cả khoảng
    (`totals`) — web không có đủ dữ liệu để tự cộng.
    """
    if kind == "purchase":
        res = unit_daily_repo.recent(kind, d_from, companies=companies, date_to=d_to)
        return {"entries": res["entries"], "total": res["total"], "paged": False}
    res = unit_daily_repo.recent(kind, d_from, companies=companies, date_to=d_to,
                                 limit=page_size, offset=(page - 1) * page_size)
    d_close = d_to or edit_window.today().isoformat()
    # Nhóm cột "Tiêu thụ (theo hợp đồng)" chạy SONG SONG với nhóm số cũ để đối chiếu: số cũ là ô
    # `revenue` chốt cứng lúc lưu, số này gom lại từ các lần giao nên luôn khớp Báo cáo tiêu thụ.
    cc = unit_daily_contract_consumption.summarize(d_from, d_close, companies)
    unit_daily_contract_consumption.attach(res["entries"], cc["by_key"])
    totals = unit_daily_timeline_totals.consumption_totals(d_from, d_close, companies)
    return {"entries": res["entries"], "total": res["total"], "paged": True,
            "totals": {**totals, **cc["totals"]}}


def _year_of(as_of: str) -> int:
    """Năm dương lịch của ngày báo cáo — dùng khớp chỉ tiêu kế hoạch năm."""
    return date.fromisoformat(as_of).year


@router.get("/timeline")
def timeline(kind: str = Query(..., pattern="^(purchase|consumption)$"),
             days: int = Query(90, ge=1, le=730),
             date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD' — khoảng tự chọn (kèm date_to)"),
             date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD' — khoảng tự chọn (kèm date_from)"),
             page: int = Query(1, ge=1),
             page_size: int = Query(50, ge=1, le=500),
             username: str = Depends(_require)) -> dict:
    """Timeline tổng quát: các bản ghi ĐÃ có số liệu (ẩn ngày trống).
    Mặc định `days` ngày gần nhất; truyền cả `date_from`+`date_to` → lọc theo khoảng tự chọn.

    Biểu **Tiêu thụ – Tồn kho** cắt trang Ở SERVER (bản ghi mang mảng dòng bán + danh sách file,
    90 ngày đã gần 1 MB). Biểu **Thu mua** cố ý KHÔNG cắt trang: dòng dữ liệu chỉ vài số nên cả
    khoảng cũng rất nhẹ, mà bảng có dòng "Lũy kế (khoảng đang xem)" — cắt trang là lũy kế sai.
    """
    today = edit_window.today()
    d_from, d_to = resolve_timeline_range(days, date_from, date_to, today)
    res = timeline_page(kind, d_from, d_to, None, page, page_size)
    unit_daily_repo.attach_purchase_prices(res["entries"], kind)
    return {
        "today": today.isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),
        "plans": unit_daily_repo.plans_for_year(today.year),
        **res, "page": page, "page_size": page_size,
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
    entries = unit_daily_repo.entries_on(kind, as_of)
    if kind == "consumption":
        # Lưới này dùng CHUNG danh mục cột với bảng theo ngày → phải gắn cả nhóm "theo hợp đồng",
        # nếu không cả nhóm cột hiện "—" và người đọc tưởng ngày đó không bán gì.
        unit_daily_contract_consumption.attach_day(
            entries, as_of, unit_daily_contract_consumption.by_company_day(as_of, as_of))
    return {
        "as_of": as_of,
        "today": edit_window.today().isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": units,
        "plans": unit_daily_repo.plans_for_year(_year_of(as_of)),
        "entries": entries,
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


@router.get("/contracts/history")
def contract_history(company: str | None = Query(None),
                     regions: str | None = Query(None, description="Khu vực, phân cách dấu phẩy"),
                     grades: str | None = Query(None, description="Chủng loại, phân cách dấu phẩy"),
                     status: str = Query("all", pattern="^(all|undelivered|delivered)$"),
                     date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD' (Ngày bắt đầu tồn kho)"),
                     date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD'"),
                     q: str | None = Query(None, max_length=120, description="Tìm theo Số HĐ/PL hoặc Chủng loại"),
                     username: str = Depends(_require)) -> dict:
    """Lịch sử TOÀN BỘ hợp đồng đã ký (kể cả đã giao) — tra cứu lại HĐ đã biến mất khỏi tồn kho ngày."""
    for label, v in (("Từ ngày", date_from), ("Đến ngày", date_to)):
        if v:
            try:
                date.fromisoformat(v)
            except ValueError as exc:
                raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc
    units = member_unit_repo.list_units(include_inactive=False)
    region_of = {u["name"]: u.get("region") for u in units}
    companies = [company] if company else None
    if companies is None and (regs := split_csv(regions)):
        companies = [n for n, r in region_of.items() if (r or "") in set(regs)] or [""]
    contracts = unit_stock_contract_repo.list_contracts(
        companies=companies, status=None if status == "all" else status,
        date_from=date_from, date_to=date_to, q=q, grades=split_csv(grades))
    for c in contracts:
        c["region"] = region_of.get(c["company"])
    contracts.sort(key=lambda c: (c["start_date"] or "", c["id"] or 0), reverse=True)
    return {"units": [u["name"] for u in units], "regions": member_region_repo.active_names(),
            "grades": list(UNIT_GRADES), "contracts": contracts}


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


@router.put("/report/move-date")
def move_date(body: UnitDailyMove, username: str = Depends(_require_edit)) -> dict:
    """Đổi NGÀY của một bản ghi đã nhập (nhập nhầm ngày) — nội dung giữ nguyên.

    Ép cửa sổ sửa cho CẢ ngày cũ lẫn ngày mới: không được kéo số liệu ra/vào vùng đã khoá.
    """
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    assert_editor_window(username, body.as_of)
    assert_editor_window(username, body.to_date)
    try:
        return {"ok": True, **unit_daily_repo.move_day(
            body.kind, body.company, body.as_of, body.to_date, username)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    """Số liệu NĂM (kế hoạch thu mua/tiêu thụ + HĐ dài hạn đã ký) — MỌI đơn vị đang hoạt động.

    Chốt 03/08/2026: bỏ cờ bật/tắt theo đơn vị. Màn này luôn mở cho mọi đơn vị, và CHÍNH ô
    "kế hoạch thu mua" ở đây là công tắc bật màn Thu mua của đơn vị đó.
    """
    return {"year": year, "units": member_unit_repo.active_names(),
            "plans": unit_daily_repo.year_plan(year)}


@router.put("/plan")
def set_plan(body: PurchasePlanEdit, username: str = Depends(_require_edit)) -> dict:
    """Đặt/xoá số liệu năm của 1 đơn vị (chuyên viên có quyền `unit_daily`)."""
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    unit_daily_repo.set_year_plan(body.year, body.company, body.plan_tonnes, body.signed_lt_tonnes,
                                  body.carry_lt_tonnes, body.carry_spot_tonnes,
                                  body.plan_sales_spot_tonnes, body.plan_revenue_ty, username)
    return {"ok": True}


# ── Nhập liệu bằng Excel (tải mẫu · xem trước · ghi) — đang TẠM TẮT, xem feature_flags ──
@router.get("/import/template", dependencies=_excel)
def import_template(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                    username: str = Depends(_require)):
    """Tải file Excel MẪU của 1 loại biểu (có sẵn dropdown đơn vị / danh mục)."""
    data = unit_daily_excel_io.build_template(kind)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mau-nhap-{kind}.xlsx"'})


@router.post("/import/preview", dependencies=_excel)
async def import_preview(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                         file: UploadFile = File(...),
                         username: str = Depends(_require_edit)) -> dict:
    """Đọc file người dùng nộp → trả các dòng + lỗi để XEM TRƯỚC (chưa ghi gì)."""
    try:
        return unit_daily_excel_io.parse_upload(kind, await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import/commit", dependencies=_excel)
def import_commit(body: ExcelImportCommit,
                  username: str = Depends(_require_edit)) -> dict:
    """Ghi các dòng hợp lệ đã xem trước (bỏ qua dòng lỗi)."""
    return unit_daily_excel_io.commit_rows(body.kind, body.rows, username)

