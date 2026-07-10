"""Schema Bản tin biến động — sinh nhận định AI theo từng nhóm số liệu + tổng thể.

Frontend gom tóm tắt số liệu mỗi nhóm (đã tính sẵn xu hướng/%thay đổi) rồi POST lên; backend
chỉ dựng prompt + gọi LLM + parse JSON. Không lưu (bấm-tạo-mới mỗi lần).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GroupInput(BaseModel):
    """1 nhóm số liệu do frontend gửi lên để AI nhận định."""

    key: str                       # định danh nhóm (exchanges, physical, fx, inventory, floor, raw)
    label: str                     # nhãn hiển thị tiếng Việt
    summary: str = ""              # tóm tắt số liệu dạng text (đã tính sẵn ở frontend)


class AssessmentRequest(BaseModel):
    """Payload sinh nhận định: danh sách nhóm số liệu."""

    groups: list[GroupInput] = Field(default_factory=list)


class GroupAssessment(BaseModel):
    """Nhận định AI cho 1 nhóm."""

    key: str
    label: str
    assessment: str = ""


class AssessmentResult(BaseModel):
    """Kết quả: nhận định từng nhóm + đoạn tổng thể."""

    groups: list[GroupAssessment] = Field(default_factory=list)
    overall: str = ""
    generated_at: str = ""
