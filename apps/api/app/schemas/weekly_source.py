"""Schema danh mục nguồn tham khảo Báo cáo tuần (`/api/weekly-sources`)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeeklySourceIn(BaseModel):
    """Tạo mới — kiểm hợp lệ chi tiết (nhóm/cách dùng/mục/mã) nằm ở `weekly_source_repo.clean_source`."""

    category: str
    name: str = Field(max_length=200)
    role: str = ""
    url: str = ""
    sections: list[str] = Field(default_factory=list)
    guide: str = ""
    mode: str = "manual"
    feed_symbol: str | None = None
    enabled: bool = True
    sort_order: int | None = None  # bỏ trống → xếp cuối danh sách


class WeeklySourceUpdate(BaseModel):
    """Sửa — chỉ gửi trường cần đổi (gửi đủ cũng được)."""

    category: str | None = None
    name: str | None = Field(default=None, max_length=200)
    role: str | None = None
    url: str | None = None
    sections: list[str] | None = None
    guide: str | None = None
    mode: str | None = None
    feed_symbol: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class WeeklySource(BaseModel):
    id: int
    category: str
    name: str
    role: str
    url: str
    sections: list[str]
    guide: str
    mode: str
    feed_symbol: str | None
    enabled: bool
    sort_order: int
    updated_by: str | None
    updated_at: str | None


class LabelItem(BaseModel):
    value: str
    label: str


class WeeklySourceMeta(BaseModel):
    categories: list[LabelItem]
    modes: list[LabelItem]
    sections: list[LabelItem]
