"""Quyền theo mục dữ liệu — phân quyền chuyên viên nhập liệu (editor).

Nguyên tắc: admin = TẤT CẢ; editor = theo danh sách `permissions` của tài khoản;
viewer (Người xem) = KHÔNG có mục số liệu nào (chỉ xem dashboard/bản tin ở tầng UI).
"""

from __future__ import annotations

# key quyền → nhãn hiển thị (dùng cho trang Quản trị người dùng)
DATA_CAPS: dict[str, str] = {
    "market_quote": "Báo giá mủ thị trường (Mục 1–4)",
    "raw_material": "Giá mủ nguyên liệu (+ Mục 5 giá mủ khu vực)",
    "floor": "Giá sàn Tập đoàn",
    "physical": "Giá Physical",
    "inventory": "Tồn kho",
    "member_unit": "Đơn vị thành viên",
    "auto_data": "Số liệu tự động (bảng giá sàn · tỷ giá · quét đa sàn)",
    "market_demand": "Nhu cầu thị trường (xem + sửa mọi đơn vị)",
    "unit_daily": "Báo cáo tiêu thụ - tồn kho (thu mua · tồn kho — xem/sửa mọi đơn vị)",
    # Quyền truy cập các màn phân tích/bản tin (xem + thao tác). Không có = ẩn khỏi menu + chặn API.
    "floor_suggest": "Gợi ý giá sàn",
    "bulletin_daily": "Bản tin ngày",
    "bulletin_weekly": "Báo cáo tuần",
    "market_movement": "Bản tin biến động",
    "assistant": "Trợ lý AI (hỏi đáp số liệu + tư vấn giá sàn)",
}
CAP_KEYS = frozenset(DATA_CAPS)


def clean_caps(permissions: list[str] | None) -> list[str]:
    """Lọc chỉ giữ key hợp lệ, bỏ trùng, theo thứ tự DATA_CAPS (chuẩn hoá trước khi lưu)."""
    got = set(permissions or [])
    return [c for c in DATA_CAPS if c in got]


def effective_caps(role: str, permissions: list[str] | None) -> set[str]:
    """Quyền THỰC của 1 tài khoản: admin→tất cả, editor→theo list, viewer→rỗng."""
    if role == "admin":
        return set(CAP_KEYS)
    if role == "editor":
        return {c for c in (permissions or []) if c in CAP_KEYS}
    return set()
