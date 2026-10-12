"""Schema Báo giá mủ thị trường — 1 phiếu/ngày (tỷ giá VCB + Mục 1-4 SVR + Mục 5 đề xuất KH + Mục 6 giá mủ tư nhân)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.market_meta import MARKET_QUOTE_GRADES


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


class ProposalItem(BaseModel):
    """1 dòng đề xuất của khách hàng. Cùng một chủng loại có thể có nhiều dòng (nhiều khách / nhiều nguồn)."""

    grade: str = ""  # chủng loại (SVR 10, RSS3, …)
    customer: str = ""  # tên khách hàng — chọn từ danh mục khách hàng của hệ thống
    qty: float | None = None  # số lượng (tấn)
    price_vnd: float | None = None  # đơn giá (VNĐ/tấn)
    price_usd: float | None = None  # đơn giá (USD/tấn)
    source: str = ""  # nguồn — tên công ty thành viên


class ProposalSection(BaseModel):
    """Mục 5 — Đề xuất mua từ khách hàng - hàng VRG: danh sách dòng đề xuất (lưu trong phiếu)."""

    items: list[ProposalItem] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _from_legacy(cls, data: Any) -> Any:
        """Phiếu cũ (đến 0.4.118) lưu theo chủng loại: `qty` / `prices` là dict chủng loại → số.

        Đọc phiếu cũ thì đổi thành danh sách dòng (mỗi chủng loại có số = một dòng) để không mất số đã nhập.
        """
        if not isinstance(data, dict) or data.get("items") or not ("qty" in data or "prices" in data):
            return data
        qty, prices = data.get("qty") or {}, data.get("prices") or {}
        known = [g for g in MARKET_QUOTE_GRADES if g in qty or g in prices]
        grades = known + [g for g in {**qty, **prices} if g not in known]
        items = [{"grade": g, "qty": qty.get(g), "price_vnd": prices.get(g)}
                 for g in grades if qty.get(g) is not None or prices.get(g) is not None]
        return {"items": items, "note": data.get("note", "")}


class PrivatePrice(BaseModel):
    """Mục 6 — giá mủ của 1 đơn vị tư nhân: một giá (`price`) hoặc khoảng giá (`price`–`price_max`)."""

    price: float | None = None
    price_max: float | None = None


class MarketQuote(BaseModel):
    """Phiếu báo giá mủ 1 ngày — toàn bộ lưu trong payload của phiếu."""

    as_of: str
    fx: VcbRate = Field(default_factory=VcbRate)
    domestic_private: Section = Field(default_factory=Section)  # Mục 1 — giá NĐ hàng tư nhân (VNĐ/tấn)
    domestic_export: Section = Field(default_factory=Section)  # Mục 2 — giá XK hàng tư nhân (USD/tấn FOB)
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
