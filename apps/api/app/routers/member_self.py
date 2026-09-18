"""Router SỐ LIỆU CỦA ĐƠN VỊ THÀNH VIÊN — giá mủ, biểu ngày, kế hoạch năm, hợp đồng tồn kho.

Phục vụ hai vai trò gắn đơn vị (`get_unit_user`), cùng phạm vi dữ liệu nhưng khác quyền ghi:
  - `member` (nhập liệu): xem + nhập/sửa số liệu của các đơn vị được gán;
  - `leader` (lãnh đạo đơn vị): CHỈ XEM — mọi method ghi bị chặn ngay ở dependency.
Tham số `member` của các handler là TÀI KHOẢN đang gọi (một trong hai vai trò trên).

Mỗi thao tác ghi phải kèm `company` và server kiểm tra company thuộc danh sách gán của tài khoản
→ không thể đụng đơn vị khác. Chỉ nhập/sửa được HÔM NAY + N ngày gần nhất (server ép); ngày cũ
hơn chỉ để xem.

Phạm vi ĐỌC rộng hơn phạm vi GHI: các màn tra cứu mở thêm những đơn vị đã SÁP NHẬP vào đơn vị được
gán (xem `_scope`), và trả kèm `view_only_units` để web khoá nút sửa cho phần đó.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.core import data_lock, edit_window
from app.core.feature_flags import require_excel_import
from app.core import market_demand_meta as demand_meta
from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_UNIT, UNIT_GRADES
from app.core.security import get_unit_user
from app.core.unit_guard import assert_unit_can_enter
from app.routers.unit_daily import resolve_timeline_range, timeline_page
from app.schemas.market_demand_item import DemandItemIn
from app.schemas.member_self import MemberPriceEdit
from app.schemas.unit_daily import (
    ExcelImportCommit, PurchasePlanEdit, StockContractEdit, UnitDailyEdit, UnitDailyMove,
)
from app.services import (
    contract_files, market_demand_item_repo, member_checklist, member_unit_merge, price_repo,
    unit_daily_excel_io, unit_daily_repo, unit_purchase_price, unit_stock_contract_repo,
)
from app.services import market_demand_item_policy as demand_policy
from app.services.unit_report_query import split_csv

router = APIRouter(prefix="/api/member", tags=["member-self"])
_DEMAND_NOT_FOUND = "Không tìm thấy phiếu nhu cầu này."
_excel = [Depends(require_excel_import)]  # nhập Excel đang tạm tắt (app/core/feature_flags.py)


def _plans_of(units: list[str], year: int) -> dict[str, float]:
    """Chỉ tiêu năm của RIÊNG các đơn vị được gán.

    `plans_for_year` trả kế hoạch của MỌI đơn vị (nguồn dùng chung với màn của Ban). Trả nguyên si
    ra endpoint của đơn vị là đơn vị này đọc được chỉ tiêu của đơn vị kia — lọc ngay tại đây.
    """
    plans = unit_daily_repo.plans_for_year(year)
    return {u: plans[u] for u in units if u in plans}


def _units(member: dict) -> list[str]:
    """Đơn vị tài khoản được NHẬP/SỬA — đúng danh sách được gán."""
    return list(member.get("member_units") or [])


def _scope(member: dict) -> tuple[list[str], list[str]]:
    """(đơn vị HIỆN TRÊN MÀN, đơn vị CHỈ XEM trong số đó) — mở phạm vi ĐỌC theo dòng đời sáp nhập.

    Sáp nhập không đổi tên dữ liệu cũ (bản ghi trước ngày hiệu lực vẫn đứng tên đơn vị cũ) nhưng
    tài khoản thì chuyển hẳn sang đơn vị nhận. Không mở vế đọc này thì số liệu trước sáp nhập biến
    mất khỏi mọi màn của đơn vị nhận — lũy kế thiếu hẳn một mảng (phản ánh 11/09/2026: tài khoản
    Chư Sê không còn thấy phần Mang Yang kỳ 01/01–23/07, dù báo cáo của Ban đã gộp đủ).

    GHI thì KHÔNG mở: `_assert_company` vẫn chỉ nhận đơn vị được gán, nên đơn vị đã sáp nhập chỉ
    xem. Web đọc `view_only_units` để khoá sẵn nút sửa thay vì để người dùng bấm rồi mới báo lỗi.
    """
    own = _units(member)
    view = member_unit_merge.expand(own) or own
    keep = set(own)
    return view, [u for u in view if u not in keep]


def _locked(units: list[str]) -> dict[str, str]:
    """{đơn vị: ngày đã chốt} của riêng các đơn vị này — trả kèm mọi payload có `edit_window_days`
    để màn nhập liệu biết ngày nào đã chốt mà chuyển sang "(đã chốt)" thay vì mời bấm rồi báo lỗi."""
    from app.services import data_lock_repo

    got = data_lock_repo.locked_map()
    return {u: got[u] for u in units if u in got}


def _assert_company(member: dict, company: str, as_of: str | None = None) -> None:
    """Chặn ghi cho đơn vị không được gán cho tài khoản này (và đơn vị đã sáp nhập).

    Sáp nhập đã chuyển tài khoản sang đơn vị mới nên vế 403 thường chặn trước, nhưng nếu quản trị
    gán tay lại đơn vị cũ thì đây là lớp chặn cuối: `as_of` = NGÀY SỐ LIỆU, ngày trước ngày sáp
    nhập vẫn sửa được.
    """
    if company not in _units(member):
        # Đơn vị đã sáp nhập nằm trong phạm vi ĐỌC (`_scope`) nhưng không bao giờ được ghi.
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")
    assert_unit_can_enter(company, as_of, require_known=False)


@router.get("/checklist")
def my_checklist(member: dict = Depends(get_unit_user)) -> dict:
    """Đơn vị còn thiếu gì — hiện ngay trên mọi màn của tài khoản đơn vị (xem `member_checklist`)."""
    return member_checklist.checklist(_units(member))


@router.get("/prices")
def my_prices(days: int = Query(30, ge=1, le=180),
              member: dict = Depends(get_unit_user)) -> dict:
    """Lịch sử giá mủ nước + mủ chén của TỪNG đơn vị được gán (dựng lưới xem/nhập).

    Kèm cả đơn vị đã sáp nhập vào (chỉ xem — `view_only_units`)."""
    units, view_only = _scope(member)
    sheets = {u: price_repo.member_price_history(u, days) for u in units}
    return {"units": units, "view_only_units": view_only, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(edit_window.PURCHASE_KIND),
            "locked_until": _locked(units), "sheets": sheets}


@router.put("/prices")
def upsert_my_price(body: MemberPriceEdit,
                    member: dict = Depends(get_unit_user)) -> dict:
    """Nhập/sửa 1 ô giá (mủ nước hoặc mủ chén) cho 1 đơn vị được gán, trong cửa sổ cho phép.

    Giá 0 = "ngày đó không có giá" → `price_repo` xoá ô giá thay vì lưu số 0 (xem `market_meta`).
    """
    _assert_company(member, body.company, body.as_of)
    # Đơn giá nằm TRÊN biểu Thu mua → cùng cửa sổ với biểu (được nhập trễ hơn các mục khác), nếu
    # không đơn vị lưu được số lượng mà bị chặn lưu giá của cùng một ngày.
    edit_window.assert_editable(body.as_of, edit_window.member_window(edit_window.PURCHASE_KIND))
    # Đơn giá thu mua là MỘT PHẦN của số liệu thu mua đã chốt → khoá theo cùng mốc.
    data_lock.assert_not_locked(body.company, body.as_of)
    # Giá đơn vị TỰ KHAI nằm ở lớp riêng — không đè lên giá chuyên viên đã chốt (xem market_meta).
    # `body.basis` client cũ gửi lên bị BỎ QUA — cơ sở tính độ không còn là lựa chọn (17/08/2026).
    cleared = unit_purchase_price.save(body.company, body.as_of, body.price_type, body.price)
    return {"ok": True, "cleared": cleared}


@router.delete("/prices")
def clear_my_price(
    company: str = Query(...),
    as_of: str = Query(..., description="YYYY-MM-DD"),
    price_type: str = Query(..., description="purchase | purchase_cup"),
    member: dict = Depends(get_unit_user),
) -> dict:
    """Xoá 1 ô giá của 1 đơn vị được gán (trong cửa sổ cho phép)."""
    _assert_company(member, company, as_of)
    if price_type not in PURCHASE_PRICE_UNIT:
        raise HTTPException(400, "Loại giá không hợp lệ.")
    edit_window.assert_editable(as_of, edit_window.member_window(edit_window.PURCHASE_KIND))
    data_lock.assert_not_locked(company, as_of)
    price_repo.delete_record(as_of, PURCHASE_SOURCE_UNIT, company, "", price_type)
    return {"deleted": True}


# ── Nhu cầu thị trường (phiếu theo trường — mỗi phiếu một chủng loại) ──
@router.get("/market-demand/items")
def my_market_demand_items(date_from: str | None = Query(None, description="Từ ngày nhận 'YYYY-MM-DD'"),
                           date_to: str | None = Query(None, description="Đến ngày nhận 'YYYY-MM-DD'"),
                           grade: str | None = Query(None),
                           q: str | None = Query(None, max_length=120),
                           member: dict = Depends(get_unit_user)) -> dict:
    """Phiếu nhu cầu — đơn vị được gán + đơn vị đã sáp nhập vào (chỉ xem), mặc định 90 ngày gần nhất."""
    units, view_only = _scope(member)
    d_from, d_to = demand_policy.date_range(date_from, date_to)
    return {"units": units, "view_only_units": view_only, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(), "grades": list(demand_meta.GRADES),
            "items": market_demand_item_repo.list_items(units, d_from, d_to, grade=grade, q=q)}


def _my_demand_item(member: dict, item_id: int) -> dict:
    """Phiếu có sẵn mà tài khoản được GHI: không có → 404; của đơn vị khác (kể cả đã sáp nhập) → 403."""
    old = market_demand_item_repo.get(item_id)
    if old is None:
        raise HTTPException(404, _DEMAND_NOT_FOUND)
    if old["company"] not in _units(member):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")
    return old


@router.put("/market-demand/items")
def save_my_market_demand_item(body: DemandItemIn, member: dict = Depends(get_unit_user)) -> dict:
    """Thêm/sửa 1 phiếu của đơn vị được gán. Chỉ đổi tình trạng · số HĐ · ngày ký · ghi chú thì
    miễn cửa sổ nhập liệu (kết quả đàm phán đến sau, cửa sổ đơn vị có thể = 0)."""
    item = demand_policy.clean(body.model_dump())
    _assert_company(member, item["company"], item["as_of"])
    old = _my_demand_item(member, item["id"]) if item["id"] else None
    demand_policy.assert_save_fences(member["username"], old, item)
    saved = market_demand_item_repo.save(item, member["username"])
    if saved is None:
        raise HTTPException(404, _DEMAND_NOT_FOUND)
    return {"item": saved}


@router.delete("/market-demand/items/{item_id}")
def delete_my_market_demand_item(item_id: int, member: dict = Depends(get_unit_user)) -> dict:
    """Xoá 1 phiếu nhập nhầm — trong cửa sổ theo ngày nhận của phiếu."""
    old = _my_demand_item(member, item_id)
    demand_policy.assert_delete_fences(member["username"], old)
    if not market_demand_item_repo.delete(item_id, _units(member)):
        raise HTTPException(404, _DEMAND_NOT_FOUND)
    return {"ok": True}


# ── Báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho) ──
@router.get("/daily-report/timeline")
def my_daily_timeline(kind: str = Query(..., pattern="^(purchase|consumption)$"),
                      days: int = Query(90, ge=1, le=730),
                      date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD' — khoảng tự chọn (kèm date_to)"),
                      date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD' — khoảng tự chọn (kèm date_from)"),
                      page: int = Query(1, ge=1),
                      page_size: int = Query(50, ge=1, le=500),
                      member: dict = Depends(get_unit_user)) -> dict:
    """Timeline báo cáo — các đơn vị được gán + đơn vị đã SÁP NHẬP vào (chỉ xem), ẩn ngày trống.
    Mặc định `days` ngày gần nhất; truyền cả `date_from`+`date_to` → lọc theo khoảng tự chọn.
    Cắt trang giống endpoint chuyên viên (xem `unit_daily.timeline`).

    Có phần của đơn vị đã sáp nhập thì dòng "Lũy kế (khoảng đang xem)" mới đủ — trước đây kỳ đầu
    năm của đơn vị cũ rơi ra ngoài, đơn vị nhận đối chiếu với sổ của mình là lệch (xem `_scope`)."""
    units, view_only = _scope(member)
    today = edit_window.today()
    d_from, d_to = resolve_timeline_range(days, date_from, date_to, today)
    res = timeline_page(kind, d_from, d_to, units, page, page_size)
    unit_daily_repo.attach_purchase_prices(res["entries"], kind)
    return {"today": today.isoformat(), "edit_window_days": edit_window.member_window(kind),
            "locked_until": _locked(units),
            "units": units, "view_only_units": view_only, "plans": _plans_of(units, today.year),
            **res, "page": page, "page_size": page_size}


@router.get("/daily-report")
def my_daily(kind: str = Query(..., pattern="^(purchase|consumption)$"),
             as_of: str = Query(..., description="Ngày 'YYYY-MM-DD'"),
             member: dict = Depends(get_unit_user)) -> dict:
    """Số liệu báo cáo cho 1 ngày — đơn vị được gán + đơn vị đã sáp nhập vào (chỉ xem)."""
    units, view_only = _scope(member)
    try:
        year = date.fromisoformat(as_of).year
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    entries = unit_daily_repo.entries_on(kind, as_of)
    return {"as_of": as_of, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(kind), "locked_until": _locked(units),
            "units": units, "view_only_units": view_only,
            "plans": _plans_of(units, year),
            "entries": {u: entries.get(u) for u in units},
            **unit_daily_repo.day_extras(kind, as_of, units)}


# ── Số liệu NĂM (kế hoạch thu mua + HĐ dài hạn đã ký) — nhập 1 lần, cập nhật khi có thay đổi ──
@router.get("/plan")
def my_year_plan(year: int = Query(..., ge=2020, le=2100),
                 member: dict = Depends(get_unit_user)) -> dict:
    """Số liệu năm của CÁC đơn vị được gán — chỉ đơn vị CÓ giao kế hoạch thu mua."""
    # Màn Kế hoạch năm mở cho MỌI đơn vị của tài khoản (chốt 03/08/2026 — bỏ cờ bật/tắt).
    units = _units(member)   # form NHẬP 1 lần → chỉ đơn vị được gán
    return {"year": year, "units": units, "plans": unit_daily_repo.year_plan(year, companies=units)}


@router.put("/plan")
def upsert_my_year_plan(body: PurchasePlanEdit,
                        member: dict = Depends(get_unit_user)) -> dict:
    """Đơn vị tự cập nhật số liệu năm của mình (không giới hạn cửa sổ ngày — số liệu năm)."""
    # Chỉ tiêu NĂM: mốc so là 01/01 năm đó — sáp nhập giữa năm vẫn sửa được kế hoạch năm ấy.
    _assert_company(member, body.company, f"{body.year}-01-01")
    unit_daily_repo.set_year_plan(body.year, body.company, body.plan_tonnes, body.signed_lt_tonnes,
                                  body.carry_lt_tonnes, body.carry_spot_tonnes,
                                  body.plan_sales_spot_tonnes, body.plan_revenue_ty, member.get("username"))
    return {"ok": True}


# ── Tồn kho ĐÃ KÝ HỢP ĐỒNG của CÁC đơn vị được gán — nhập 1 lần, sau chỉ điền ngày giao ──
@router.get("/stock-contracts")
def my_stock_contracts(as_of: str | None = Query(None, description="Chỉ HĐ đang tồn ngày này"),
                       member: dict = Depends(get_unit_user)) -> dict:
    """Hợp đồng đã ký của các đơn vị được gán + đơn vị đã sáp nhập vào (kèm cả HĐ đã giao)."""
    if as_of:
        try:
            date.fromisoformat(as_of)
        except ValueError as exc:
            raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    units, _ = _scope(member)
    return {"as_of": as_of,
            "contracts": unit_stock_contract_repo.list_contracts(companies=units, as_of=as_of)}


@router.get("/stock-contracts/history")
def my_stock_contract_history(status: str = Query("all", pattern="^(all|undelivered|delivered)$"),
                              date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD'"),
                              date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD'"),
                              grades: str | None = Query(None, description="Chủng loại, phân cách dấu phẩy"),
                              q: str | None = Query(None, max_length=120),
                              member: dict = Depends(get_unit_user)) -> dict:
    """Lịch sử TOÀN BỘ hợp đồng đã ký — đơn vị được gán + đơn vị đã sáp nhập vào (kể cả đã giao)."""
    for label, v in (("Từ ngày", date_from), ("Đến ngày", date_to)):
        if v:
            try:
                date.fromisoformat(v)
            except ValueError as exc:
                raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc
    units, view_only = _scope(member)
    contracts = unit_stock_contract_repo.list_contracts(
        companies=units, status=None if status == "all" else status,
        date_from=date_from, date_to=date_to, q=q, grades=split_csv(grades))
    contracts.sort(key=lambda c: (c["start_date"] or "", c["id"] or 0), reverse=True)
    return {"units": units, "view_only_units": view_only, "grades": list(UNIT_GRADES),
            "contracts": contracts}


@router.put("/stock-contracts")
def save_my_stock_contract(body: StockContractEdit,
                           member: dict = Depends(get_unit_user)) -> dict:
    """Đơn vị thêm HĐ mới hoặc cập nhật NGÀY GIAO khi đã xuất kho."""
    _assert_company(member, body.company, body.start_date)
    # Khoá theo CẢ ngày đang lưu lẫn ngày gửi lên: hợp đồng này nằm trong chỉ tiêu tồn kho đã chốt.
    old = unit_stock_contract_repo.get(body.id) if body.id else None
    data_lock.assert_not_locked(
        body.company, body.start_date, body.delivered_date,
        (old or {}).get("start_date"), (old or {}).get("delivered_date"))
    try:
        return {"contract": unit_stock_contract_repo.save(
            body.model_dump(), body.company, member.get("username"))}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/stock-contracts/{contract_id}")
def delete_my_stock_contract(contract_id: int,
                             member: dict = Depends(get_unit_user)) -> dict:
    """Xoá 1 hợp đồng của đơn vị mình (nhập nhầm)."""
    old = unit_stock_contract_repo.get(contract_id) or {}
    if old.get("company"):
        data_lock.assert_not_locked(old["company"], old.get("start_date"), old.get("delivered_date"))
    if not unit_stock_contract_repo.delete(contract_id, _units(member)):
        raise HTTPException(404, "Không tìm thấy hợp đồng này.")
    return {"ok": True}


@router.get("/daily-report/prev-stock")
def my_prev_stock(company: str = Query(...),
                  before: str = Query(..., description="Ngày 'YYYY-MM-DD'"),
                  member: dict = Depends(get_unit_user)) -> dict:
    """Tồn kho ngày gần nhất trước `before` của 1 đơn vị được gán (nút 'Lấy tồn ngày trước')."""
    _assert_company(member, company)
    try:
        date.fromisoformat(before)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    got = unit_daily_repo.prev_stock(company, before)
    return {"found": got is not None, **(got or {})}


@router.put("/daily-report")
def upsert_my_daily(body: UnitDailyEdit,
                    member: dict = Depends(get_unit_user)) -> dict:
    """Ghi/sửa số liệu 1 đơn vị được gán cho 1 ngày, trong cửa sổ cho phép. create_only → chống ghi trùng."""
    _assert_company(member, body.company, body.as_of)
    edit_window.assert_editable(body.as_of, edit_window.member_window(body.kind))
    data_lock.assert_not_locked(body.company, body.as_of)
    if body.create_only and unit_daily_repo.has_entry(body.kind, body.as_of, body.company):
        raise HTTPException(409, "Đơn vị này đã có số liệu cho ngày này — vui lòng dùng chức năng Sửa.")
    unit_daily_repo.upsert(body.kind, body.as_of, body.company, body.fields, member.get("username"))
    return {"ok": True}


@router.put("/daily-report/move-date")
def move_my_daily_date(body: UnitDailyMove,
                       member: dict = Depends(get_unit_user)) -> dict:
    """Đổi NGÀY của bản ghi đã nhập (nhập nhầm ngày) — nội dung giữ nguyên.

    Ép cửa sổ sửa cho CẢ ngày cũ lẫn ngày mới: không được kéo số liệu ra/vào vùng đã khoá.
    """
    # Ngày ĐÍCH mới là ngày số liệu sẽ nằm sau khi dời.
    _assert_company(member, body.company, body.to_date)
    edit_window.assert_editable(body.as_of, edit_window.member_window(body.kind))
    edit_window.assert_editable(body.to_date, edit_window.member_window(body.kind))
    data_lock.assert_not_locked(body.company, body.as_of, body.to_date)
    try:
        return {"ok": True, **unit_daily_repo.move_day(
            body.kind, body.company, body.as_of, body.to_date, member.get("username"))}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/daily-report/contract-file")
def upload_my_contract_file(file: UploadFile, member: dict = Depends(get_unit_user)) -> dict:
    """Upload file Hợp đồng (PDF/ảnh) cho tồn kho đã có HĐ — trả tên file lưu để gắn vào dòng."""
    return contract_files.save(file)


@router.get("/daily-report/contract-file/{name}")
def get_my_contract_file(name: str, member: dict = Depends(get_unit_user)):
    """Tải file Hợp đồng đã upload (tên lưu uuid)."""
    return FileResponse(str(contract_files.path_for(name)))


# ── Nhập liệu bằng Excel — CHỈ các đơn vị được gán cho tài khoản (đang TẠM TẮT, xem feature_flags) ──
@router.get("/import/template", dependencies=_excel)
def my_import_template(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                       member: dict = Depends(get_unit_user)):
    """Tải file Excel MẪU — tài khoản 1 đơn vị thì mẫu bỏ luôn cột 'Đơn vị' (tự gán khi nhập)."""
    data = unit_daily_excel_io.build_template(kind, allowed_units=_units(member))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mau-nhap-{kind}.xlsx"'})


@router.post("/import/preview", dependencies=_excel)
async def my_import_preview(kind: str = Query(..., pattern="^(purchase|sales|stock|plan)$"),
                            file: UploadFile = File(...),
                            member: dict = Depends(get_unit_user)) -> dict:
    """Xem trước file nộp — dòng của đơn vị khác bị đánh dấu lỗi."""
    try:
        return unit_daily_excel_io.parse_upload(kind, await file.read(),
                                                allowed_units=_units(member))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import/commit", dependencies=_excel)
def my_import_commit(body: ExcelImportCommit,
                     member: dict = Depends(get_unit_user)) -> dict:
    """Ghi các dòng hợp lệ — server ép lại đơn vị thuộc quyền tài khoản."""
    # File Excel là đường ghi thứ hai vào đúng những bảng đã chốt → phải qua cùng hàng rào.
    for r in body.rows:
        if r.get("company") and r.get("as_of"):
            data_lock.assert_not_locked(str(r["company"]), str(r["as_of"]))
    return unit_daily_excel_io.commit_rows(body.kind, body.rows, member.get("username"),
                                           allowed_units=_units(member))

