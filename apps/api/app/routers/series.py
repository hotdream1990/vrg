"""Router CHUỖI SỐ LIỆU THEO NGÀY cho Command Center / Bản tin biến động (chỉ đọc).

Gom cả 3 miền (thu mua · tồn kho · tiêu thụ) dựng từ số liệu đơn vị thành viên đã nhập. Khác họ
`/api/unit-daily/analytics/*` (bảng lọc chi tiết, gác quyền `unit_daily`): ở đây là số tổng hợp
mức Tập đoàn phục vụ dashboard, nên **chỉ gác đăng nhập** — Dashboard hiển thị cho cả người xem
không có quyền nhập liệu.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import unit_series
from app.services import unit_series_consumption as con
from app.services import unit_series_purchase as pur
from app.services import unit_series_stock as st

router = APIRouter(prefix="/api/series", tags=["series"])


@router.get("/purchase")
def purchase(
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
    basket: str = Query("steady", pattern="^(steady|all)$",
                        description="rổ tính dải giá: steady = chỉ đơn vị khai đều"),
) -> dict:
    """Mủ nước & mủ chén theo ngày: SẢN LƯỢNG thu mua (tấn) + dải đơn giá của các đơn vị."""
    a, b = unit_series.window(date_from, date_to)
    return pur.purchase_series(a, b, basket)


@router.get("/purchase-volume")
def purchase_volume(
    material: str = Query("latex", pattern="^(latex|cup|lace)$"),
    group_by: str = Query("region", pattern="^(region|company)$"),
    date_from: str | None = Query(None), date_to: str | None = Query(None),
) -> dict:
    """Sản lượng thu mua theo ngày, chia theo khu vực hoặc đơn vị (tấn)."""
    a, b = unit_series.window(date_from, date_to)
    return pur.purchase_volume_series(a, b, material, group_by)


@router.get("/stock")
def stock(
    group_by: str = Query("structure", pattern="^(structure|grade|region|free_grade)$"),
    date_from: str | None = Query(None), date_to: str | None = Query(None),
) -> dict:
    """Tồn kho theo ngày: cơ cấu hợp đồng · chủng loại · khu vực · tồn tự do theo chủng loại.

    Chuỗi bắt đầu từ `unit_series_stock.STOCK_START` — trước mốc đó chưa đủ đơn vị nhập để cộng
    thành số của Tập đoàn.
    """
    a, b = unit_series.window(date_from, date_to, start_floor=st.STOCK_START)
    return st.stock_series(a, b, group_by)


@router.get("/consumption")
def consumption(
    group_by: str = Query("region", pattern="^(region|company|grade|contract|channel)$"),
    date_from: str | None = Query(None), date_to: str | None = Query(None),
) -> dict:
    """Tiêu thụ theo ngày (tấn) + doanh thu quy VNĐ, lấy từ các lần giao của hợp đồng."""
    a, b = unit_series.window(date_from, date_to)
    return con.consumption_series(a, b, group_by)
