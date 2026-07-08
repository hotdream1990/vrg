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
    title: str                       # tiêu đề custom (mặc định "Lần {lan}")
    items: list[FloorItem] = Field(default_factory=list)


class FloorScheduleSummary(BaseModel):
    lan: int
    as_of: str
    title: str
    grades: int
    filled: int
    updated: str | None = None


class FloorSaveRequest(BaseModel):
    """Tạo/sửa 1 biểu giá. `lan` tự nhảy khi tạo mới; `title` = tiêu đề custom (tuỳ chọn)."""

    as_of: str
    title: str | None = None
    items: list[FloorItem] = Field(default_factory=list)
