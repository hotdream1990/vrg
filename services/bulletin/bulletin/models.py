"""Data models cho bulletin input.

BulletinData gom toàn bộ dữ liệu cần thiết để fill vào template PPTX.
Phần nào chưa có dữ liệu (None) sẽ giữ nguyên nội dung template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .convert import is_no_trading


def _delta(prev: int | None, curr: int | None) -> tuple[int | None, float | None]:
    """(thay đổi tuyệt đối, %) giữa 2 phiên — bỏ trống nếu một trong hai là No Trading.

    Phiên không giao dịch KHÔNG phải mức giá 0, nên không được so với phiên có giá
    (nếu không cột thay đổi in ra '-2,739 / -100%' vô nghĩa).
    """
    if prev is None or curr is None or is_no_trading(prev) or is_no_trading(curr):
        return None, None
    return curr - prev, round((curr - prev) / prev * 100, 1)


@dataclass
class WorldPriceRow:
    """Một dòng giá CSTN thế giới (Slide 2, Table 1)."""

    exchange: str   # OSE | SHANGHAI | SGX | MRE
    grade: str      # RSS3 | TSR20 | SMRCV | SMR20 | LATEX
    unit: str       # luôn USD/T trong bản tin
    price_prev: int | None = None
    price_curr: int | None = None

    @property
    def change_abs(self) -> int | None:
        return _delta(self.price_prev, self.price_curr)[0]

    @property
    def change_pct(self) -> float | None:
        return _delta(self.price_prev, self.price_curr)[1]


@dataclass
class PhysicalPriceRow:
    """Một dòng giá physical/ANRPC (Slide 2, Table 2)."""

    grade: str      # RSS3 | STR20 | SMR20 | SIR20 | Thai Latex 60% (Bulk) | (Drums)
    price_prev: int | None = None
    price_curr: int | None = None

    @property
    def change_abs(self) -> int | None:
        return _delta(self.price_prev, self.price_curr)[0]

    @property
    def change_pct(self) -> float | None:
        return _delta(self.price_prev, self.price_curr)[1]


@dataclass
class VrgFloorRow:
    """Một dòng giá sàn VRG (Slide 3, Table 3)."""

    grade: str             # SVR CV 50, SVR CV60, SVR L, ...
    fob_usd: int | None = None
    domestic_vnd: int | None = None


@dataclass
class BulletinData:
    """Toàn bộ dữ liệu đầu vào để generate bản tin ngày."""

    report_date: date          # ngày bản tin (T-1)
    prev_date: date            # ngày liền trước (T-2)

    # Section I — Giá CSTN thế giới (Slide 2, Table 1)
    # Thứ tự cố định: OSE-RSS3, SHFE-RSS3, SGX-RSS3, SGX-TSR20, MRE-SMRCV, MRE-SMR20, MRE-LATEX
    world_prices: list[WorldPriceRow] = field(default_factory=list)

    # Section II — Giá physical/ANRPC (Slide 2, Table 2)
    # Thứ tự: RSS3, STR20, SMR20, SIR20, Thai Latex Bulk, Thai Latex Drums
    physical_prices: list[PhysicalPriceRow] = field(default_factory=list)
    # Ngày cột riêng cho physical = 2 phiên vật chất THẬT gần nhất (có thể cũ hơn report_date).
    # None → fallback report_date/prev_date như cũ.
    physical_prev_date: date | None = None
    physical_curr_date: date | None = None

    # Section III — Giá trong nước (Slide 3)
    vrg_floor_prev_label: str | None = None     # "Giá sàn lần 13\n(27/05/2026)"
    vrg_floor_curr_label: str | None = None     # "Giá sàn lần 14\n(09/06/2026)"
    vrg_floor_prev: list[VrgFloorRow] = field(default_factory=list)
    vrg_floor_curr: list[VrgFloorRow] = field(default_factory=list)
    raw_material_regions: dict[str, str] = field(default_factory=dict)

    # Section IV — Thông tin thị trường (Slide 4-5)
    # Mỗi phần tử = 1 đoạn văn (paragraph)
    market_exchange_summary: list[str] = field(default_factory=list)
    market_physical_summary: str | None = None
    market_analysis: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
