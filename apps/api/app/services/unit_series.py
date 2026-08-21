"""Khung chung cho các chuỗi số liệu THEO NGÀY dựng từ biểu đơn vị thành viên đã nhập.

Phục vụ Command Center / Bản tin biến động — nơi cần *diễn biến* chứ không phải bảng lọc như màn
"Thống kê số liệu". Ba miền số liệu dùng chung khung này:

- `unit_series_purchase.py`    — thu mua: đơn giá + sản lượng (mủ nước · mủ chén).
- `unit_series_stock.py`       — tồn kho: cơ cấu hợp đồng · chủng loại · khu vực · tồn tự do.
- `unit_series_consumption.py` — tiêu thụ: khu vực · công ty · chủng loại · loại/hình thức hợp đồng.

Mọi chuỗi trả cùng một khuôn để web dùng chung một biểu đồ cột chồng:
`{series: [{key, label}], rows: [{as_of, total, values: {key: số}}]}`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

#: Cửa sổ hiển thị mặc định / tối đa (ngày). Chuỗi tồn kho hỏi hợp đồng 1 lần cho MỖI ngày nên
#: cửa sổ phải có trần, không để màn hình kéo theo cả năm.
DEFAULT_WINDOW_DAYS = 60
MAX_WINDOW_DAYS = 180


def days_between(date_from: str, date_to: str) -> list[str]:
    a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def window(date_from: str | None, date_to: str | None, *, start_floor: str | None = None,
           default_days: int = DEFAULT_WINDOW_DAYS) -> tuple[str, str]:
    """Khoảng ngày đã kẹp: mặc định `default_days` ngày gần nhất, trần `MAX_WINDOW_DAYS`."""
    from app.core.edit_window import today

    end = date.fromisoformat(date_to) if date_to else today()
    start = date.fromisoformat(date_from) if date_from else end - timedelta(days=default_days - 1)
    if start_floor:
        start = max(start, date.fromisoformat(start_floor))
    start = max(start, end - timedelta(days=MAX_WINDOW_DAYS - 1))
    if start > end:
        start = end
    return start.isoformat(), end.isoformat()



def num(v: Any) -> float | None:
    """Số hoặc None (payload jsonb có thể chứa chuỗi/None)."""
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


#: Số nhóm vẽ riêng trên một biểu đồ cột chồng; phần đuôi gộp `OTHER_KEY` cho đọc được.
#: Vượt ngần này thì chú giải dài hơn cả biểu đồ và các dải màu mỏng đến mức không phân biệt nổi.
MAX_KEYS = 8
OTHER_KEY = "Khác"


def top_keys(totals: dict[str, float], limit: int = MAX_KEYS) -> list[str]:
    """Các nhóm lớn nhất theo tổng cả kỳ (đã sắp tên), phần đuôi thành `OTHER_KEY`."""
    ranked = [k for k, _ in sorted(totals.items(), key=lambda kv: -kv[1])]
    if len(ranked) <= limit:
        return sorted(ranked)
    return sorted(ranked[:limit]) + [OTHER_KEY]


def pack_rows(rows: list[dict[str, Any]], keys: list[str]) -> None:
    """Gộp các nhóm ngoài `keys` vào `OTHER_KEY` ngay trên từng ngày (sửa tại chỗ)."""
    head = set(keys)
    for r in rows:
        merged: dict[str, float] = {}
        for k, v in r["values"].items():
            slot = k if k in head else OTHER_KEY
            merged[slot] = merged.get(slot, 0.0) + v
        r["values"] = {k: round(v, 3) for k, v in merged.items()}


def series_of(rows: list[dict[str, Any]], totals: dict[str, float] | None = None,
              limit: int = MAX_KEYS) -> list[dict[str, str]]:
    """Danh sách nhóm cho chú giải; có `totals` thì cắt top và gộp đuôi ngay trên `rows`."""
    if totals is None:
        return [{"key": k, "label": k} for k in sorted({k for r in rows for k in r["values"]})]
    keys = top_keys(totals, limit)
    pack_rows(rows, keys)
    return [{"key": k, "label": k} for k in keys]
