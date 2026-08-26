"""HÀNG CÓ CHỨNG CHỈ + PREMIUM — dùng CHUNG cho hợp đồng gốc (HĐNT/HĐDH) và hợp đồng bán.

Yêu cầu 26/08/2026: *"Hợp đồng gốc có phần hàng có chứng chỉ: list chứng chỉ chọn (PEFC, EUDR,
VRG GREEN) và ô Premium cộng thêm… không chọn premium thì để trống. Hợp đồng chuyến cũng có tương
tự. Phần giá thì có option USD và VND, ô tiền để tự nhập"*.

3 giá trị lưu cùng nhau ở CẤP HỢP ĐỒNG (không phải từng dòng chủng loại):
    certs        — danh sách chứng chỉ đã chọn (chọn được nhiều)
    premium      — số tiền cộng thêm, để TRỐNG nếu hợp đồng không có premium
    premium_ccy  — USD hay VND (chỉ có nghĩa khi đã nhập premium)

⚠ Premium là số GHI NHẬN, **không** tự cộng vào đơn giá/doanh thu: đơn giá trên dòng hợp đồng là
giá bán thực tế đã chốt với khách (thường đã gồm phần premium). Cộng thêm lần nữa là thổi doanh thu.
Tách riêng như thế này để sau còn thống kê "bán được bao nhiêu tấn hàng có chứng chỉ, premium bình
quân bao nhiêu" mà không đụng tới con số doanh thu đang chạy.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.market_meta import CONTRACT_CERTS, PREMIUM_CURRENCIES

_CERTS = frozenset(CONTRACT_CERTS)
_CCY = frozenset(PREMIUM_CURRENCIES)


def clean_certs(value: Any) -> list[str]:
    """Danh sách chứng chỉ hợp lệ, bỏ trùng, giữ THỨ TỰ danh mục (raise nếu có mã lạ).

    Báo lỗi thay vì lặng lẽ bỏ giá trị lạ: chứng chỉ sai chính tả mà bị nuốt thì hợp đồng hiện ra
    "không có chứng chỉ" trong khi người nhập tưởng đã khai xong.
    """
    if value in (None, "", []):
        return []
    if not isinstance(value, (list, tuple, set)):
        raise ValueError("Danh sách chứng chỉ không hợp lệ.")
    picked = {str(v).strip() for v in value if str(v).strip()}
    bad = sorted(picked - _CERTS)
    if bad:
        raise ValueError(f"Chứng chỉ “{', '.join(bad)}” không có trong danh mục "
                         f"({', '.join(CONTRACT_CERTS)}).")
    return [c for c in CONTRACT_CERTS if c in picked]


def clean(row: dict) -> dict[str, Any]:
    """{certs, premium, premium_ccy} đã chuẩn hoá cho một hợp đồng."""
    certs = clean_certs(row.get("certs"))

    raw = row.get("premium")
    try:
        premium = None if raw in (None, "") else float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Premium phải là số.") from exc
    if premium is not None and not math.isfinite(premium):
        raise ValueError("Premium phải là số.")
    if premium is not None and premium < 0:
        raise ValueError("Premium không được âm.")
    # 0 = "có ô nhưng bằng không" — coi như KHÔNG có premium để bảng thống kê khỏi đếm hợp đồng
    # premium 0 vào nhóm "có premium" (cùng quy ước giá 0 = không có giá của kho giá).
    if premium == 0:
        premium = None

    ccy = str(row.get("premium_ccy") or "").strip().upper()
    if premium is None:
        return {"certs": certs, "premium": None, "premium_ccy": None}
    if ccy not in _CCY:
        raise ValueError(f"Loại tiền của premium phải là {' hoặc '.join(PREMIUM_CURRENCIES)}.")
    return {"certs": certs, "premium": premium, "premium_ccy": ccy}
