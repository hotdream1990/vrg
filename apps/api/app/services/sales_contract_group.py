"""NHÓM BÁO CÁO của một hợp đồng bán: HĐ chuyến · HĐ nguyên tắc · HĐ dài hạn (chốt 01/10/2026).

Xếp theo HỒ SƠ MẸ trước, loại tự khai sau:
  - gắn HĐ nguyên tắc (HĐNT)  → `principle`
  - gắn HĐ dài hạn (HĐDH)     → `long_term`
  - không gắn hồ sơ nào       → loại tự khai (`spot` · `long_term` = phụ lục cũ chưa gắn hồ sơ ·
                                "" = chưa khai)

Vì sao không lấy ô "loại hợp đồng" của chính hợp đồng: Dầu Tiếng Việt Lào có 10 đơn hàng thuộc 3
HĐNT với Camel, 7 cái lưu "HĐ chuyến" (gắn bằng nút "Gắn hợp đồng có sẵn"), 3 cái lưu "Phụ lục" —
báo cáo xếp 3 cái sau vào "dài hạn" trong khi đơn vị không có HĐDH nào. Đơn vị và chủ dự án cùng
chốt: mọi hợp đồng thuộc HĐNT là HĐNT. Khoá nhóm trùng khoá `master_type` của `master_contract`.
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

#: Nhãn nhóm trên MÀN HÌNH. Biểu Excel mẫu Ban TTKD chỉ có 2 cột → HĐNT gộp vào cột chuyến
#: (xem `unit_period_report.ban_ttkd_view`).
GROUP_LABELS = {"spot": "HĐ chuyến", "principle": "HĐ nguyên tắc", "long_term": "HĐ dài hạn"}


def group_of(contract_type: str | None, master_type: str | None) -> str:
    """Nhóm báo cáo từ loại tự khai + loại hồ sơ mẹ (None = không gắn hồ sơ)."""
    if master_type in ("principle", "long_term"):
        return master_type
    return contract_type or ""


def master_types(master_ids: Iterable[Any]) -> dict[int, str]:
    """{id hồ sơ mẹ: master_type} — một truy vấn cho cả lô."""
    ids = sorted({int(i) for i in master_ids if i is not None})
    if not ids:
        return {}
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT id, master_type FROM master_contract WHERE id = ANY(:ids)"),
                          {"ids": ids}).all()
    return {int(r[0]): r[1] for r in rows}


def regrouped(old: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    """Lần lưu này có đổi NHÓM báo cáo (chuyến · HĐNT · dài hạn) của hợp đồng không?

    Nhóm xếp theo hồ sơ mẹ nên đổi hồ sơ mẹ — ô vốn được coi là an toàn sau khi chốt
    (`sales_contract_lock`) — cũng dịch sản lượng giữa các cột. Đợt giao không mang hồ sơ → False.
    """
    if old is None or new.get("parent_id") or old.get("parent_id"):
        return False
    mt = master_types([old.get("master_id"), new.get("master_id")])
    return (group_of(old.get("contract_type"), mt.get(old.get("master_id")))
            != group_of(new.get("contract_type"), mt.get(new.get("master_id"))))


def assert_regroup_fences(username: str, company: str | None, contract_ids: list[int]) -> None:
    """Đổi nhóm báo cáo của hợp đồng có LẦN GIAO nằm trong kỳ đã chốt → chặn tài khoản đơn vị.

    Xét cả lần giao của chính hợp đồng lẫn các ĐỢT GIAO bên trong: `assert_delivery_fences` chỉ nhìn
    ngày giao của dòng đang sửa, mà hợp đồng giao nhiều lần thì dòng mẹ không có ngày giao nào.
    """
    from app.core import security

    if not contract_ids:
        return
    with session_scope() as db:
        days = db.execute(text(
            "SELECT DISTINCT delivered_at FROM sales_contract WHERE delivered_at IS NOT NULL "
            "AND (id = ANY(:ids) OR parent_id = ANY(:ids))"),
            {"ids": [int(i) for i in contract_ids]}).scalars().all()
    security.assert_not_data_locked(username, company, *days)
