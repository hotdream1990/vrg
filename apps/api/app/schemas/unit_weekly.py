"""Schema báo cáo tuần đơn vị (thu mua · tiêu thụ–tồn kho) + chỉ tiêu kế hoạch thu mua."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal["purchase", "consumption"]


class UnitWeeklyEdit(BaseModel):
    kind: Kind
    company: str                       # đơn vị (member ép ∈ đơn vị được gán; editor có quyền → mọi đơn vị)
    week_key: str                      # Thứ 2 ISO của tuần 'YYYY-MM-DD'
    fields: dict[str, float] = Field(default_factory=dict, max_length=40)  # {ô: số}; server lọc theo allowlist
    create_only: bool = False          # True (nút Thêm) → 409 nếu (tuần, đơn vị, loại) đã có số (chống ghi trùng)


class PurchasePlanEdit(BaseModel):
    year: int = Field(ge=2020, le=2100)
    company: str
    plan_tonnes: float | None = None   # None = xoá chỉ tiêu
