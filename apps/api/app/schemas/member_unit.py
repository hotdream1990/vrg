"""Schema Đơn vị thành viên (member_unit)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemberUnit(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True
    region: str | None = None       # khu vực đã gán (optional)
    country: str = "VN"             # quốc gia (VN/LA/KH)
    currency: str = "VND"           # loại tiền thu mua (VND/LAK/KHR) — ≠ VND ⇒ cần tỷ giá
    has_factory: bool = True        # có nhà máy chế biến — False ⇒ nhập tồn kho nguyên liệu
    has_purchase_plan: bool = True  # có giao kế hoạch thu mua năm — chỉ đơn vị bật cờ mới hiện ở "Kế hoạch năm"


class MemberUnitAdd(BaseModel):
    name: str


class MemberUnitUpdate(BaseModel):
    """Đổi tên / bật-tắt active / gán khu vực (bỏ field nào = không đổi field đó)."""

    new_name: str | None = None
    is_active: bool | None = None
    region: str | None = None       # "" hoặc None qua endpoint riêng để bỏ gán
    set_region: bool = False        # True = áp giá trị `region` (kể cả None để gỡ gán)
    country: str | None = None      # quốc gia (VN/LA/KH)
    currency: str | None = None     # loại tiền (VND/LAK/KHR)
    set_locale: bool = False        # True = áp country + currency
    has_factory: bool | None = None # có nhà máy chế biến (áp khi set_factory=True)
    set_factory: bool = False       # True = áp has_factory
    has_purchase_plan: bool | None = None  # có giao kế hoạch thu mua năm (áp khi set_purchase_plan=True)
    set_purchase_plan: bool = False        # True = áp has_purchase_plan


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
