"""Danh mục Nhật ký hoạt động: nhóm số liệu + loại thao tác (nhãn hiển thị tiếng Việt).

Tách riêng khỏi `services/audit_repo.py` để router/UI dùng chung mà không kéo theo tầng DB —
cùng cách tổ chức với `core/permissions.py` (nhãn quyền).
"""

from __future__ import annotations

#: Nhóm số liệu → nhãn hiển thị (trùng key quyền để lọc/hiểu theo đúng màn hình nhập liệu).
ENTITIES: dict[str, str] = {
    "raw_material": "Giá mủ nguyên liệu",
    "physical": "Giá Physical",
    "auto_data": "Số liệu tự động (giá sàn · tỷ giá)",
    "floor": "Giá sàn Tập đoàn",
    "inventory": "Tồn kho",
    "market_quote": "Báo giá mủ thị trường",
    "unit_daily": "Báo cáo tiêu thụ - tồn kho",
    "stock_contract": "Hợp đồng tồn kho",
    "unit_plan": "Kế hoạch năm",
    "market_demand": "Nhu cầu thị trường",
    "bulletin_daily": "Bản tin ngày",
    "bulletin_weekly": "Báo cáo tuần",
    "member_unit": "Đơn vị thành viên",
    "member_region": "Khu vực",
    "user": "Tài khoản người dùng",
    "config": "Cấu hình hệ thống",
    "schedule": "Lịch chạy",
}

#: Loại thao tác → nhãn hiển thị.
ACTIONS: dict[str, str] = {
    "create": "Thêm mới",
    "update": "Sửa",
    "delete": "Xoá",
    "scan": "Quét tự động",
}
