"""Schema Báo cáo phân tích thị trường TUẦN (v2 — kỳ gộp 1–3 tuần).

Bảng III.1/III.2 = TB tuần USD/tấn theo từng cột tuần (auto, read-only); III.3 mủ nước = biên độ
từng tuần (auto, ghi đè từng ô). Các phần viết (narrative) = list đoạn văn, AI dựng nháp + người
dùng sửa. Payload lưu narrative + override; bảng luôn dựng lại từ dữ liệu giá.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeekCol(BaseModel):
    """1 cột tuần — [0] là tuần mốc so sánh, sau đó các tuần trong kỳ."""

    week_no: int
    year: int
    mon: str                               # '2026-08-24'
    fri: str
    label: str                             # 'Tuần 35 (24/8 - 28/8)'
    short: str                             # 'T35'
    range: str                             # '24/8 – 28/8/2026'


class WeekTableRow(BaseModel):
    """1 dòng bảng III.1/III.2 (TB tuần; prev/curr/change_* = cặp tuần CUỐI)."""

    exchange: str | None = None            # OSE | SHANGHAI | SGX | MRE (None cho III.2)
    grade: str
    values: list[float | None] = Field(default_factory=list)       # len = len(weeks)
    changes: list[float | None] = Field(default_factory=list)      # len - 1, 1 số lẻ
    changes_pct: list[float | None] = Field(default_factory=list)  # len - 1, 2 số lẻ
    prev: float | None = None
    curr: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None


class RangeStat(BaseModel):
    """Cao/thấp CẢ KỲ (không gồm tuần mốc) + ngày + tuần + giá nội tệ ngày đó."""

    exchange: str | None = None
    grade: str
    high: float
    high_date: str                         # 'dd/mm'
    high_week_no: int | None = None
    high_native: float | None = None
    low: float
    low_date: str
    low_week_no: int | None = None
    low_native: float | None = None
    native_unit: str | None = None         # 'JPY/kg' | 'CNY/tấn' | 'US cent/kg' | None
    # Ngày 'dd/mm' có giá nội tệ nhưng thiếu tỷ giá → không vào cao/thấp USD (sàn vẫn giao dịch).
    no_fx_dates: list[str] = Field(default_factory=list)


class FxRow(BaseModel):
    """Tỷ giá TB tuần (chỉ ngày có giá sàn, đúng ngày — không carry-forward)."""

    pair: str
    values: list[float | None] = Field(default_factory=list)
    changes: list[float | None] = Field(default_factory=list)
    changes_pct: list[float | None] = Field(default_factory=list)


class MacroSection(BaseModel):
    """1 tiểu mục Phần IV — tiêu đề (sửa được) + gạch đầu dòng (sửa tay/AI)."""

    title: str
    bullets: list[str] = Field(default_factory=list)


class WeeklyNarrative(BaseModel):
    """Phần viết (editable) + cấu hình kỳ — lưu trong payload."""

    span_weeks: int = Field(default=1, ge=1, le=3)           # số tuần gộp
    report_note: list[str] = Field(default_factory=list)     # "Ghi chú:" dưới masthead
    summary_prev: list[str] = Field(default_factory=list)    # I
    movement: list[str] = Field(default_factory=list)        # II
    exchange_table_notes: list[str] = Field(default_factory=list)  # ghi chú tay dưới bảng III.1
    exchange_notes: list[str] = Field(default_factory=list)  # III.1 nhận định
    physical_table_notes: list[str] = Field(default_factory=list)  # ghi chú tay dưới bảng III.2
    physical_notes: list[str] = Field(default_factory=list)  # III.2 nhận định
    latex_notes: list[str] = Field(default_factory=list)     # III.3 nhận định
    macro: list[MacroSection] = Field(default_factory=list)  # IV
    forecast: list[str] = Field(default_factory=list)        # V
    conclusion: list[str] = Field(default_factory=list)      # VI
    # Ghi đè III.3 theo từng cột tuần — phần tử None/"" = dùng số tự tính (KHÔNG lưu seed).
    latex_override: list[str | None] | None = None           # len = len(weeks)
    latex_change_override: list[str | None] | None = None    # len = len(weeks) - 1
    # Trường v1 — chỉ để đọc báo cáo cũ (span 1, chưa có list override thì map sang override).
    latex_prev: str | None = None
    latex_curr: str | None = None
    latex_change: str | None = None


class WeeklyReport(BaseModel):
    """Báo cáo tuần đầy đủ (bảng auto + narrative). GET/PUT trả cái này."""

    week_key: str                          # '2026-08-24' (Thứ 2 ISO tuần ĐẦU kỳ)
    week_no: int
    year: int
    span_weeks: int = 1
    weeks: list[WeekCol] = Field(default_factory=list)
    last_week_no: int
    last_year: int
    date_range: str                        # '24/8/2026 – 4/9/2026'
    prev_week_no: int
    prev_year: int                         # năm ISO tuần mốc (khác year ở đầu năm)
    next_week_no: int
    next_year: int                         # năm ISO tuần sau kỳ (khác year ở cuối năm)
    prev_col_label: str                    # 'Tuần 34 (17/8 - 21/8)'
    curr_col_label: str                    # cột tuần cuối kỳ
    title_label: str                       # 'Tuần 35 và 36 năm 2026'
    span_label: str                        # '35-36/2026'
    prev_label: str
    movement_label: str
    next_label: str
    list_label: str
    exchange_rows: list[WeekTableRow] = Field(default_factory=list)
    physical_rows: list[WeekTableRow] = Field(default_factory=list)
    exchange_gaps: list[str] = Field(default_factory=list)
    physical_gaps: list[str] = Field(default_factory=list)
    range_stats: list[RangeStat] = Field(default_factory=list)
    physical_range_stats: list[RangeStat] = Field(default_factory=list)
    fx_rows: list[FxRow] = Field(default_factory=list)
    latex_bands: list[str | None] = Field(default_factory=list)
    latex_changes: list[str | None] = Field(default_factory=list)
    # Số TỰ TÍNH III.3 theo dữ liệu hiện tại (bất kể ghi đè) — để báo "đang dùng số đã lưu".
    latex_auto_bands: list[str | None] = Field(default_factory=list)
    latex_auto_changes: list[str | None] = Field(default_factory=list)
    latex_prev: str | None = None
    latex_curr: str | None = None
    latex_change: str | None = None
    narrative: WeeklyNarrative = Field(default_factory=WeeklyNarrative)


class WeeklyReportSummary(BaseModel):
    """Dòng danh sách báo cáo đã lưu."""

    week_key: str
    week_no: int
    year: int
    span_weeks: int = 1
    label: str                             # 'Tuần 35-36/2026 (24/8/2026 – 4/9/2026)'
    updated: str | None = None


class AiAssistRequest(BaseModel):
    """Yêu cầu AI dựng nháp cho 1 phần."""

    section: str                           # summary_prev|movement|exchange_notes|...|macro:<i>|forecast|conclusion


class AiAssistResult(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)        # số không đối chiếu được với dữ liệu
    absolute_words: list[str] = Field(default_factory=list)  # từ tuyệt đối cần tránh


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
    warnings: dict[str, list[str]] = Field(default_factory=dict)        # key = field hoặc 'macro:<i>'
    absolute_words: dict[str, list[str]] = Field(default_factory=dict)


class WeeklyConsistencyResult(BaseModel):
    """Soát chữ nhận định với dữ liệu hiện tại — chỉ cảnh báo, không sửa/ghi gì."""

    warnings: dict[str, list[str]] = Field(default_factory=dict)   # field | 'macro:<i>' | 'latex_bands'
    count: int = 0
    summary: str = ""
