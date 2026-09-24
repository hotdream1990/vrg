"""Schema phương án giá sàn nháp + bản nháp tờ trình.

Phương án (`proposal`) nhận dạng dict rồi làm sạch ở `floor_proposal.sanitize` (dựng lại dòng theo
tờ trình, nạp lại giá lần trước từ DB) — schema chỉ chặn kích thước để không nhận payload phình.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

_TEXT_ITEMS = 20
_TEXT_LEN = 1500


_Grade = Annotated[str, StringConstraints(max_length=40)]


class ProposalChange(BaseModel):
    grades: list[_Grade] | None = Field(default=None, max_length=20)
    op: Literal["step", "amount", "percent", "set", "reset_model", "reset_current", "undo"]
    value: float | None = None
    field: Literal["fob", "vnd"] | None = None


class CreateProposal(BaseModel):
    as_of: str | None = Field(default=None, max_length=10)
    base: Literal["model", "current"] = "model"
    model: Literal["v1", "v1i", "v1f", "v2"] | None = None


class ApplyProposal(BaseModel):
    proposal: dict[str, Any]
    changes: list[ProposalChange] = Field(min_length=1, max_length=20)
    by: Literal["manual"] = "manual"   # thay đổi qua API luôn là sửa tay; "ai" chỉ Trợ lý đặt được


class PreviewProposal(BaseModel):
    proposal: dict[str, Any]
    n1: list[str] | None = Field(default=None, max_length=_TEXT_ITEMS)
    n2: list[str] | None = Field(default=None, max_length=_TEXT_ITEMS)
    draft_id: int | None = None


class CreateDraft(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=4000)
    source: Literal["assistant", "floor_suggest", "manual"] = "manual"
    proposal: dict[str, Any] | None = None
    as_of: str | None = Field(default=None, max_length=10)
    model: Literal["v1", "v1i", "v1f", "v2"] | None = None


class UpdateDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=4000)
    proposal: dict[str, Any]
    n1: list[str] = Field(default_factory=list, max_length=_TEXT_ITEMS)
    n2: list[str] = Field(default_factory=list, max_length=_TEXT_ITEMS)
    #: `updated_at` của bản đang sửa — có người lưu sau mốc này thì từ chối (409), không lưu đè.
    base_updated_at: str | None = Field(default=None, max_length=40)


def clean_paragraphs(items: list[str] | None) -> list[str] | None:
    """Đoạn diễn giải: bỏ đoạn rỗng, cắt độ dài. None giữ None (= dùng bản có sẵn)."""
    if items is None:
        return None
    return [s.strip()[:_TEXT_LEN] for s in items if isinstance(s, str) and s.strip()]
