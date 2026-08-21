"""Chuỗi TIÊU THỤ theo ngày (Command Center · Bản tin biến động).

Nguồn số DUY NHẤT là các **lần giao của hợp đồng bán hàng** — đúng nguồn màn "Thống kê tiêu thụ"
dùng, nên hai màn không bao giờ lệch nhau. Xem được theo: khu vực · công ty · chủng loại · loại
hợp đồng · hình thức hợp đồng.

Mỗi ngày trả kèm **doanh thu quy VNĐ**: dòng bán bằng USD mà thiếu tỷ giá thì KHÔNG được đoán —
sản lượng vẫn tính, doanh thu bỏ qua dòng đó và đếm vào `revenue_missing_lines` để nói rõ ra.
"""

from __future__ import annotations

from typing import Any

from app.services import unit_report_rows
from app.services.unit_series import days_between, series_of
from app.services.unit_report_query import GROUPERS

#: Các cách chia dùng được cho chuỗi ngày (không có `day`/`source`: một cái là chính trục X,
#: cái kia đã bỏ từ 30/07/2026 khi tiêu thụ chuyển sang tính từ hợp đồng).
GROUPS = ("region", "company", "grade", "contract", "channel")

#: Nhóm ít nhãn (loại/hình thức hợp đồng) thì vẽ hết, không gộp "Khác" — gộp là mất luôn ý nghĩa.
_NO_PACK = ("contract", "channel")


def consumption_series(date_from: str, date_to: str, group_by: str = "region") -> dict[str, Any]:
    """Sản lượng tiêu thụ từng ngày (tấn) + doanh thu (VNĐ), chia theo `group_by`."""
    group_by = group_by if group_by in GROUPS else "region"
    key_of = GROUPERS[group_by]
    rows_src = unit_report_rows.consumption_rows(date_from, date_to)["rows"]

    per_day: dict[str, dict[str, float]] = {}
    revenue: dict[str, float] = {}
    missing: dict[str, int] = {}
    totals: dict[str, float] = {}
    for r in rows_src:
        day, qty = r.get("as_of"), r.get("qty") or 0.0
        if not day or not qty:
            continue                       # chưa khai ngày giao / dòng 0 tấn: không có gì để vẽ
        key = key_of(r) or "Chưa khai"
        slot = per_day.setdefault(day, {})
        slot[key] = slot.get(key, 0.0) + qty
        totals[key] = totals.get(key, 0.0) + qty
        if r.get("revenue_vnd") is not None:
            revenue[day] = revenue.get(day, 0.0) + r["revenue_vnd"]
        else:
            missing[day] = missing.get(day, 0) + 1

    rows = [{"as_of": day, "total": round(sum(per_day[day].values()), 3),
             "revenue_vnd": round(revenue.get(day, 0.0), 0) or None,
             "revenue_missing_lines": missing.get(day, 0),
             "values": {k: round(v, 3) for k, v in per_day[day].items()}}
            for day in days_between(date_from, date_to) if per_day.get(day)]

    series = series_of(rows) if group_by in _NO_PACK else series_of(rows, totals)
    return {"date_from": date_from, "date_to": date_to, "group_by": group_by,
            "series": series, "rows": rows}
