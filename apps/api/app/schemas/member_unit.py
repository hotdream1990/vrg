"""Schema Đơn vị thành viên (member_unit)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemberUnit(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class MemberUnitAdd(BaseModel):
    name: str


class MemberUnitUpdate(BaseModel):
    """Đổi tên và/hoặc bật-tắt active (bỏ field nào = không đổi field đó)."""

    new_name: str | None = None
    is_active: bool | None = None


class MemberUnitReorder(BaseModel):
    names: list[str] = Field(default_factory=list)
