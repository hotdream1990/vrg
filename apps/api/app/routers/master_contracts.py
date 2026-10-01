"""Router HỢP ĐỒNG MẸ (HĐNT/HĐDH) — dùng chung cho đơn vị thành viên và chuyên viên.

Dùng LẠI quyền `sales_contract` (cùng nhóm màn "Quản lý hợp đồng"): hợp đồng mẹ và phụ lục là một
bộ hồ sơ, tách quyền riêng chỉ tạo ra tài khoản xem được phụ lục mà không xem được hợp đồng gốc.
Phạm vi đơn vị do server ép (`cap_or_member_scope`) — đơn vị chỉ đụng được hồ sơ của mình.

File đính kèm dùng CHUNG endpoint upload/tải của `/api/sales-contracts/file` (cùng thư mục lưu),
xem `sales_contracts.get_file` — nó hỏi cả hai bảng để biết file thuộc đơn vị nào.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.market_meta import MASTER_CONTRACT_TYPES
from app.core.permissions import LEVEL_EDIT
from app.core.security import cap_or_member_scope
from app.schemas.master_contract import AnnexLinkIn, MasterContractIn
from app.services import (
    customer_repo, master_contract_annexes, master_contract_repo, sales_contract_group,
)

router = APIRouter(prefix="/api/master-contracts", tags=["master-contracts"])

Scope = Annotated[tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract"))]
EditScope = Annotated[
    tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract", LEVEL_EDIT))]


def _assert_company(companies: list[str] | None, company: str) -> None:
    if companies is not None and company not in companies:
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _with_customer(companies: list[str] | None, rows: list[dict]) -> list[dict]:
    """Gắn TÊN khách hàng cho các dòng đang hiện (chỉ tra đúng những khách có trong trang)."""
    names = customer_repo.names_by_id(companies, sorted({
        r["customer_id"] for r in rows if r.get("customer_id")}))
    for r in rows:
        r["customer_name"] = names.get(r.get("customer_id") or 0)
    return rows


@router.get("")
def list_masters(scope: Scope, company: str | None = Query(None),
                 q: str | None = Query(None, max_length=120, description="Tìm theo số HĐ/ghi chú"),
                 master_type: str | None = Query(None, pattern="^(principle|long_term)$"),
                 customer_id: list[int] | None = Query(None),
                 ids: list[int] | None = Query(None, description="Lấy đúng vài HĐ mẹ theo id"),
                 limit: int | None = Query(None, ge=1, le=200, description="Ô tìm nhanh"),
                 page: int = Query(1, ge=1),
                 page_size: int = Query(25, ge=1, le=200)) -> dict:
    """MỘT TRANG hợp đồng mẹ → `{items, total, page, page_size}` (phân trang Ở SERVER)."""
    _, companies = scope
    if company:
        _assert_company(companies, company)
    size = limit or page_size
    res = master_contract_repo.list_masters(
        companies, company=company, q=q, master_type=master_type, customer_ids=customer_id,
        ids=ids, limit=size, offset=0 if limit else (page - 1) * page_size)
    return {"items": _with_customer(companies, res["items"]), "total": res["total"],
            "page": 1 if limit else page, "page_size": size,
            "master_types": MASTER_CONTRACT_TYPES}


@router.get("/{master_id}")
def get_master(master_id: int, scope: Scope) -> dict:
    """Chi tiết 1 hợp đồng mẹ + danh sách PHỤ LỤC đã nối về nó."""
    _, companies = scope
    m = master_contract_repo.get(master_id)
    if not m or (companies is not None and m["company"] not in companies):
        raise HTTPException(404, "Không tìm thấy hợp đồng mẹ trong phạm vi tài khoản.")
    _with_customer(companies, [m])
    kids = master_contract_annexes.annexes(master_id)
    return {"master": m, "annexes": kids,
            # Sản lượng đã ký ở các phụ lục — đối chiếu với cam kết trên hợp đồng mẹ.
            "annex_qty": sum(k["qty"] for k in kids)}


@router.put("/{master_id}/annexes")
def link_annexes(master_id: int, body: AnnexLinkIn, scope: EditScope) -> dict:
    """Gắn các hợp đồng ĐÃ CÓ vào hợp đồng mẹ này (`attach=false` là gỡ ra).

    Chiều ngược của ô "Hợp đồng mẹ" ở form hợp đồng — cần cho việc dọn hồ sơ cũ, vì hàng nghìn hợp
    đồng đã nhập trước khi có cấp hợp đồng mẹ. Gắn/gỡ đổi liên kết + loại hợp đồng (Phụ lục / chưa
    khai), không đụng sản lượng hay khách hàng — xem `master_contract_annexes`.
    """
    username, companies = scope
    try:
        res = master_contract_annexes.link(master_id, body.contract_ids, body.attach,
                                           companies, username)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**res, "annexes": master_contract_annexes.annexes(master_id)}


@router.put("")
def save_master(body: MasterContractIn, scope: EditScope) -> dict:
    """Thêm mới (không có id) hoặc cập nhật 1 hợp đồng mẹ."""
    username, companies = scope
    _assert_company(companies, body.company)
    # Đổi HĐNT ↔ HĐDH là dời MỌI phụ lục sang cột khác của báo cáo (nhóm theo hồ sơ mẹ, 01/10/2026)
    # → phụ lục có lần giao trong kỳ đã chốt thì tài khoản đơn vị bị chặn.
    old = master_contract_repo.get(body.id) if body.id else None
    if old and old.get("master_type") != body.master_type:
        sales_contract_group.assert_regroup_fences(
            username, old["company"], [a["id"] for a in master_contract_annexes.annexes(body.id)])
    try:
        return {"master": master_contract_repo.save(body.model_dump(), body.company, username)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{master_id}")
def delete_master(master_id: int, scope: EditScope) -> dict:
    """Xoá 1 hợp đồng mẹ (chặn khi còn phụ lục trỏ về)."""
    _, companies = scope
    try:
        ok = master_contract_repo.delete(master_id, companies)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Không tìm thấy hợp đồng mẹ trong phạm vi tài khoản.")
    return {"ok": True}
