"""Schema Hỗ trợ & Thông báo · Nhắc lịch."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.entry_types import DEFAULT_AUDIENCE, clean_audience
from app.services.support_reminder_repo import REPEAT_RULES, SCOPES

_MAX_SUBJECT = 200
_MAX_BODY = 20000
_MAX_FILES = 10


class Attachment(BaseModel):
    """File đính kèm đã upload trước qua `/api/support/file` (tên lưu + tên gốc để hiển thị)."""

    file: str = Field(max_length=200)
    filename: str = Field(default="", max_length=200)
    size: int | None = None


def _clean_files(v: list[Attachment]) -> list[Attachment]:
    if len(v) > _MAX_FILES:
        raise ValueError(f"Tối đa {_MAX_FILES} file đính kèm mỗi tin.")
    return v


def _default_audience() -> list[str]:
    return list(DEFAULT_AUDIENCE)


class UnitRequestCreate(BaseModel):
    """Đơn vị (lãnh đạo / chuyên viên nhập liệu) mở một yêu cầu hỗ trợ gửi Tập đoàn.

    Không có ô người nhận: server tự tính = lãnh đạo + loại nhập liệu của người gửi."""

    company: str = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=_MAX_SUBJECT)
    body: str = Field(default="", max_length=_MAX_BODY)
    files: list[Attachment] = Field(default_factory=list)

    _files = field_validator("files")(_clean_files)


class AnnounceCreate(BaseModel):
    """Tập đoàn gửi thông báo xuống 1 đơn vị · một nhóm · tất cả."""

    subject: str = Field(min_length=1, max_length=_MAX_SUBJECT)
    body: str = Field(default="", max_length=_MAX_BODY)
    files: list[Attachment] = Field(default_factory=list)
    scope: str = "all"                 # all | units | region
    units: list[str] = Field(default_factory=list)
    region: str | None = None
    #: Nhóm người nhận trong đơn vị: leader · purchase · stock · contract (chọn nhiều). Lọc về danh
    #: mục chuẩn ở đây; rỗng sau khi lọc thì router trả 400 (thông điệp rõ hơn lỗi 422).
    audience: list[str] = Field(default_factory=_default_audience)

    _files = field_validator("files")(_clean_files)
    _audience = field_validator("audience")(clean_audience)

    @field_validator("scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v not in SCOPES:
            raise ValueError("Phạm vi gửi không hợp lệ.")
        return v


class ReplyCreate(BaseModel):
    body: str = Field(default="", max_length=_MAX_BODY)
    files: list[Attachment] = Field(default_factory=list)

    _files = field_validator("files")(_clean_files)


class StatusUpdate(BaseModel):
    status: str  # open | closed

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in ("open", "closed"):
            raise ValueError("Trạng thái không hợp lệ.")
        return v


class ReminderEdit(BaseModel):
    """Lịch nhắc — phạm vi giống thông báo, thêm chu kỳ + mốc phát kế tiếp."""

    title: str = Field(min_length=1, max_length=_MAX_SUBJECT)
    body: str = Field(default="", max_length=_MAX_BODY)
    files: list[Attachment] = Field(default_factory=list)
    scope: str = "all"
    units: list[str] = Field(default_factory=list)
    region: str | None = None
    repeat_rule: str = "once"
    next_at: datetime
    enabled: bool = True
    audience: list[str] = Field(default_factory=_default_audience)

    _files = field_validator("files")(_clean_files)
    _audience = field_validator("audience")(clean_audience)

    @field_validator("scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v not in SCOPES:
            raise ValueError("Phạm vi gửi không hợp lệ.")
        return v

    @field_validator("repeat_rule")
    @classmethod
    def _repeat(cls, v: str) -> str:
        if v not in REPEAT_RULES:
            raise ValueError("Chu kỳ nhắc không hợp lệ.")
        return v
