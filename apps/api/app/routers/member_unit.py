"""Router Đơn vị thành viên — quản lý danh sách công ty cho Giá mủ nguyên liệu."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_editor
from app.schemas.member_unit import (
    MemberUnit,
    MemberUnitAdd,
    MemberUnitReorder,
    MemberUnitUpdate,
)
from app.services import member_unit_repo

router = APIRouter(prefix="/api/member-units", tags=["member-units"])

_editor = [Depends(require_editor)]  # ghi: cần admin/editor (viewer chỉ xem)


@router.get("", response_model=list[MemberUnit])
def list_units(include_inactive: bool = True):
    """Danh sách đơn vị thành viên (theo thứ tự sắp xếp)."""
    return member_unit_repo.list_units(include_inactive)


@router.post("", response_model=list[MemberUnit], dependencies=_editor)
def add_unit(body: MemberUnitAdd):
    """Thêm đơn vị mới."""
    if not body.name.strip():
        raise HTTPException(400, "Tên đơn vị không được trống")
    member_unit_repo.add_unit(body.name)
    return member_unit_repo.list_units()


@router.put("/{name}", response_model=list[MemberUnit], dependencies=_editor)
def update_unit(name: str, body: MemberUnitUpdate):
    """Đổi tên (migrate giá) và/hoặc bật-tắt active và/hoặc gán khu vực."""
    if body.new_name is not None:
        member_unit_repo.rename_unit(name, body.new_name)
        name = body.new_name.strip() or name
    if body.is_active is not None:
        member_unit_repo.set_active(name, body.is_active)
    if body.set_region:
        member_unit_repo.set_region(name, body.region)
    return member_unit_repo.list_units()


@router.post("/reorder", response_model=list[MemberUnit], dependencies=_editor)
def reorder(body: MemberUnitReorder):
    """Sắp xếp lại theo thứ tự danh sách tên truyền vào."""
    member_unit_repo.reorder(body.names)
    return member_unit_repo.list_units()


@router.delete("/{name}", response_model=list[MemberUnit], dependencies=_editor)
def delete_unit(name: str):
    """Xoá đơn vị khỏi danh sách."""
    if not member_unit_repo.delete_unit(name):
        raise HTTPException(404, f"Không có đơn vị '{name}'")
    return member_unit_repo.list_units()
