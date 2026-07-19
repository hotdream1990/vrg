"""Schema báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho) + chỉ tiêu kế hoạch thu mua."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["purchase", "consumption"]


class UnitDailyEdit(BaseModel):
    kind: Kind
    company: str                       # đơn vị (member ép ∈ đơn vị được gán; editor có quyền → mọi đơn vị)
    as_of: str                         # ngày báo cáo 'YYYY-MM-DD'
    # {ô: số} (thu mua) hoặc {sales: [...dòng...], ...ô tồn kho} (tiêu thụ). Server chuẩn hoá theo allowlist.
    fields: dict[str, Any] = Field(default_factory=dict, max_length=40)
    create_only: bool = False          # True (nút Thêm) → 409 nếu (ngày, đơn vị, loại) đã có số (chống ghi trùng)


class PurchasePlanEdit(BaseModel):
    """Số liệu NĂM của 1 đơn vị (nhập 1 lần, cập nhật khi có thay đổi). None = xoá ô đó."""

    year: int = Field(ge=2020, le=2100)
    company: str
    plan_tonnes: float | None = None        # kế hoạch thu mua năm (tấn)
    signed_lt_tonnes: float | None = None   # tổng SL đã ký HĐ dài hạn năm (tấn)
    carry_lt_tonnes: float | None = None    # SL tiêu thụ HĐ dài hạn năm trước chuyển sang (tấn)
    carry_spot_tonnes: float | None = None  # SL tiêu thụ HĐ chuyến năm trước chuyển sang (tấn)
