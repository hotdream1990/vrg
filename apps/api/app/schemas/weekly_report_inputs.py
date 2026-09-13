"""Schema đầu vào của Báo cáo tuần: tài liệu đính kèm · chỉ số thị trường · tin trong kỳ."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WeeklyAttachment(BaseModel):
    id: int
    week_key: str
    filename: str
    size: int
    kind: str                     # 'anrpc' | 'other'
    pages: int | None             # số trang PDF (DOCX: None)
    text_chars: int               # 0 = không trích được chữ (bản scan)
    summary: str | None
    uploaded_by: str | None
    created_at: str | None


class AttachmentPatch(BaseModel):
    kind: str | None = None
    summary: str | None = Field(default=None, max_length=20000)  # "" = xoá tóm tắt


class PointValue(BaseModel):
    value: float | None
    date: str                     # 'dd/mm'


class MarketIndicator(BaseModel):
    source_id: int
    name: str
    role: str
    url: str
    symbol: str
    values: list[float | None]    # TB giá đóng cửa từng tuần (len = len(weeks))
    changes: list[float | None]
    changes_pct: list[float | None]
    last_closes: list[float | None]
    high: PointValue | None       # cao/thấp CẢ KỲ (không gồm tuần mốc)
    low: PointValue | None
    error: str | None


class IndicatorsResponse(BaseModel):
    indicators: list[MarketIndicator]
    period: dict[str, Any]


class NewsArticle(BaseModel):
    url: str
    title: str
    published: str                # 'YYYY-MM-DD'


class NewsResponse(BaseModel):
    articles: list[NewsArticle]
    source_url: str
