"""Schema Trợ lý AI — hội thoại hỏi đáp số liệu nội bộ."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)  # lịch sử hội thoại, cũ→mới
    #: Gói kỹ năng người dùng chọn trong phiên chat. None = dùng mọi gói tài khoản được phép.
    packs: list[str] | None = Field(default=None, max_length=10)
    #: Mức tư vấn — giới hạn Trợ lý được đi xa tới đâu (chỉ tra số · theo mô hình · có điều chỉnh).
    advice: Literal["data", "model", "adjusted"] = "model"
    #: Mã phiên chat do frontend sinh, để gom các lượt vào cùng một hội thoại trong nhật ký.
    session_id: str | None = Field(default=None, max_length=64)
