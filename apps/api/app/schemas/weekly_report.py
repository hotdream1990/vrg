"""Schema Báo cáo phân tích thị trường TUẦN.

Bảng III.1/III.2 = TB tuần USD/tấn (auto, read-only); III.3 mủ nước = min–max tuần (auto-seed,
sửa được). Các phần viết (narrative) = list đoạn văn, AI dựng nháp + người dùng sửa. Draft lưu
narrative + override III.3; bảng luôn dựng lại từ dữ liệu giá.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeekTableRow(BaseModel):
    """1 dòng bảng III.1/III.2 (TB tuần, đã tính +/- và %)."""

    exchange: str | None = None            # OSE | SHANGHAI | SGX | MRE (None cho III.2)
    grade: str
    prev: float | None = None
    curr: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None


class MacroSection(BaseModel):
    """1 tiểu mục Phần IV — tiêu đề + gạch đầu dòng (sửa tay/AI)."""

    title: str
    bullets: list[str] = Field(default_factory=list)


class WeeklyNarrative(BaseModel):
    """Phần viết (editable) — lưu trong draft."""

    summary_prev: list[str] = Field(default_factory=list)   # I
    movement: list[str] = Field(default_factory=list)        # II
    exchange_notes: list[str] = Field(default_factory=list)  # III.1 nhận định
    physical_notes: list[str] = Field(default_factory=list)  # III.2 nhận định
    latex_notes: list[str] = Field(default_factory=list)     # III.3 nhận định
    macro: list[MacroSection] = Field(default_factory=list)  # IV
    forecast: list[str] = Field(default_factory=list)        # V
    conclusion: list[str] = Field(default_factory=list)      # VI
    # Override bảng III.3 (biên độ mủ nước) — auto-seed min–max, cho sửa
    latex_prev: str | None = None
    latex_curr: str | None = None
    latex_change: str | None = None


class WeeklyReport(BaseModel):
    """Báo cáo tuần đầy đủ (bảng auto + narrative). GET trả cái này."""

    week_key: str                          # '2026-06-22' (Thứ 2 ISO)
    week_no: int
    year: int
    date_range: str                        # '22-26/6/2026'
    prev_week_no: int
    prev_year: int                         # năm ISO tuần trước (khác year ở đầu năm)
    next_week_no: int
    next_year: int                         # năm ISO tuần sau (khác year ở cuối năm)
    prev_col_label: str                    # 'Tuần 25 (15/6 - 19/6)'
    curr_col_label: str                    # 'Tuần 26 (22/6 - 26/6)'
    exchange_rows: list[WeekTableRow] = Field(default_factory=list)
    physical_rows: list[WeekTableRow] = Field(default_factory=list)
    latex_prev: str | None = None
    latex_curr: str | None = None
    latex_change: str | None = None
    narrative: WeeklyNarrative = Field(default_factory=WeeklyNarrative)


class WeeklyReportSummary(BaseModel):
    """Dòng danh sách báo cáo đã lưu."""

    week_key: str
    week_no: int
    year: int
    label: str                             # 'Tuần 26/2026 (22-26/6/2026)'
    updated: str | None = None


class AiAssistRequest(BaseModel):
    """Yêu cầu AI dựng nháp cho 1 phần."""

    section: str                           # summary_prev|movement|exchange_notes|...|macro|forecast|conclusion


class AiAssistResult(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class WeeklyAiSections(BaseModel):
    """Các phần viết AI sinh (KHÔNG gồm biên độ III.3)."""

    summary_prev: list[str] = Field(default_factory=list)
    movement: list[str] = Field(default_factory=list)
    exchange_notes: list[str] = Field(default_factory=list)
    physical_notes: list[str] = Field(default_factory=list)
    latex_notes: list[str] = Field(default_factory=list)
    macro: list[MacroSection] = Field(default_factory=list)
    forecast: list[str] = Field(default_factory=list)
    conclusion: list[str] = Field(default_factory=list)


class AiAssistAllResult(BaseModel):
    sections: WeeklyAiSections
    source_urls: list[str] = Field(default_factory=list)
