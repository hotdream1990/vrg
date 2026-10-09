"""Tổng tự cộng của Kế hoạch năm — hàm THUẦN (không đụng DB), dùng chung cho lưu và xem trước Excel.

`plan_revenue_ty` (KH doanh thu tổng, TỶ ĐỒNG) vẫn là cột thật để mọi nơi đang đọc không phải sửa,
nhưng do server cộng từ 3 mục con mỗi lần lưu (chốt 09/10/2026 — xem `revenue_total_to_save`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: 3 mục con của KH doanh thu (tỷ đồng): khai thác · thu mua · hàng hóa.
REVENUE_CHILDREN: tuple[str, ...] = (
    "plan_revenue_exploit_ty", "plan_revenue_purchase_ty", "plan_revenue_goods_ty",
)
REVENUE_TOTAL = "plan_revenue_ty"
_DIGITS = 6   # làm tròn để 0,1 + 0,2 không thành 0,30000000000000004 trong DB/nhật ký


def revenue_total(values: Mapping[str, Any]) -> float | None:
    """Tổng các mục con doanh thu KHÁC None (làm tròn 6 số lẻ); None nếu cả 3 đều trống.

    Mục con trống coi như không có — không có mục con nào thì tổng trống (không phải 0).
    """
    nums = [float(values[k]) for k in REVENUE_CHILDREN if values.get(k) is not None]
    return round(sum(nums), _DIGITS) if nums else None


def revenue_total_to_save(stored: Mapping[str, Any], body: Mapping[str, Any]) -> tuple[bool, float | None]:
    """KH doanh thu tổng phải ghi khi lưu `body` lên dòng đang có `stored` → (server quyết?, tổng).

    - Sau khi ghép body vào số đang lưu mà CÒN mục con có số → `(True, tổng mục con)`: con thắng,
      `plan_revenue_ty` trong body bị bỏ qua — kể cả body không có khoá con nào (client cũ gửi cả
      hàng với 3 con null, Excel mẫu cũ để trống ô tổng) để tổng không lệch khỏi mục con.
    - Không còn mục con nào: body vừa xoá nốt mục con cuối → `(True, None)`; ngược lại
      `(False, None)` = ghi `plan_revenue_ty` THEO BODY (đơn vị cũ chỉ có tổng; vắng mặt = giữ nguyên).
    """
    after = {k: body[k] if k in body else stored.get(k) for k in REVENUE_CHILDREN}
    total = revenue_total(after)
    if total is not None:
        return True, total
    cleared = any(k in body and _num(body[k]) != _num(stored.get(k)) for k in REVENUE_CHILDREN)
    return cleared, None


def _num(v: Any) -> float | None:
    return None if v is None else float(v)
