"""Schema cho tài khoản đơn vị thành viên tự nhập giá mủ nước / mủ chén của các đơn vị được gán."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemberPriceEdit(BaseModel):
    company: str  # đơn vị (phải nằm trong danh sách gán của tài khoản)
    as_of: str  # YYYY-MM-DD
    price_type: Literal["purchase", "purchase_cup"]  # mủ nước | mủ chén
    price: float = Field(gt=0)
