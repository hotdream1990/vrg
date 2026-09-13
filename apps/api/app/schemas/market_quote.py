"""Schema Báo giá mủ thị trường — 1 phiếu/ngày (tỷ giá VCB + Mục 1-4 SVR + Mục 5 đề xuất KH + Mục 6 giá mủ tư nhân)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VcbRate(BaseModel):
    """Tỷ giá Vietcombank trong phiếu (VNĐ/USD)."""

    mua_tm: float | None = None  # mua tiền mặt
    mua_ck: float | None = None  # mua chuyển khoản
    ban: float | None = None  # bán


class Section(BaseModel):
    """1 bảng giá theo chủng loại + ghi chú (Mục 1-4). Kèm bao bì, đơn vị vận chuyển & tình trạng."""

    prices: dict[str, float | None] = Field(default_factory=dict)  # grade -> đơn giá
    packaging: dict[str, str] = Field(default_factory=dict)  # grade -> bao bì (hàng rời/pallet)
    shipping: dict[str, str] = Field(default_factory=dict)  # grade -> đơn vị vận chuyển
    status: dict[str, str] = Field(default_factory=dict)  # grade -> tình trạng giao dịch
    note: str = ""


class ProposalSection(BaseModel):
    """Mục 5 — Đề xuất mua từ khách hàng - hàng VRG: số lượng + đơn giá theo chủng loại (lưu trong phiếu)."""

    qty: dict[str, float | None] = Field(default_factory=dict)  # grade -> số lượng (tấn)
    prices: dict[str, float | None] = Field(default_factory=dict)  # grade -> đơn giá (VNĐ/tấn)
    note: str = ""


class PrivatePrice(BaseModel):
    """Mục 6 — giá mủ của 1 đơn vị tư nhân: một giá (`price`) hoặc khoảng giá (`price`–`price_max`)."""

    price: float | None = None
    price_max: float | None = None


class MarketQuote(BaseModel):
    """Phiếu báo giá mủ 1 ngày — toàn bộ lưu trong payload của phiếu."""

    as_of: str
    fx: VcbRate = Field(default_factory=VcbRate)
    domestic_private: Section = Field(default_factory=Section)  # Mục 1 — giá NĐ hàng tư nhân (VNĐ/tấn)
    domestic_export: Section = Field(default_factory=Section)  # Mục 2 — giá XK hàng tư nhân (VNĐ/tấn)
    export_vrg: Section = Field(default_factory=Section)  # Mục 3 — giá XK VRG (USD/tấn)
    domestic_vrg: Section = Field(default_factory=Section)  # Mục 4 (VNĐ/tấn)
    customer_proposal: ProposalSection = Field(default_factory=ProposalSection)  # Mục 5 — đề xuất KH hàng VRG
    private_prices: dict[str, PrivatePrice] = Field(default_factory=dict)  # Mục 6 — tên đơn vị tư nhân -> giá
    # Mục 6 — chi phí gia công chế biến SVR 3L (đồng/tấn) dùng quy giá mủ tư nhân ra giá thành SVR 3L.
    # None = dùng mức mặc định trên giao diện (2.000.000).
    private_processing_cost: float | None = None
    footer: str = ""


class MarketQuoteSummary(BaseModel):
    """Dòng tóm tắt cho danh sách phiếu."""

    as_of: str
    filled: int = 0
    updated: str | None = None


class PrivateUnit(BaseModel):
    """1 đơn vị tư nhân trong danh mục Mục 6."""

    id: int
    name: str


class PrivateUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class MarketQuoteMeta(BaseModel):
    """Metadata dựng form: chủng loại SVR + gợi ý bao bì + danh mục đơn vị tư nhân (Mục 6)."""

    grades: list[str]
    packaging: list[str]
    private_units: list[PrivateUnit]


class VcbRateResult(VcbRate):
    """Tỷ giá VCB lấy realtime + ngày nguồn."""

    date: str
