"""Schema CHỐT SỐ LIỆU ĐƠN VỊ — đợt chốt của Ban + xác nhận của đơn vị.

Kiểm tra nghiệp vụ (ngày hợp lệ, đơn vị thuộc quyền) nằm ở router/service, ở đây chỉ khai hình dạng.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LockRoundIn(BaseModel):
    id: int | None = None              # có id = SỬA đợt đã có
    lock_date: str                     # chốt số liệu đến HẾT ngày này (YYYY-MM-DD)
    note: str | None = None            # lời nhắn của Ban, hiện trong cảnh báo của đơn vị


class LockConfirmIn(BaseModel):
    """Đơn vị bấm xác nhận chốt (quản trị khoá hộ dùng `LockUnitsIn`)."""
    round_id: int
    company: str


class LockUnitsIn(BaseModel):
    """Quản trị khoá / mở khoá hộ nhiều đơn vị trong một đợt."""
    round_id: int
    companies: list[str] = Field(default_factory=list)
