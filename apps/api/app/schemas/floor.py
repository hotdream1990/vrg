"""Schema Giá sàn Tập đoàn (biểu giá theo lần)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FloorItem(BaseModel):
    grade: str
    fob_usd: float | None = None
    domestic_vnd: float | None = None


class FloorSchedule(BaseModel):
    lan: int
    as_of: str                       # YYYY-MM-DD (ngày áp dụng)
    items: list[FloorItem] = Field(default_factory=list)


class FloorScheduleSummary(BaseModel):
    lan: int
    as_of: str
    grades: int
    filled: int
    updated: str | None = None


class FloorSaveRequest(BaseModel):
    """Tạo/sửa 1 biểu giá. Khi tạo mới (POST) lần tự nhảy, bỏ qua field lan."""

    as_of: str
    items: list[FloorItem] = Field(default_factory=list)
