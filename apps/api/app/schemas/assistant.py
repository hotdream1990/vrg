"""Schema Trợ lý AI — hội thoại hỏi đáp số liệu nội bộ."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)  # lịch sử hội thoại, cũ→mới
