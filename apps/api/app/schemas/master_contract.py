"""Schema HỢP ĐỒNG MẸ — HĐ nguyên tắc (HĐNT) / HĐ dài hạn (HĐDH).

Chỉ khai báo hình dạng dữ liệu nhận từ client; mọi kiểm tra nghiệp vụ nằm ở
`services/master_contract_clean.py` (cùng cách tổ chức với hợp đồng bán hàng).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.sales_contract import ContractDocIn


class MasterLineIn(BaseModel):
    """1 dòng cam kết: chủng loại · số lượng · quy khô.

    KHÔNG có đơn giá/loại tiền/tỷ giá (chốt 25/08/2026): hồ sơ mẹ chỉ cam kết CHỦNG LOẠI và SẢN
    LƯỢNG, còn giá là số của từng chuyến — khai ở phụ lục, hoặc đi theo công thức giá của hồ sơ.

    Số lượng để TRỐNG được: HĐ nguyên tắc thường chỉ chốt chủng loại. Quy khô đi kèm số lượng cho
    latex và mủ nguyên liệu, giống dòng hợp đồng bán.
    """
    grade: str = ""
    qty: float | None = None           # latex/mủ nguyên liệu: SL MỦ NƯỚC (tấn)
    qty_dry: float | None = None       # quy khô (tấn) — chỉ latex và mủ nguyên liệu


class MasterContractIn(BaseModel):
    id: int | None = None
    company: str
    code: str                          # SỐ HỢP ĐỒNG mẹ
    master_type: str = ""              # principle | long_term
    customer_id: int | None = None
    sign_date: str | None = None
    expiry_date: str | None = None
    lines: list[MasterLineIn] = Field(default_factory=list)
    price_formula: str | None = None   # công thức giá — text tự do
    files: list[ContractDocIn] = Field(default_factory=list)
    note: str | None = None


class AnnexLinkIn(BaseModel):
    """Gắn / gỡ PHỤ LỤC cho hợp đồng mẹ — chọn hợp đồng ĐÃ CÓ rồi nối vào hồ sơ.

    `attach = False` là GỠ. Gắn/gỡ đổi liên kết `master_id` + loại hợp đồng (gắn → Phụ lục, gỡ → chưa
    khai — chốt 01/10/2026); khách hàng và sản lượng giữ nguyên (chốt 24/08/2026).
    """
    contract_ids: list[int] = Field(default_factory=list)
    attach: bool = True
