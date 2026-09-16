"""Ghi 1 ô ĐƠN GIÁ THU MUA do ĐƠN VỊ TỰ KHAI (lớp `vrg_unit`) — một chỗ cho mọi đường ghi của đơn vị.

Hai nơi dùng: màn giá của tài khoản đơn vị (`PUT /api/member/prices`) và luồng Ban duyệt «Đề nghị
sửa số liệu» (`edit_request_ops_daily`). Tách ra để hai đường không lệch nhau về nguồn, nhãn đơn vị
tính hay luật giá 0.
"""

from __future__ import annotations

from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_UNIT
from app.services import price_repo


def save(company: str, as_of: str, price_type: str, price: float) -> bool:
    """Ghi giá lớp đơn vị tự khai. Trả True nếu là giá 0 = "ngày đó không có giá" (ô bị XOÁ).

    Nhãn đơn vị tính lấy theo loại mủ (mủ nước độ TSC, mủ chén/mủ dây độ DRC — chốt 17/08/2026);
    giá 0 do `price_repo.upsert_record` xoá ô thay vì lưu số 0 (xem `market_meta`).
    """
    price_repo.upsert_record({
        "as_of": as_of, "source": PURCHASE_SOURCE_UNIT, "grade": company, "contract": "",
        "price_type": price_type, "price": float(price),
        "currency": "VND", "unit": PURCHASE_PRICE_UNIT[price_type],
    })
    return float(price) == 0
