"""Schema phiếu Nhu cầu thị trường (theo trường).

Kiểu dữ liệu để RỘNG (chuỗi ngày, chuỗi rỗng/None đều nhận): luật nghiệp vụ nằm ở
`services/market_demand_item_policy.py` để báo 400 bằng câu tiếng Việt — pydantic chặt quá thì
người dùng chỉ nhận được lỗi 422 khó hiểu.
"""

from __future__ import annotations

from pydantic import BaseModel


class DemandItemIn(BaseModel):
    id: int | None = None                 # rỗng = thêm mới
    company: str
    as_of: str                            # YYYY-MM-DD — ngày nhận nhu cầu
    customer: str | None = ""
    grade: str = ""
    qty: float | None = None
    qty_unit: str | None = "ton"
    price: float | None = None
    currency: str | None = "VND"
    delivery_place: str | None = ""
    delivery_time: str | None = ""        # gõ tự do: "đến 30/11/2026", "T9+10/2026"…
    result: str | None = ""               # gõ tự do: "Đã ký HĐMB số 1752 ngày 17/09/2026"; trống = chưa có
    note: str | None = ""


class DemandDeleteIn(BaseModel):
    """Payload đề nghị XOÁ một phiếu (`demand_delete`)."""

    id: int
