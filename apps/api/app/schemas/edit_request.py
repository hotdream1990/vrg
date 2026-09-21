"""Schema «Đề nghị sửa số liệu quá khứ» — body gửi đề nghị, ghi chú duyệt, payload theo từng thao tác.

Payload của mỗi thao tác = đúng body của API ghi gốc (xem `plans/260915-de-nghi-sua-so-lieu-qua-khu/
api-contract.md`), nên các schema dưới đây kế thừa/dùng lại schema gốc thay vì khai lại.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.unit_daily import UnitDailyEdit


class EditRequestIn(BaseModel):
    """Đơn vị gửi đề nghị. Kiểu lỏng CÓ CHỦ Ý: op/payload/lý do sai trả 400 kèm câu dễ hiểu (không 422)."""

    op: str = ""
    payload: Any = None
    reason: str | None = None


class ReviewIn(BaseModel):
    """Duyệt / từ chối. Ghi chú bắt buộc khi TỪ CHỐI; `expected_updated_at` = `updated_at` của đề nghị
    lúc người duyệt mở ra (kiểm ở service ⇒ 400/409 kèm câu dễ hiểu, không 422)."""

    note: str | None = Field(None, max_length=2000)
    expected_updated_at: str | None = Field(None, max_length=64)
    accept_changed: bool = False       # chỉ khi DUYỆT: đã xem cột Hiện tại, chấp nhận ghi đè


class PurchasePricesIn(BaseModel):
    """Đơn giá thu mua lớp đơn vị tự khai đi kèm biểu Thu mua. Chỉ ô có giá trị mới ghi; 0 = xoá ô."""

    purchase: float | None = Field(None, ge=0)
    purchase_cup: float | None = Field(None, ge=0)
    purchase_lace: float | None = Field(None, ge=0)


class DailyReportRequest(UnitDailyEdit):
    """Biểu Thu mua / Tồn kho 1 ngày (+ đơn giá khi kind=purchase).

    `create_only` (nút Thêm) chỉ kiểm LÚC GỬI — không lưu vào đề nghị (xem `edit_request_ops.prepare`).
    """

    prices: PurchasePricesIn | None = None


class ContractDeleteRequest(BaseModel):
    id: int


class ContractDeliveryTypeRequest(BaseModel):
    """Chuyển loại giao 1 hợp đồng = body của `PUT /api/sales-contracts/{id}/delivery-type` + `id`."""

    id: int
    delivery_type: str = ""
