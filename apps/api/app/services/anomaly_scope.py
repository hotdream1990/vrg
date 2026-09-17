"""Thu hẹp kết quả "Cảnh báo bất thường" về các đơn vị của tài khoản LÃNH ĐẠO ĐƠN VỊ.

Lãnh đạo đơn vị dùng màn này để nhắc nhân viên nhập liệu ĐÚNG việc cần sửa, nên chỉ được thấy dòng
của chính đơn vị mình. Việc thu hẹp làm ở server — web nhận gì hiện nấy, không có bước lọc nào ở
trình duyệt để có thể bỏ qua.
"""
from __future__ import annotations

from typing import Any

from app.services.anomaly_types import finalize

#: Luật tính trên số GỘP của cả Tập đoàn (tổng doanh thu toàn hệ thống một ngày): dòng của nó
#: để lộ số liệu của đơn vị khác. Lỗi gốc phía đơn vị (giá bán nhập sai đơn vị tính) đã có luật
#: `wrong_sale_price` tính riêng từng đơn vị bắt được, nên bỏ nhóm này không mất gì.
GROUP_WIDE_RULES = frozenset({"revenue_outlier"})


def for_units(result: dict[str, Any], units: list[str]) -> dict[str, Any]:
    """Chỉ giữ dòng có `don_vi` thuộc `units`; dòng thiếu tên đơn vị bị bỏ (không đoán chủ).

    Các nhóm theo đơn vị vẫn trả đủ, kể cả nhóm rỗng, để người xem biết luật nào đã được kiểm tra;
    riêng nhóm trong `GROUP_WIDE_RULES` bị bỏ hẳn. Số đếm và tổng quan tính lại trên phần còn lại.
    """
    keep = set(units)
    groups = []
    for g in result.get("groups") or []:
        if g["key"] in GROUP_WIDE_RULES:
            continue
        rows = [r for r in g["rows"] if r.get("don_vi") in keep]
        groups.append({**g, "rows": rows, "count": len(rows),
                       "units": len({r["don_vi"] for r in rows})})
    return finalize(result["date_from"], result["date_to"], groups)
