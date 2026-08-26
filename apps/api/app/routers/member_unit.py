"""Router Đơn vị thành viên — quản lý danh sách công ty cho Giá mủ nguyên liệu."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_cap_edit
from app.schemas.member_unit import (
    MemberUnit,
    MemberUnitAdd,
    MemberUnitMerge,
    MemberUnitReorder,
    MemberUnitUpdate,
)
from app.services import member_unit_merge, member_unit_repo

router = APIRouter(prefix="/api/member-units", tags=["member-units"])

_editor = [Depends(require_cap_edit("member_unit"))]  # ghi: cần 'member_unit' mức Sửa


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
    """Đổi tên (migrate giá) và/hoặc bật-tắt active và/hoặc gán khu vực/công ty mẹ."""
    try:
        if body.new_name is not None:
            member_unit_repo.rename_unit(name, body.new_name)
            name = body.new_name.strip() or name
        if body.is_active is not None:
            # Đơn vị đã sáp nhập bị ẩn theo thiết kế — bật lại bằng nút "Hiện" sẽ cho nó xuất hiện
            # trở lại ở mọi form nhập liệu trong khi vẫn mang cờ sáp nhập. Phải gỡ sáp nhập trước.
            if body.is_active and (unit := _get(name)) and unit.get("merged_into"):
                raise ValueError(f"“{name}” đã sáp nhập vào “{unit['merged_into']}” — "
                                 "gỡ sáp nhập trước nếu muốn cho hoạt động trở lại.")
            member_unit_repo.set_active(name, body.is_active)
        if body.set_region:
            member_unit_repo.set_region(name, body.region)
        if body.set_locale:
            member_unit_repo.set_locale(name, body.country, body.currency)
        if body.set_factory and body.has_factory is not None:
            member_unit_repo.set_factory(name, body.has_factory)
        if body.set_parent:
            member_unit_repo.set_parent(name, body.parent_company)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return member_unit_repo.list_units()


def _get(name: str) -> dict | None:
    return next((u for u in member_unit_repo.list_units() if u["name"] == name), None)


@router.post("/{name}/merge", dependencies=_editor)
def merge_unit(name: str, body: MemberUnitMerge):
    """Sáp nhập đơn vị `name` vào đơn vị khác kể từ ngày hiệu lực.

    KHÔNG chuyển số liệu: mọi bản ghi cũ giữ nguyên tên đơn vị cũ nên vẫn tách được "trước sáp
    nhập / sau sáp nhập" (xem `services/member_unit_merge.py`). Từ ngày hiệu lực, đơn vị cũ bị ẩn
    khỏi các form nhập liệu và tài khoản của nó chuyển sang đơn vị mới.
    """
    try:
        result = member_unit_merge.merge(name, body.merged_into.strip(), body.merged_at)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**result, "units": member_unit_repo.list_units()}


@router.delete("/{name}/merge", dependencies=_editor)
def unmerge_unit(name: str):
    """Gỡ sáp nhập — đơn vị hoạt động độc lập trở lại (tài khoản KHÔNG tự trả về, cấp lại tay)."""
    try:
        result = member_unit_merge.unmerge(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**result, "units": member_unit_repo.list_units()}


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
