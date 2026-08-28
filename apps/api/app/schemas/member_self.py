"""Schema cho tài khoản đơn vị thành viên tự nhập giá mủ nước / mủ chén của các đơn vị được gán."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemberPriceEdit(BaseModel):
    company: str  # đơn vị (phải nằm trong danh sách gán của tài khoản)
    as_of: str  # YYYY-MM-DD
    # mủ nước | mủ chén | mủ dây — khớp `market_meta.PURCHASE_PRICE_TYPES`
    price_type: Literal["purchase", "purchase_cup", "purchase_lace"]
    # 0 ĐƯỢC PHÉP và có nghĩa "ngày đó không có giá" → server xoá ô giá, KHÔNG lưu số 0
    # (xem `market_meta`). Trước đây chặn `gt=0`: đơn vị gõ 0 là nhận lỗi 422 khó hiểu trong khi
    # sản lượng đã lưu xong — nhìn như hệ thống hỏng. Số âm vẫn chặn.
    price: float = Field(ge=0)
    # ĐÃ BỎ (17/08/2026): mủ chén luôn tính theo độ DRC, mủ nước theo độ TSC — nhãn đơn vị lấy từ
    # `market_meta.PURCHASE_PRICE_UNIT`. Vẫn NHẬN trường này để trình duyệt chưa nạp lại bản mới
    # không bị 422, nhưng server BỎ QUA giá trị gửi lên.
    basis: Literal["tsc", "drc"] | None = None
