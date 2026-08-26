"""Schema Đơn vị thành viên (member_unit)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MemberUnit(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True
    region: str | None = None       # khu vực đã gán (optional)
    country: str = "VN"             # quốc gia (VN/LA/KH)
    currency: str = "VND"           # loại tiền thu mua (VND/LAK/KHR) — ≠ VND ⇒ cần tỷ giá
    has_factory: bool = True        # có nhà máy chế biến — False ⇒ nhập tồn kho nguyên liệu
    parent_company: str | None = None  # công ty mẹ đã gán (cây mẹ-con, chỉ dùng cho báo cáo cấp Tập đoàn)
    # Đang lấy giá mủ nguyên liệu của đơn vị này tự động sang lớp chuyên viên
    # (bật ở màn Giá mủ nguyên liệu — xem `services/purchase_price_sync.py`).
    auto_price_sync: bool = False
    # SÁP NHẬP: đơn vị này đã nhập vào đơn vị nào, từ ngày nào. Số liệu TRƯỚC ngày đó vẫn đứng tên
    # đơn vị này (xem `services/member_unit_merge.py`) — khác hẳn đổi tên.
    merged_into: str | None = None
    merged_at: date | None = None


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
    parent_company: str | None = None      # công ty mẹ (áp khi set_parent=True); "" hoặc None = bỏ gán
    set_parent: bool = False               # True = áp parent_company


class MemberUnitMerge(BaseModel):
    """Sáp nhập đơn vị này vào `merged_into` kể từ `merged_at` (số liệu cũ giữ nguyên tên cũ)."""

    merged_into: str                 # đơn vị NHẬN (phải đang hoạt động, chưa sáp nhập đi đâu)
    merged_at: str                   # ngày hiệu lực 'YYYY-MM-DD'


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
