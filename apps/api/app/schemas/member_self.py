"""Schema cho tài khoản đơn vị thành viên tự nhập giá mủ nước / mủ chén của các đơn vị được gán."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemberPriceEdit(BaseModel):
    company: str  # đơn vị (phải nằm trong danh sách gán của tài khoản)
    as_of: str  # YYYY-MM-DD
    price_type: Literal["purchase", "purchase_cup"]  # mủ nước | mủ chén
    # 0 ĐƯỢC PHÉP và có nghĩa "ngày đó không có giá" → server xoá ô giá, KHÔNG lưu số 0
    # (xem `market_meta`). Trước đây chặn `gt=0`: đơn vị gõ 0 là nhận lỗi 422 khó hiểu trong khi
    # sản lượng đã lưu xong — nhìn như hệ thống hỏng. Số âm vẫn chặn.
    price: float = Field(ge=0)
    # Mủ chén tính theo độ TSC hay độ DRC — chỉ đổi NHÃN đơn vị lưu kèm giá (mặc định TSC).
    basis: Literal["tsc", "drc"] | None = None
