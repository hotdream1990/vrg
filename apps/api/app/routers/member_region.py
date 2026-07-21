"""Router Khu vực (member_region) — nhóm đơn vị thành viên cho Giá mủ nguyên liệu."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_cap_edit
from app.schemas.member_unit import (
    MemberRegion,
    MemberRegionAdd,
    MemberRegionReorder,
    MemberRegionUpdate,
)
from app.services import member_region_repo

router = APIRouter(prefix="/api/member-regions", tags=["member-regions"])

_editor = [Depends(require_cap_edit("member_unit"))]  # ghi: cùng quyền 'member_unit' mức Sửa (khu vực = nhóm đơn vị)


@router.get("", response_model=list[MemberRegion])
def list_regions(include_inactive: bool = True):
    """Danh sách khu vực (theo thứ tự sắp xếp)."""
    return member_region_repo.list_regions(include_inactive)


@router.post("", response_model=list[MemberRegion], dependencies=_editor)
def add_region(body: MemberRegionAdd):
    """Thêm khu vực mới."""
    if not body.name.strip():
        raise HTTPException(400, "Tên khu vực không được trống")
    member_region_repo.add_region(body.name)
    return member_region_repo.list_regions()


@router.put("/{name}", response_model=list[MemberRegion], dependencies=_editor)
def update_region(name: str, body: MemberRegionUpdate):
    """Đổi tên (giữ liên kết đơn vị) và/hoặc bật-tắt active."""
    if body.new_name is not None:
        member_region_repo.rename_region(name, body.new_name)
        name = body.new_name.strip() or name
    if body.is_active is not None:
        member_region_repo.set_active(name, body.is_active)
    return member_region_repo.list_regions()


@router.post("/reorder", response_model=list[MemberRegion], dependencies=_editor)
def reorder(body: MemberRegionReorder):
    """Sắp xếp lại theo thứ tự danh sách tên truyền vào."""
    member_region_repo.reorder(body.names)
    return member_region_repo.list_regions()


@router.delete("/{name}", response_model=list[MemberRegion], dependencies=_editor)
def delete_region(name: str):
    """Xoá khu vực (gỡ liên kết các đơn vị đang thuộc khu vực này)."""
    if not member_region_repo.delete_region(name):
        raise HTTPException(404, f"Không có khu vực '{name}'")
    return member_region_repo.list_regions()
