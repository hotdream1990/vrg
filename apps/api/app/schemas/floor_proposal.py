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


class Para(BaseModel):
    lead: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=4000)


class Signers(BaseModel):
    left_role: str = Field(default="", max_length=120)
    left_name: str = Field(default="", max_length=120)
    right_role: str = Field(default="", max_length=120)
    right_name: str = Field(default="", max_length=120)
    approver_role: str = Field(default="", max_length=120)
    approver_name: str = Field(default="", max_length=120)


class Memo(BaseModel):
    """Nội dung tờ trình mẫu mới (plans/261003-quy-trinh-gia-san). Làm sạch thêm ở `to_trinh_memo.clean`."""
    so: str = Field(default="", max_length=40)
    sign_date: str = Field(default="", max_length=10)
    futures_note: str = Field(default="", max_length=1500)
    futures: list[Para] = Field(default_factory=list, max_length=_TEXT_ITEMS)
    physical_title: str = Field(default="", max_length=300)
    physical_note: str = Field(default="", max_length=1500)
    physical: list[Para] = Field(default_factory=list, max_length=_TEXT_ITEMS)
    outlook: list[Para] = Field(default_factory=list, max_length=_TEXT_ITEMS)
    inventory: Para = Field(default_factory=Para)
    intro: str = Field(default="", max_length=1500)
    signers: Signers = Field(default_factory=Signers)
    ai: dict[str, Any] | None = None


class Sheet(BaseModel):
    """Chú thích tỷ giá dưới hình dự thảo."""
    vcb_rate: float | None = None
    vcb_time: str = Field(default="", max_length=20)
    vcb_date: str | None = Field(default=None, max_length=10)


class PreviewProposal(BaseModel):
    proposal: dict[str, Any]
    n1: list[str] | None = Field(default=None, max_length=_TEXT_ITEMS)
    n2: list[str] | None = Field(default=None, max_length=_TEXT_ITEMS)
    memo: Memo | None = None
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
    #: Diễn giải kiểu cũ (bản nháp trước quy trình 4 bước) — không gửi = giữ nguyên.
    n1: list[str] | None = Field(default=None, max_length=_TEXT_ITEMS)
    n2: list[str] | None = Field(default=None, max_length=_TEXT_ITEMS)
    sheet: Sheet | None = None
    memo: Memo | None = None
    #: `updated_at` của bản đang sửa — có người lưu sau mốc này thì từ chối (409), không lưu đè.
    base_updated_at: str | None = Field(default=None, max_length=40)


class MoveStage(BaseModel):
    to: Literal["nhap", "du_thao", "to_trinh", "ap_dung"]
    base_updated_at: str | None = Field(default=None, max_length=40)


class MemoAi(BaseModel):
    memo: Memo | None = None   # nội dung đang sửa (chưa lưu); không gửi = bản đã lưu


def clean_paragraphs(items: list[str] | None) -> list[str] | None:
    """Đoạn diễn giải: bỏ đoạn rỗng, cắt độ dài. None giữ None (= dùng bản có sẵn)."""
    if items is None:
        return None
    return [s.strip()[:_TEXT_LEN] for s in items if isinstance(s, str) and s.strip()]
