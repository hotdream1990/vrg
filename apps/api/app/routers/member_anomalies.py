"""Cảnh báo bất thường cho LÃNH ĐẠO ĐƠN VỊ — chỉ số liệu của chính đơn vị mình.

Mục đích (chủ dự án đặt hàng 17/09/2026): lãnh đạo thấy ngay nhân viên nhập liệu đang sai/thiếu gì
để nhắc đúng trọng tâm, thay vì chờ Ban gọi điện. Cùng bộ luật với màn của quản trị, khác hai điểm:
  - chỉ giữ dòng của các đơn vị được gán cho tài khoản, cộng đơn vị đã sáp nhập vào đơn vị đó
    (lọc ở server, `anomaly_scope.for_units`);
  - bỏ luật tính trên số gộp toàn Tập đoàn, và không trả ngưỡng cấu hình (việc của quản trị).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.security import get_current_leader
from app.routers.anomalies import XLSX_MEDIA, scan_range
from app.services import anomaly_export, anomaly_scope, member_unit_merge

router = APIRouter(prefix="/api/member/anomalies", tags=["member-anomalies"])

_DATE = r"^\d{4}-\d{2}-\d{2}$"


def _mine(leader: dict, date_from: str | None, date_to: str | None) -> dict:
    """Số liệu trước sáp nhập vẫn đứng tên đơn vị CŨ, nên lỗi nhập liệu cũ cũng đứng tên đó. Mở
    cùng phạm vi ĐỌC như mọi màn khác của tài khoản đơn vị (`member_self._scope`) — không thì đơn
    vị đã giải thể không còn ai thấy cảnh báo của mình, trừ quản trị."""
    own = leader.get("member_units") or []
    units = member_unit_merge.expand(own) or own
    return anomaly_scope.for_units(scan_range(date_from, date_to), units)


@router.get("")
def my_anomalies(date_from: str | None = Query(None, pattern=_DATE),
                 date_to: str | None = Query(None, pattern=_DATE),
                 leader: dict = Depends(get_current_leader)) -> dict:
    """Cảnh báo của các đơn vị được gán (mặc định 01/01 → hôm qua, giống màn quản trị)."""
    return _mine(leader, date_from, date_to)


@router.get("/export.xlsx")
def export_my_anomalies(date_from: str | None = Query(None, pattern=_DATE),
                        date_to: str | None = Query(None, pattern=_DATE),
                        leader: dict = Depends(get_current_leader)) -> Response:
    """Excel đúng phần đang xem — để lãnh đạo gửi thẳng cho nhân viên cần sửa."""
    result = _mine(leader, date_from, date_to)
    name = f"canh-bao-bat-thuong-{result['date_from']}-den-{result['date_to']}.xlsx"
    return Response(
        content=anomaly_export.build_xlsx(result), media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
