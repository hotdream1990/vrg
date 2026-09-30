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
    """1 dòng chi tiết: chủng loại · tấn · quy khô · đơn giá · loại tiền · tỷ giá."""
    grade: str = ""
    qty: float | None = None
    qty_dry: float | None = None      # quy khô (tấn) — bắt buộc khi bán LATEX + 2 loại NL mới
    price: float | None = None        # VNĐ: triệu đ/tấn · ngoại tệ: /tấn
    ccy: str = "VND"
    fx: float | None = None           # tỷ giá quy về VNĐ (bắt buộc khi ccy ≠ VND)
    # Ngày HIỆU LỰC của dòng (30/09/2026) — CHỈ dòng của hợp đồng, trống = theo ngày ký. Thiếu ô này
    # ở schema thì `model_dump()` nuốt mất, DB luôn NULL mà không ai báo (bẫy từng gặp với master_id).
    from_date: str | None = None


class ContractIn(BaseModel):
    id: int | None = None
    company: str
    parent_id: int | None = None      # khác None = ĐỢT GIAO (một lần giao + một lần thanh toán)
    # Khác None = hợp đồng nằm trong một HỒ SƠ HỢP ĐỒNG MẸ (HĐNT/HĐDH). CHỈ là liên kết — khách
    # hàng và mọi số liệu khác vẫn do chính hợp đồng khai (chốt 24/08/2026).
    master_id: int | None = None
    code: str
    customer_id: int | None = None
    delivery_type: str = "single"     # single = giao 1 lần · multi = giao nhiều lần (chia đợt)
    # Loại HỢP ĐỒNG (chỉ tiêu báo cáo): long_term = dài hạn · spot = chuyến. Bắt buộc ở hợp đồng;
    # đợt giao bỏ trống và thừa kế của hợp đồng. KHÔNG suy từ `delivery_type` — hai khái niệm khác.
    contract_type: str | None = None
    sign_date: str | None = None
    expiry_date: str | None = None
    # Ngày mở đợt — ô này đã BỎ khỏi form (05/08/2026) vì khối 3 nay tính trên hợp đồng, không
    # theo vòng đời từng đợt nữa. Vẫn nhận để bản ghi cũ sửa lại không mất dữ liệu.
    start_date: str | None = None
    lines: list[ContractLineIn] = Field(default_factory=list)
    delivered: bool = False           # suy ra từ `delivered_at`, client gửi gì cũng bỏ qua
    delivered_at: str | None = None   # trống = ĐANG CHỜ GIAO (đợt đã lập, chưa giao)
    channel: str | None = None        # export | domestic | internal
    to_company: str | None = None     # đơn vị nhận khi tiêu thụ nội bộ
    # Hoá đơn của đợt giao: số + file scan (chốt 05/08/2026).
    invoice_no: str | None = None
    invoice_docs: list[ContractDocIn] = Field(default_factory=list)
    payment_date: str | None = None
    payment_qty: float | None = None
    payment_docs: list[ContractDocIn] = Field(default_factory=list)
    files: list[ContractDocIn] = Field(default_factory=list)
    # HÀNG CÓ CHỨNG CHỈ (26/08/2026) — chọn nhiều; premium để TRỐNG nếu hợp đồng không có.
    certs: list[str] = Field(default_factory=list)   # PEFC · EUDR · VRG GREEN
    premium: float | None = None                     # số tiền cộng thêm (tự nhập)
    premium_ccy: str | None = None                   # USD | VND
    note: str | None = None


class CompletionIn(BaseModel):
    """Chốt HOÀN THÀNH hợp đồng — `completed_at = None` là MỞ LẠI hợp đồng.

    Hợp đồng GIAO 1 LẦN chưa có ngày giao: chốt hoàn thành CHÍNH LÀ ghi nhận đã giao (chốt
    27/08/2026) nên kèm luôn ngày giao + hình thức tiêu thụ. Trường hợp hợp đồng huỷ/không giao
    nữa thì gửi `no_delivery = true` — không có ô thoát này thì hợp đồng huỷ sẽ đẻ ra tiêu thụ ảo.
    """
    completed_at: str | None = None
    delivered_at: str | None = None    # để trống = lấy đúng ngày hoàn thành
    channel: str | None = None         # export | domestic | internal
    to_company: str | None = None      # đơn vị nhận (khi tiêu thụ nội bộ)
    no_delivery: bool = False          # huỷ / không giao nữa — chốt mà KHÔNG ghi lần giao


class DeliveryTypeIn(BaseModel):
    """Chuyển giao-1-lần ↔ giao-nhiều-lần mà không phải xoá hợp đồng nhập lại."""
    delivery_type: str
