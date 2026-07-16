"""Schema Nhu cầu thị trường (free text theo đơn vị / ngày)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MarketDemandEdit(BaseModel):
    company: str  # đơn vị (member ép ∈ đơn vị được gán; editor có quyền → mọi đơn vị)
    as_of: str  # YYYY-MM-DD
    content: str = Field(default="", max_length=8000)  # free text, rỗng = xoá nội dung
    create_only: bool = False  # True = TẠO MỚI: chặn nếu (ngày, đơn vị) đã có nhu cầu (chống ghi trùng)
