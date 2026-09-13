"""Data models cho Báo cáo phân tích thị trường cao su TUẦN (v2 — kỳ 1 tuần hoặc gộp 2–3 tuần).

Bảng số liệu (III.1/III.2) = trung bình tuần USD/tấn; mỗi dòng có `values` theo từng cột tuần
(`weeks[0]` = tuần mốc so sánh, `weeks[1..n]` = các tuần trong kỳ). +/- và % của từng cặp tuần
liền nhau tự tính (nửa LÊN, như bulletin.convert). Các phần viết (I, II, nhận định, IV, V, VI) =
list dòng chữ, AI dựng nháp + người dùng sửa tay; phần nào rỗng → template bỏ qua (không bịa).

Quy ước dữ liệu: giá 0 = No Trading → coi như thiếu (không đem vào phép tính +/-, %).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


def _half_up(x: float, places: str) -> float:
    return float(Decimal(str(x)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _missing(x: float | None) -> bool:
    return x is None or x == 0


@dataclass
class WeekCol:
    """1 cột tuần của bảng."""

    week_no: int                                # 35
    year: int                                   # 2026
    label: str                                  # 'Tuần 35 (24/8 - 28/8)'


@dataclass
class TableRow:
    """Dòng bảng III.1 (sàn quốc tế, có `exchange`) hoặc III.2 (giao ngay, `exchange` = None)."""

    exchange: str | None                        # OSE | SHANGHAI | SGX | MRE | None
    grade: str                                  # RSS3 | TSR20 | SMR CV | SMR20 | LATEX | STR20
    values: list[float | None] = field(default_factory=list)  # len = len(weeks)

    @property
    def changes(self) -> list[float | None]:
        """+/- từng cặp tuần liền nhau (1 số lẻ)."""
        v = self.values
        return [None if _missing(a) or _missing(b) else _half_up(b - a, "0.1")
                for a, b in zip(v, v[1:])]

    @property
    def changes_pct(self) -> list[float | None]:
        """% thay đổi từng cặp tuần liền nhau (2 số lẻ)."""
        v = self.values
        return [None if _missing(a) or _missing(b) else _half_up((b - a) / a * 100, "0.01")
                for a, b in zip(v, v[1:])]


@dataclass
class MacroSection:
    """1 tiểu mục của Phần IV — Yếu tố vĩ mô (tiêu đề + các dòng gạch đầu dòng)."""

    title: str                                  # "2. Cung – Cầu:"
    bullets: list[str] = field(default_factory=list)


@dataclass
class WeeklyReportData:
    """Toàn bộ dữ liệu để generate 1 báo cáo tuần (1 kỳ)."""

    title_label: str                            # 'Tuần 35 và 36 năm 2026'
    date_range: str                             # '24/8/2026 – 4/9/2026'
    span_label: str                             # '35-36/2026'
    prev_label: str                             # 'Tuần 34/2026 (17/8 – 21/8/2026)'
    movement_label: str                         # 'Tuần 35-36/2026 (24/8 – 4/9/2026)'
    next_label: str                             # 'Tuần 37/2026'
    weeks: list[WeekCol]                        # [tuần mốc, tuần 1..n]
    report_note: list[str] = field(default_factory=list)   # "Ghi chú:" dưới masthead

    # Phần I — Tóm tắt tuần mốc · Phần II — Diễn biến kỳ báo cáo
    summary_prev: list[str] = field(default_factory=list)
    movement: list[str] = field(default_factory=list)

    # Phần III.1 — Sàn quốc tế: bảng + ghi chú dưới bảng (gaps auto, notes tay) + nhận định
    exchange_rows: list[TableRow] = field(default_factory=list)
    exchange_gaps: list[str] = field(default_factory=list)
    exchange_table_notes: list[str] = field(default_factory=list)
    exchange_notes: list[str] = field(default_factory=list)
    # Phần III.2 — Giao ngay
    physical_rows: list[TableRow] = field(default_factory=list)
    physical_gaps: list[str] = field(default_factory=list)
    physical_table_notes: list[str] = field(default_factory=list)
    physical_notes: list[str] = field(default_factory=list)
    # Phần III.3 — Mủ nước nội địa (biên độ VNĐ/độ TSC): len(weeks) · len(weeks)-1
    latex_bands: list[str | None] = field(default_factory=list)
    latex_changes: list[str | None] = field(default_factory=list)
    latex_notes: list[str] = field(default_factory=list)

    # Phần IV — Yếu tố vĩ mô · V — Dự báo · VI — Kết luận & khuyến nghị
    macro: list[MacroSection] = field(default_factory=list)
    forecast: list[str] = field(default_factory=list)
    conclusion: list[str] = field(default_factory=list)
