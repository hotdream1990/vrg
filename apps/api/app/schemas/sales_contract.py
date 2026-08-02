"""Schema Khách hàng + Hợp đồng bán hàng 2 cấp (nhận từ client, kiểm nghiệp vụ ở repo)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContractDocIn(BaseModel):
    """1 file đính kèm: `file` = tên lưu trên server, `filename` = tên gốc hiển thị."""
    file: str
    filename: str | None = None


class CustomerIn(BaseModel):
    id: int | None = None
    company: str
    code: str | None = None
    name: str
    tax_code: str | None = None
    note: str | None = None
    is_active: bool = True


class ContractLineIn(BaseModel):
    """1 dòng chi tiết: chủng loại · tấn · quy khô · đơn giá · loại tiền · tỷ giá · chi phí."""
    grade: str = ""
    qty: float | None = None
    qty_dry: float | None = None      # quy khô (tấn) — bắt buộc khi bán LATEX + 2 loại NL mới
    price: float | None = None        # VNĐ: triệu đ/tấn · ngoại tệ: /tấn
    ccy: str = "VND"
    fx: float | None = None           # tỷ giá quy về VNĐ (bắt buộc khi ccy ≠ VND)
    cost: float | None = None         # chi phí của dòng bán (triệu đồng)


class ContractIn(BaseModel):
    id: int | None = None
    company: str
    parent_id: int | None = None      # khác None = PHỤ LỤC (một lần giao + một lần thanh toán)
    code: str
    customer_id: int | None = None
    delivery_type: str = "single"     # single = giao 1 lần · multi = giao nhiều lần (mẹ–phụ lục)
    sign_date: str | None = None
    expiry_date: str | None = None
    # Ngày MỞ ĐỢT giao (hàng gom vào kho cho đợt này) — bắt buộc với phụ lục;
    # hợp đồng giao-1-lần bỏ trống thì mặc định = ngày ký.
    start_date: str | None = None
    lines: list[ContractLineIn] = Field(default_factory=list)
    delivered: bool = False           # suy ra từ `delivered_at`, client gửi gì cũng bỏ qua
    delivered_at: str | None = None   # trống = ĐANG CHỜ GIAO (đợt đã mở, chưa giao)
    channel: str | None = None        # export | domestic | internal
    to_company: str | None = None     # đơn vị nhận khi tiêu thụ nội bộ
    payment_date: str | None = None
    payment_qty: float | None = None
    payment_cost: float | None = None
    payment_docs: list[ContractDocIn] = Field(default_factory=list)
    files: list[ContractDocIn] = Field(default_factory=list)
    note: str | None = None
