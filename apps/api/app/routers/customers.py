"""Router DANH MỤC KHÁCH HÀNG — dùng chung cho đơn vị thành viên và chuyên viên.

Phạm vi do server ép (`cap_or_member_scope`): đơn vị chỉ thấy/sửa khách của chính mình;
chuyên viên có quyền `sales_contract` thấy mọi đơn vị. Không nhân đôi endpoint /api/member/*.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.permissions import LEVEL_EDIT
from app.core.security import cap_or_member_scope
from app.schemas.sales_contract import CustomerIn
from app.services import customer_repo

router = APIRouter(prefix="/api/customers", tags=["customers"])

Scope = Annotated[tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract"))]
EditScope = Annotated[
    tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract", LEVEL_EDIT))]


def _assert_company(companies: list[str] | None, company: str) -> None:
    """Chặn ghi sang đơn vị ngoài phạm vi (None = chuyên viên, được mọi đơn vị)."""
    if companies is not None and company not in companies:
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


@router.get("")
def list_customers(scope: Scope, include_inactive: bool = True, q: str | None = None):
    """Danh sách khách hàng trong phạm vi tài khoản."""
    _, companies = scope
    return customer_repo.list_customers(companies, include_inactive, q)


@router.put("")
def save_customer(body: CustomerIn, scope: EditScope):
    """Thêm mới (không có id) hoặc cập nhật 1 khách hàng."""
    username, companies = scope
    _assert_company(companies, body.company)
    try:
        return customer_repo.save(body.model_dump(), body.company, username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{customer_id}")
def delete_customer(customer_id: int, scope: EditScope):
    """Xoá 1 khách hàng (chặn khi đã gắn hợp đồng — nên ẩn thay vì xoá)."""
    _, companies = scope
    try:
        ok = customer_repo.delete(customer_id, companies)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Không tìm thấy khách hàng trong phạm vi tài khoản.")
    return {"ok": True}
