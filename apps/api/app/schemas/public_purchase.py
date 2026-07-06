"""Schema cho link công khai nhập giá mủ nước (đơn vị thành viên)."""

from __future__ import annotations

from pydantic import BaseModel


class PublicAuthReq(BaseModel):
    password: str


class PublicSubmitReq(BaseModel):
    company: str
    price: float


class PublicRecentReq(BaseModel):
    company: str
