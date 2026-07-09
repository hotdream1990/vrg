"""Schema Đơn vị thành viên (member_unit)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemberUnit(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True
    region: str | None = None       # khu vực đã gán (optional)


class MemberUnitAdd(BaseModel):
    name: str


class MemberUnitUpdate(BaseModel):
    """Đổi tên / bật-tắt active / gán khu vực (bỏ field nào = không đổi field đó)."""

    new_name: str | None = None
    is_active: bool | None = None
    region: str | None = None       # "" hoặc None qua endpoint riêng để bỏ gán
    set_region: bool = False        # True = áp giá trị `region` (kể cả None để gỡ gán)


class MemberUnitReorder(BaseModel):
    names: list[str] = Field(default_factory=list)


# ── Khu vực (member_region) — cùng cấu trúc quản lý với đơn vị ──
class MemberRegion(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class MemberRegionAdd(BaseModel):
    name: str


class MemberRegionUpdate(BaseModel):
    new_name: str | None = None
    is_active: bool | None = None


class MemberRegionReorder(BaseModel):
    names: list[str] = Field(default_factory=list)
