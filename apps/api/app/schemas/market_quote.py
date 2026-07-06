"""Schema Báo giá mủ thị trường — 1 phiếu/ngày (tỷ giá VCB + Mục 1-3 SVR + Mục 4 mủ nước)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VcbRate(BaseModel):
    """Tỷ giá Vietcombank trong phiếu (VNĐ/USD)."""

    mua_tm: float | None = None  # mua tiền mặt
    mua_ck: float | None = None  # mua chuyển khoản
    ban: float | None = None  # bán


class Section(BaseModel):
    """1 bảng giá theo chủng loại + ghi chú (Mục 1, 2)."""

    prices: dict[str, float | None] = Field(default_factory=dict)  # grade -> đơn giá
    note: str = ""


class DomesticVrgSection(Section):
    """Mục 3 — thêm tình trạng giao dịch theo chủng loại."""

    status: dict[str, str] = Field(default_factory=dict)  # grade -> tình trạng


class MarketQuote(BaseModel):
    """Phiếu báo giá mủ 1 ngày. `regions` (Mục 4) đồng bộ kho Giá mủ nguyên liệu."""

    as_of: str
    fx: VcbRate = Field(default_factory=VcbRate)
    domestic_private: Section = Field(default_factory=Section)  # Mục 1 — giá NĐ tư nhân (VNĐ/tấn)
    export_vrg: Section = Field(default_factory=Section)  # Mục 2 — giá XK VRG (USD/tấn)
    domestic_vrg: DomesticVrgSection = Field(default_factory=DomesticVrgSection)  # Mục 3 (VNĐ/tấn)
    regions: dict[str, float | None] = Field(default_factory=dict)  # Mục 4 — đơn vị -> đồng/độ TSC
    footer: str = ""


class MarketQuoteSummary(BaseModel):
    """Dòng tóm tắt cho danh sách phiếu."""

    as_of: str
    filled: int = 0
    updated: str | None = None


class MarketQuoteMeta(BaseModel):
    """Metadata dựng form: chủng loại SVR cố định + đơn vị thành viên (cột Mục 4)."""

    grades: list[str]
    units: list[str]


class VcbRateResult(VcbRate):
    """Tỷ giá VCB lấy realtime + ngày nguồn."""

    date: str
