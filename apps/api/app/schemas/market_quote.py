"""Schema Báo giá mủ thị trường — 1 phiếu/ngày (tỷ giá VCB + Mục 1-3 SVR + Mục 4 mủ nước)."""

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
    """Mục 4 — Đề xuất mua từ khách hàng: số lượng + đơn giá theo chủng loại (lưu trong phiếu)."""

    qty: dict[str, float | None] = Field(default_factory=dict)  # grade -> số lượng (tấn)
    prices: dict[str, float | None] = Field(default_factory=dict)  # grade -> đơn giá (VNĐ/tấn)
    note: str = ""


class MarketQuote(BaseModel):
    """Phiếu báo giá mủ 1 ngày. `regions`/`regions_cup` (Mục 5) đồng bộ kho Giá mủ nguyên liệu."""

    as_of: str
    fx: VcbRate = Field(default_factory=VcbRate)
    domestic_private: Section = Field(default_factory=Section)  # Mục 1 — giá NĐ hàng tư nhân (VNĐ/tấn)
    domestic_export: Section = Field(default_factory=Section)  # Mục 2 — giá NĐ hàng xuất khẩu (VNĐ/tấn)
    export_vrg: Section = Field(default_factory=Section)  # Mục 3 — giá XK VRG (USD/tấn)
    domestic_vrg: Section = Field(default_factory=Section)  # Mục 4 (VNĐ/tấn)
    customer_proposal: ProposalSection = Field(default_factory=ProposalSection)  # Mục 4 — đề xuất KH
    regions: dict[str, float | None] = Field(default_factory=dict)  # Mục 5 — mủ nước (đồng/độ TSC)
    regions_cup: dict[str, float | None] = Field(default_factory=dict)  # Mục 5 — mủ chén (đồng/độ TSC)
    footer: str = ""


class MarketQuoteSummary(BaseModel):
    """Dòng tóm tắt cho danh sách phiếu."""

    as_of: str
    filled: int = 0
    updated: str | None = None


class MarketQuoteMeta(BaseModel):
    """Metadata dựng form: chủng loại SVR + đơn vị thành viên (Mục 5) + gợi ý bao bì."""

    grades: list[str]
    units: list[str]
    packaging: list[str]


class VcbRateResult(VcbRate):
    """Tỷ giá VCB lấy realtime + ngày nguồn."""

    date: str
