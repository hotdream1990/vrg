"""Schema response cho endpoint giá (scan/latest/history)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class PriceRow(BaseModel):
    source: str
    grade: str
    price: float
    currency: str
    unit: str
    price_type: str
    as_of: date
    contract: str | None = None


class PriceRecordEdit(BaseModel):
    """Thêm/sửa 1 bản ghi giá thủ công (trang quản lý đa sàn)."""

    as_of: date
    source: str
    grade: str
    contract: str = ""
    price_type: str
    price: float
    currency: str
    unit: str


class SourceStatus(BaseModel):
    source: str
    status: str
    count: int
    note: str | None = None


class ScanResponse(BaseModel):
    """Kết quả quét: bản ghi + trạng thái nguồn + thông tin ghi DB."""

    records: list[PriceRow]
    sources: list[SourceStatus]
    persisted: int          # số bản ghi ghi vào DB (0 nếu DB down)
    run_id: int | None = None
    db: str                 # "ok" | "skipped:<lý do>"


class ExchangeComponent(BaseModel):
    """1 dòng giá sàn dạng thành phần (native · tỷ giá · USD/T) — dashboard."""

    exchange: str
    grade: str
    native_price: float
    native_unit: str
    fx_pair: str | None = None
    fx_rate: float | None = None
    usd_tonne: int | None = None
    as_of: date


class FxRateItem(BaseModel):
    pair: str            # vd USD/JPY
    rate: float          # 1 USD = rate <ngoại tệ>
    as_of: date | None = None


class PriceBoard(BaseModel):
    """Bảng giá thành phần + tỷ giá cho dashboard Quét Đa sàn."""

    exchanges: list[ExchangeComponent]
    fx: list[FxRateItem]
    ingested_at: str | None = None


class HistoryPoint(BaseModel):
    as_of: date
    price: float


class HistorySeries(BaseModel):
    source: str
    grade: str
    points: list[HistoryPoint]
