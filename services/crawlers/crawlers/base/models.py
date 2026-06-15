"""Mô hình dữ liệu chuẩn cho crawler (Pydantic).

PriceRecord = bản ghi giá đã chuẩn hóa (1 grade, 1 ngày). ContractQuote = 1 dòng kỳ hạn
dùng để chọn theo volume/trading_value. CrawlResult = kết quả 1 nguồn (cô lập lỗi).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Source(str, Enum):
    ANRPC = "anrpc"
    SGX = "sgx"
    SHFE = "shfe"
    TOCOM = "tocom"
    LGM = "lgm"
    FX = "fx"


class Status(str, Enum):
    OK = "ok"          # lấy được ≥1 bản ghi
    EMPTY = "empty"    # nguồn truy cập được nhưng không có dữ liệu (vd ngày nghỉ)
    BLOCKED = "blocked"  # nguồn chặn/cần auth/PDF — ghi open item
    ERROR = "error"    # lỗi ngoài dự kiến


class ContractQuote(BaseModel):
    """Một dòng kỳ hạn future (để selector chọn kỳ hạn theo max volume/trading_value)."""

    expiry_month: int | None = None
    expiry_year: int | None = None
    settle: float | None = None
    volume: float | None = None
    trading_value: float | None = None


class PriceRecord(BaseModel):
    """Bản ghi giá chuẩn hóa — đầu ra dùng cho ETL/serving (Phase 03)."""

    source: Source
    grade: str                      # SMR20, STR20, SIR20, RSS3, TSR20, USD/CNY...
    price: float
    currency: str                   # USD, CNY, VND...
    unit: str                       # "US$/kg", "CNY/tonne", "per USD"...
    price_type: str                 # physical | settlement | fx
    as_of: date                     # ngày dữ liệu (T-1 trong production)
    contract: str | None = None     # mã/kỳ hạn nếu là future
    source_ts: datetime | None = None
    extra: dict = Field(default_factory=dict)


class CrawlResult(BaseModel):
    """Kết quả crawl 1 nguồn. Lỗi 1 nguồn không làm gãy nguồn khác."""

    source: Source
    status: Status
    records: list[PriceRecord] = Field(default_factory=list)
    note: str | None = None         # ghi chú / câu hỏi mở khi BLOCKED/EMPTY
