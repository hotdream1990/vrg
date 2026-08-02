"""Router HỢP ĐỒNG BÁN HÀNG 2 CẤP + số TIÊU THỤ / KHỐI 3 tính ra từ hợp đồng.

Dùng chung cho đơn vị thành viên và chuyên viên (`cap_or_member_scope`): đơn vị chỉ đụng được
hợp đồng của mình, chuyên viên có quyền `sales_contract` thấy mọi đơn vị.

KHÔNG áp cửa sổ nhập liệu N ngày ở đây — giống hợp đồng tồn kho cũ: ngày ký / ngày giao của một
hợp đồng hoàn toàn có thể nằm xa trong quá khứ, chặn theo cửa sổ sẽ khoá nhập hợp đồng cũ.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile

from app.core.market_meta import (
    CONTRACT_TYPES,
    DELIVERY_TYPES,
    DRY_REQUIRED_GRADES,
    SALE_CHANNELS,
    SALE_CURRENCIES,
    SALE_GRADES,
)
from app.core.permissions import LEVEL_EDIT
from app.core.security import cap_or_member_scope
from app.schemas.sales_contract import ContractIn
from app.services import (
    contract_files,
    customer_repo,
    member_unit_repo,
    sales_contract_repo,
    sales_contract_report,
    unit_analytics_excel,
)

router = APIRouter(prefix="/api/sales-contracts", tags=["sales-contracts"])

Scope = Annotated[tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract"))]
EditScope = Annotated[
    tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract", LEVEL_EDIT))]


def _assert_company(companies: list[str] | None, company: str) -> None:
    if companies is not None and company not in companies:
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _check_date(value: str | None, label: str) -> None:
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


@router.get("/meta")
def meta(scope: Scope) -> dict:
    """Danh mục dùng cho form: đơn vị · chủng loại · hình thức · loại giao · loại tiền · khách hàng."""
    _, companies = scope
    units = member_unit_repo.list_units(include_inactive=False)
    mine = [u["name"] for u in units] if companies is None else list(companies)
    return {
        "units": mine,
        # Nội tệ của từng đơn vị — form chỉ cho chọn VND · USD · nội tệ CỦA ĐƠN VỊ ĐÓ (chốt Q10:
        # trong nước bán VND, thêm USD khi xuất khẩu; nước ngoài mới có thêm LAK/KHR).
        "unit_currency": {u["name"]: (u.get("currency") or "VND") for u in units},
        "all_units": [u["name"] for u in units],
        # Đơn vị NHẬN khi tiêu thụ nội bộ — chỉ trong NHÓM công ty mẹ–con. Đơn vị không có tên ở đây
        # là đứng một mình → form ẩn luôn hình thức "Tiêu thụ nội bộ".
        "internal_targets": member_unit_repo.internal_targets(),
        "grades": list(SALE_GRADES),
        "dry_required": sorted(DRY_REQUIRED_GRADES),
        "channels": SALE_CHANNELS,
        "delivery_types": DELIVERY_TYPES,
        "contract_types": CONTRACT_TYPES,
        "currencies": list(SALE_CURRENCIES),
        "customers": customer_repo.list_customers(companies, include_inactive=False),
    }


@router.get("")
def list_contracts(scope: Scope, company: str | None = Query(None),
                   customer_id: int | None = Query(None),
                   status: str = Query("all", pattern="^(all|open|done)$"),
                   date_from: str | None = Query(None, description="Ngày ký từ 'YYYY-MM-DD'"),
                   date_to: str | None = Query(None, description="Ngày ký đến 'YYYY-MM-DD'"),
                   q: str | None = Query(None, max_length=120)) -> dict:
    """Danh sách HỢP ĐỒNG MẸ kèm tiến độ giao. Mở một hợp đồng để xem/thêm phụ lục."""
    _, companies = scope
    _check_date(date_from, "Từ ngày")
    _check_date(date_to, "Đến ngày")
    if company:
        _assert_company(companies, company)
        companies = [company]
    rows = sales_contract_report.parents_with_progress(
        companies, customer_id=customer_id, status=None if status == "all" else status,
        q=q, date_from=date_from, date_to=date_to)
    names = customer_repo.names_by_id(companies)
    for r in rows:
        r["customer_name"] = names.get(r.get("customer_id") or 0)
    return {"contracts": rows}


def _consumption(scope_companies: list[str] | None, date_from: str, date_to: str,
                 company: str | None, customer_id: int | None) -> dict:
    """Phần dùng chung của endpoint JSON và endpoint xuất Excel (tránh lệch số giữa 2 nơi)."""
    _check_date(date_from, "Từ ngày")
    _check_date(date_to, "Đến ngày")
    companies = scope_companies
    if company:
        _assert_company(companies, company)
        companies = [company]
    return {
        "date_from": date_from, "date_to": date_to,
        "by_company": sales_contract_report.consumption(date_from, date_to, companies, customer_id),
        "undelivered": sales_contract_report.undelivered_on(date_to, companies),
        "customers": {str(c["id"]): c["name"] for c in customer_repo.list_customers(companies)},
    }


@router.get("/consumption")
def consumption(scope: Scope, date_from: str = Query(...), date_to: str = Query(...),
                company: str | None = Query(None),
                customer_id: int | None = Query(None)) -> dict:
    """TIÊU THỤ trong kỳ — tổng hợp từ các lần giao, KHÔNG còn ô nhập tay."""
    _, companies = scope
    return _consumption(companies, date_from, date_to, company, customer_id)


_XLSX_COLS: list[tuple[str, str, str]] = [
    ("deliveries", "Số lần giao", "lần"),
    ("qty", "Sản lượng tiêu thụ", "tấn"),
    ("qty_dry", "Quy khô", "tấn"),
    ("qty_export", SALE_CHANNELS["export"], "tấn"),
    ("qty_domestic", SALE_CHANNELS["domestic"], "tấn"),
    ("qty_internal", SALE_CHANNELS["internal"], "tấn"),
    ("revenue_ty", "Doanh thu", "tỷ đồng"),
    ("cost", "Chi phí dòng bán", "triệu đồng"),
    ("remaining", "Đã ký HĐ chưa giao (cuối kỳ)", "tấn"),
]


@router.get("/consumption.xlsx")
def consumption_xlsx(scope: Scope, date_from: str = Query(...), date_to: str = Query(...),
                     company: str | None = Query(None),
                     customer_id: int | None = Query(None)):
    """Xuất Excel bảng Báo cáo tiêu thụ — dùng CHUNG số liệu với bảng trên web."""
    _, companies = scope
    rep = _consumption(companies, date_from, date_to, company, customer_id)
    rows, totals = [], {k: 0.0 for k, _, _ in _XLSX_COLS}
    missing_fx = False
    for name in sorted(set(rep["by_company"]) | set(rep["undelivered"])):
        c = rep["by_company"].get(name) or {}
        ch = c.get("by_channel") or {}
        rev = c.get("revenue")
        missing_fx = missing_fx or (name in rep["by_company"] and rev is None)
        row = {
            "label": name, "deliveries": c.get("deliveries", 0),
            "qty": c.get("qty", 0.0), "qty_dry": c.get("qty_dry", 0.0),
            "qty_export": ch.get("export", 0.0), "qty_domestic": ch.get("domestic", 0.0),
            "qty_internal": ch.get("internal", 0.0),
            # Doanh thu để TRỐNG khi thiếu tỷ giá — không quy về 0 để khỏi đọc nhầm là "bán không thu tiền".
            "revenue_ty": None if rev is None else rev / 1_000_000_000,
            "cost": c.get("cost", 0.0),
            "remaining": (rep["undelivered"].get(name) or {}).get("qty", 0.0),
        }
        rows.append(row)
        for k, _, _ in _XLSX_COLS:
            v = row.get(k)
            if isinstance(v, (int, float)):
                totals[k] += v
    note = "Nguồn: các lần giao ghi trên hợp đồng & phụ lục."
    if missing_fx:
        note += " ⚠ Có lần giao thiếu tỷ giá → doanh thu để trống, KHÔNG tính là 0."
    data = unit_analytics_excel.build_xlsx(
        title="BÁO CÁO TIÊU THỤ", period=f"{date_from} → {date_to}", note=note,
        group_by="company", columns=_XLSX_COLS, rows=rows, totals=totals)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="bao-cao-tieu-thu-{date_from}-den-{date_to}.xlsx"'})


@router.get("/undelivered")
def undelivered(scope: Scope, as_of: str = Query(..., description="Tính tại ngày 'YYYY-MM-DD'"),
                company: str | None = Query(None)) -> dict:
    """ĐÃ KÝ HĐ CHƯA GIAO (khối 3) tại ngày — SL cam kết trừ tổng đã giao."""
    _, companies = scope
    _check_date(as_of, "Ngày")
    if company:
        _assert_company(companies, company)
        companies = [company]
    return {"as_of": as_of, "by_company": sales_contract_report.undelivered_on(as_of, companies)}


@router.get("/{contract_id}")
def get_contract(contract_id: int, scope: Scope) -> dict:
    """Chi tiết 1 hợp đồng mẹ + toàn bộ phụ lục (mỗi phụ lục = 1 lần giao + 1 lần thanh toán)."""
    _, companies = scope
    c = sales_contract_repo.get(contract_id)
    if not c or (companies is not None and c["company"] not in companies):
        raise HTTPException(404, "Không tìm thấy hợp đồng trong phạm vi tài khoản.")
    kids = sales_contract_repo.children(contract_id) if c["parent_id"] is None else []
    # 3 rổ: đã giao · đang chờ giao (đã mở đợt, chưa có ngày giao) · chưa mở đợt.
    if c["delivery_type"] == "multi":
        done = sum(k["qty"] for k in kids if k["delivered_at"])
        pending = sum(k["qty"] for k in kids if not k["delivered_at"])
    else:
        done = c["qty"] if c["delivered_at"] else 0.0
        pending = 0.0 if c["delivered_at"] else c["qty"]
    return {"contract": c, "children": kids, "delivered_qty": done, "pending_qty": pending,
            "remaining_qty": max(0.0, c["qty"] - done - pending)}


@router.put("")
def save_contract(body: ContractIn, scope: EditScope) -> dict:
    """Thêm mới / cập nhật hợp đồng mẹ hoặc phụ lục (phụ lục tự tính là ĐÃ GIAO)."""
    username, companies = scope
    _assert_company(companies, body.company)
    try:
        return {"contract": sales_contract_repo.save(body.model_dump(), body.company, username)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, scope: EditScope) -> dict:
    """Xoá 1 hợp đồng / phụ lục (hợp đồng mẹ còn phụ lục thì phải xoá phụ lục trước)."""
    _, companies = scope
    try:
        ok = sales_contract_repo.delete(contract_id, companies)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Không tìm thấy hợp đồng trong phạm vi tài khoản.")
    return {"ok": True}


@router.post("/file")
def upload_file(file: UploadFile, scope: EditScope) -> dict:
    """Upload hợp đồng scan / chứng từ thanh toán — trả tên file lưu để gắn vào bản ghi."""
    return contract_files.save(file)


@router.get("/file/{name}")
def get_file(name: str, scope: Scope, filename: str | None = Query(None)):
    """Tải file đã đính kèm (tên lưu uuid). Ép đúng MIME + chặn trình duyệt đoán kiểu.

    File nằm chung một thư mục phẳng nên phải kiểm file thuộc hợp đồng của đơn vị nào: thiếu bước
    này, tài khoản đơn vị A biết tên file là tải được bản scan hợp đồng của đơn vị B.
    """
    _, companies = scope
    owners = sales_contract_repo.companies_of_file(name)
    # Endpoint này CHỈ phục vụ file của hợp đồng bán hàng. File của module khác dùng chung thư mục
    # lưu trữ nên không chặn ở đây là mở đường đọc chéo module (chuyên viên chỉ có quyền hợp đồng
    # vẫn tải được file của biểu Thu mua/Tồn kho).
    if not owners:
        raise HTTPException(404, "Không tìm thấy file hợp đồng.")
    if companies is not None and not owners & set(companies):
        raise HTTPException(404, "Không tìm thấy file trong phạm vi tài khoản.")
    return contract_files.serve(name, filename)
