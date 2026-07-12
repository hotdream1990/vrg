"""Data models cho Báo cáo phân tích thị trường cao su TUẦN.

Bảng số liệu (III.1/III.2/III.3) = trung bình tuần USD/tấn (quy đổi như bản tin ngày);
+/- và % tự tính. Các phần viết (I, II, III-nhận định, IV, V, VI) = list đoạn văn, AI dựng
nháp + người dùng sửa tay. Phần nào None/rỗng → template bỏ qua (không bịa).
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _abs(prev: float | None, curr: float | None) -> float | None:
    if prev is None or curr is None:
        return None
    return round(curr - prev, 1)


def _pct(prev: float | None, curr: float | None) -> float | None:
    if prev is None or curr is None or prev == 0:
        return None
    return round((curr - prev) / prev * 100, 2)


@dataclass
class ExchangeWeekRow:
    """Dòng bảng III.1 — giá sàn quốc tế (TB tuần, USD/tấn)."""

    exchange: str          # OSE | SHANGHAI | SGX | MRE
    grade: str             # RSS3 | TSR20 | SMR CV | SMR20 | LATEX
    prev: float | None = None
    curr: float | None = None

    @property
    def change_abs(self) -> float | None:
        return _abs(self.prev, self.curr)

    @property
    def change_pct(self) -> float | None:
        return _pct(self.prev, self.curr)


@dataclass
class PhysicalWeekRow:
    """Dòng bảng III.2 — giá thị trường giao ngay (TB tuần, USD/tấn)."""

    grade: str             # RSS3 | STR20 | SMR20 | LATEX
    prev: float | None = None
    curr: float | None = None

    @property
    def change_abs(self) -> float | None:
        return _abs(self.prev, self.curr)

    @property
    def change_pct(self) -> float | None:
        return _pct(self.prev, self.curr)


@dataclass
class MacroSection:
    """1 tiểu mục của Phần IV — Yếu tố vĩ mô (tiêu đề + các gạch đầu dòng)."""

    title: str                                  # "1. Thị trường Năng lượng..."
    bullets: list[str] = field(default_factory=list)


@dataclass
class WeeklyReportData:
    """Toàn bộ dữ liệu để generate 1 báo cáo tuần."""

    week_no: int                                # 26
    year: int                                   # 2026
    date_range: str                             # "22-26/6/2026" (nhãn bìa)
    prev_week_no: int                           # 25
    prev_year: int                              # 2026 (năm ISO tuần trước — khác year ở đầu năm)
    next_week_no: int                           # 27
    next_year: int                              # 2026 (năm ISO tuần sau — khác year ở cuối năm)
    prev_col_label: str                         # "Tuần 25 (15/6 - 19/6)"
    curr_col_label: str                         # "Tuần 26 (22/6 - 26/6)"

    # Phần I — Tóm tắt tuần trước
    summary_prev: list[str] = field(default_factory=list)
    # Phần II — Diễn biến tuần báo cáo
    movement: list[str] = field(default_factory=list)

    # Phần III.1 — Bảng sàn quốc tế + nhận định
    exchange_rows: list[ExchangeWeekRow] = field(default_factory=list)
    exchange_notes: list[str] = field(default_factory=list)
    # Phần III.2 — Bảng giao ngay + nhận định
    physical_rows: list[PhysicalWeekRow] = field(default_factory=list)
    physical_notes: list[str] = field(default_factory=list)
    # Phần III.3 — Mủ nước nội địa (biên độ VNĐ/độ TSC) + nhận định
    latex_prev: str | None = None               # "538 – 583"
    latex_curr: str | None = None               # "538 - 605"
    latex_change: str | None = None             # "0 /+22"
    latex_notes: list[str] = field(default_factory=list)

    # Phần IV — Yếu tố vĩ mô (nhiều tiểu mục)
    macro: list[MacroSection] = field(default_factory=list)
    # Phần V — Dự báo tuần tới
    forecast: list[str] = field(default_factory=list)
    # Phần VI — Kết luận & khuyến nghị
    conclusion: list[str] = field(default_factory=list)
