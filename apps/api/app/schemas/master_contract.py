"""Schema HỢP ĐỒNG MẸ — HĐ nguyên tắc (HĐNT) / HĐ dài hạn (HĐDH).

Chỉ khai báo hình dạng dữ liệu nhận từ client; mọi kiểm tra nghiệp vụ nằm ở
`services/master_contract_clean.py` (cùng cách tổ chức với hợp đồng bán hàng).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.sales_contract import ContractDocIn


class MasterLineIn(BaseModel):
    """1 dòng cam kết: chủng loại · số lượng · ĐƠN GIÁ của chủng loại đó · loại tiền · tỷ giá.

    Số lượng và đơn giá để TRỐNG được: HĐ nguyên tắc thường chỉ chốt chủng loại, còn giá đi theo
    công thức/thoả thuận từng chuyến (khai ở phụ lục).
    """
    grade: str = ""
    qty: float | None = None
    price: float | None = None         # VNĐ: triệu đ/tấn · ngoại tệ: /tấn (giống dòng hợp đồng)
    ccy: str = "VND"
    fx: float | None = None            # tỷ giá quy về VNĐ (bắt buộc khi có đơn giá ngoại tệ)


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

    `attach = False` là GỠ. Gắn thì khách hàng của các hợp đồng đó được ghi đè bằng khách của hợp
    đồng mẹ (luật "phụ lục thừa kế khách hàng"); gỡ thì giữ nguyên khách đang có.
    """
    contract_ids: list[int] = Field(default_factory=list)
    attach: bool = True
