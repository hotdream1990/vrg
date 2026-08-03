"""Schema báo cáo tiêu thụ–tồn kho theo ngày (thu mua · tiêu thụ–tồn kho) + chỉ tiêu kế hoạch thu mua."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["purchase", "consumption"]


class UnitDailyEdit(BaseModel):
    kind: Kind
    company: str                       # đơn vị (member ép ∈ đơn vị được gán; editor có quyền → mọi đơn vị)
    as_of: str                         # ngày báo cáo 'YYYY-MM-DD'
    # {ô: số} (thu mua) hoặc {sales: [...dòng...], ...ô tồn kho} (tiêu thụ). Server chuẩn hoá theo allowlist.
    fields: dict[str, Any] = Field(default_factory=dict, max_length=40)
    create_only: bool = False          # True (nút Thêm) → 409 nếu (ngày, đơn vị, loại) đã có số (chống ghi trùng)


class UnitDailyMove(BaseModel):
    """Đổi NGÀY của một bản ghi đã nhập (nhập nhầm ngày) — nội dung giữ nguyên.

    Cả ngày cũ lẫn ngày mới đều phải nằm trong cửa sổ sửa của người thao tác (server ép).
    """

    kind: Kind
    company: str
    as_of: str                         # ngày ĐANG lưu của bản ghi
    to_date: str                       # ngày MỚI muốn chuyển sang


class PurchasePlanEdit(BaseModel):
    """Số liệu NĂM của 1 đơn vị (nhập 1 lần, cập nhật khi có thay đổi). None = xoá ô đó."""

    year: int = Field(ge=2020, le=2100)
    company: str
    plan_tonnes: float | None = None        # kế hoạch thu mua năm (tấn)
    signed_lt_tonnes: float | None = None   # tổng SL đã ký HĐ dài hạn năm (tấn)
    carry_lt_tonnes: float | None = None    # SL tiêu thụ HĐ dài hạn năm trước chuyển sang (tấn)
    carry_spot_tonnes: float | None = None  # SL tiêu thụ HĐ chuyến năm trước chuyển sang (tấn)
    plan_sales_spot_tonnes: float | None = None  # kế hoạch TIÊU THỤ cho HĐ chuyến (tấn)


class ContractDocIn(BaseModel):
    """1 chứng từ đính kèm: tên lưu trên server (uuid) + tên gốc để hiển thị."""

    file: str
    filename: str | None = None


class StockContractEdit(BaseModel):
    """1 hợp đồng đã ký chưa giao — nhập MỘT LẦN, tự nằm trong tồn kho tới hết ngày trước ngày giao.

    `id` trống = thêm mới. Khi xuất kho chỉ cần cập nhật `delivered_date` (ngày giao thực tế).
    """

    id: int | None = None
    company: str
    code: str | None = None                 # số Hợp đồng / Phụ lục
    grade: str                              # chủng loại
    qty: float | None = None                # số lượng (tấn)
    price: float | None = None              # đơn giá (theo `ccy`)
    ccy: Literal["VND", "USD"] = "VND"
    fx: float | None = None                 # tỷ giá USD→VND (khi ccy = USD)
    start_date: str                         # ngày bắt đầu tồn kho 'YYYY-MM-DD'
    delivery_date: str | None = None        # lịch giao (dự kiến)
    delivered_date: str | None = None       # ngày giao THỰC TẾ (trống = chưa giao)
    # HĐ scan: đính kèm NHIỀU file. Cặp `file`/`filename` là file ĐẦU danh sách — server tự ghi lại
    # để bản ghi cũ và client cũ (chỉ gửi cặp phẳng) vẫn dùng được (xem services/contract_docs.py).
    files: list[ContractDocIn] | None = None
    file: str | None = None
    filename: str | None = None


class ExcelImportCommit(BaseModel):
    """Ghi các dòng đã XEM TRƯỚC từ file Excel (client gửi lại nguyên danh sách đã đọc)."""

    kind: str = Field(pattern="^(purchase|sales|stock|plan)$")
    rows: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
