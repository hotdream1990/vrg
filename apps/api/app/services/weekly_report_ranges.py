"""Cao/thấp CẢ KỲ báo cáo tuần (không gồm tuần mốc) — tính TỪ DATA để AI không bịa đỉnh/đáy.

Hàm thuần: nhận chuỗi ngày → (USD/tấn, nội tệ). Chỉ xét Thứ 2–6 (khớp TB tuần). Ngày 'dd/mm' 2 chữ
số (bám mẫu "27/08"); kèm số tuần của ngày đó và giá nội tệ tại đúng ngày đó. Hai ngày bằng giá →
lấy ngày SỚM hơn. Ngày có giá nội tệ nhưng thiếu tỷ giá KHÔNG vào cao/thấp USD (không đắp tỷ giá ngày
khác) — liệt kê ở `no_fx_dates` để nhận định ghi kèm.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.weekly_report_tables import is_price

Points = dict[str, tuple[Any, Any]]  # ngày ISO → (USD/tấn, giá nội tệ | None)

_SATURDAY = 5


def ddmm(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def week_no_of(iso: str, weeks: list[dict[str, Any]]) -> int | None:
    return next((w["week_no"] for w in weeks if w["mon"] <= iso <= w["fri"]), None)


def _in_span(iso: str, lo: str, hi: str) -> bool:
    return lo <= iso <= hi and date.fromisoformat(iso).weekday() < _SATURDAY


def range_stat(exchange: str | None, grade: str, points: Points, weeks: list[dict[str, Any]],
               native_unit: str | None = None, no_fx_days: list[str] | None = None) -> dict[str, Any] | None:
    """`weeks` = các tuần TRONG KỲ. None nếu cả kỳ không có giá USD nào."""
    if not weeks:
        return None
    lo_d, hi_d = weeks[0]["mon"], weeks[-1]["fri"]
    pts = sorted((d, float(u), n) for d, (u, n) in points.items() if _in_span(d, lo_d, hi_d) and is_price(u))
    if not pts:
        return None
    hi = max(pts, key=lambda p: p[1])   # max/min trả phần tử ĐẦU TIÊN khi bằng nhau → ngày sớm hơn
    lo = min(pts, key=lambda p: p[1])
    return {
        "exchange": exchange, "grade": grade,
        "high": hi[1], "high_date": ddmm(hi[0]), "high_week_no": week_no_of(hi[0], weeks),
        "high_native": hi[2] if native_unit else None,
        "low": lo[1], "low_date": ddmm(lo[0]), "low_week_no": week_no_of(lo[0], weeks),
        "low_native": lo[2] if native_unit else None,
        "native_unit": native_unit,
        "no_fx_dates": [ddmm(d) for d in sorted(no_fx_days or []) if _in_span(d, lo_d, hi_d)],
    }
