"""Pydantic schemas cho bulletin API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorldPriceItem(BaseModel):
    exchange: str
    grade: str
    unit: str = "USD/T"
    price_prev: int | None = None
    price_curr: int | None = None
    change_abs: int | None = None
    change_pct: float | None = None


class PhysicalPriceItem(BaseModel):
    grade: str
    price_prev: int | None = None
    price_curr: int | None = None
    change_abs: int | None = None
    change_pct: float | None = None


class VrgFloorItem(BaseModel):
    grade: str
    fob_usd: int | None = None
    domestic_vnd: int | None = None


class RawMaterialRegion(BaseModel):
    """1 dòng giá thu mua mủ nước theo công ty VRG (đồng/độ TSC)."""

    region: str                       # tên đơn vị thành viên VRG
    price: float | None = None        # giá đồng/độ TSC (numeric, để lưu fact_price)
    unit: str = "đồng/độ TSC"
    price_text: str = ""              # hiển thị (số đã format, không kèm đơn vị)


class SectionStatus(BaseModel):
    """Trạng thái nguồn dữ liệu 1 section."""
    section: str
    source: str            # "db" | "manual" | "empty"
    description: str       # mô tả chi tiết


class BulletinDraft(BaseModel):
    """Draft bản tin ngày -- đầy đủ data cho preview + edit trên UI."""

    report_date: str               # DD/MM/YYYY
    prev_date: str                 # DD/MM/YYYY

    # Section I -- read-only preview
    world_prices: list[WorldPriceItem] = Field(default_factory=list)

    # Section II -- read-only preview (ngày cột = phiên vật chất THẬT, có thể cũ hơn ngày báo cáo)
    physical_prices: list[PhysicalPriceItem] = Field(default_factory=list)
    physical_prev_label: str = ""      # DD/MM/YYYY — phiên vật chất trước
    physical_curr_label: str = ""      # DD/MM/YYYY — phiên vật chất gần nhất
    physical_stale: bool = False       # phiên gần nhất cũ hơn ngày báo cáo

    # Section III -- editable
    vrg_floor_prev_label: str = ""
    vrg_floor_curr_label: str = ""
    vrg_floor_prev: list[VrgFloorItem] = Field(default_factory=list)
    vrg_floor_curr: list[VrgFloorItem] = Field(default_factory=list)
    raw_materials: list[RawMaterialRegion] = Field(default_factory=list)

    # Section IV -- editable
    exchange_summary: list[str] = Field(default_factory=list)
    physical_summary: str = ""
    market_analysis: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    # Data source summary (auto-computed by service)
    data_sources: list[SectionStatus] = Field(default_factory=list)


class BulletinDraftUpdate(BaseModel):
    """Chi cac field admin co the chinh sua."""

    vrg_floor_prev_label: str | None = None
    vrg_floor_curr_label: str | None = None
    vrg_floor_prev: list[VrgFloorItem] | None = None
    vrg_floor_curr: list[VrgFloorItem] | None = None
    raw_materials: list[RawMaterialRegion] | None = None
    exchange_summary: list[str] | None = None
    physical_summary: str | None = None
    market_analysis: list[str] | None = None
    source_urls: list[str] | None = None

