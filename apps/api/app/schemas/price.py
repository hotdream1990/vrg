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


class HistoryPoint(BaseModel):
    as_of: date
    price: float


class HistorySeries(BaseModel):
    source: str
    grade: str
    points: list[HistoryPoint]
