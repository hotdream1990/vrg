"""Kiểm độ tươi tỷ giá — ĐỘC LẬP với crawler (nhìn thẳng vào kho giá, không tin trạng thái nguồn).

Bối cảnh (09/2026): USD/JPY·CNY·THB chết 11 ngày mà không ai biết — crawler tỷ giá vẫn báo OK vì
VND/MYR còn lấy được, ghi chú lỗi chỉ nằm trong JSON. Cách chắc nhất để bắt MỌI kiểu hỏng (nguồn đổi
giao diện, bị chặn, parse sai, trả trang cũ…) là hỏi kho: ngày mới nhất của từng cặp là bao giờ.

Quy ước "quá cũ": số NGÀY LÀM VIỆC (Thứ 2–6) sau ngày mới nhất, tính tới hôm nay (giờ VN) ≥ ngưỡng.
x-rates chỉ có giá đóng cửa ngày D từ ~07:00 sáng D+1, nên sáng thứ Hai mới có số thứ Sáu là bình
thường (trễ 1) — ngưỡng mặc định 3. Không xét ngày lễ riêng (ngưỡng 3 đã chừa được 1 ngày lễ).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.db import session_scope
from app.core.market_meta import FX_PAIRS

THRESHOLD_KEY = "FX_STALE_BUSINESS_DAYS"
DEFAULT_THRESHOLD = 3
FX_SOURCE = "fx"

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def now_vn() -> datetime:
    return datetime.now(_TZ)


def today_vn() -> date:
    return now_vn().date()


def business_days_after(latest: date, today: date) -> int:
    """Số ngày Thứ 2–6 nằm trong (latest, today]. `today` ≤ `latest` → 0."""
    days = (today - latest).days
    if days <= 0:
        return 0
    weeks, rest = divmod(days, 7)
    # Cộng trọn tuần không đổi thứ → phần lẻ xét đúng các ngày latest+1 … latest+rest.
    return weeks * 5 + sum(1 for i in range(1, rest + 1) if (latest + timedelta(days=i)).weekday() < 5)


def parse_threshold(raw: str | None) -> int:
    """Chuỗi cấu hình → ngưỡng (≥1). Rỗng/không hợp lệ/≤0 → mặc định."""
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD
    return n if n >= 1 else DEFAULT_THRESHOLD


def find_stale(latest_by_pair: dict[str, date | None], today: date, threshold: int,
               pairs: list[str] | None = None) -> list[dict[str, Any]]:
    """Các cặp quá cũ (hoặc CHƯA có dữ liệu). Hàm thuần — không đụng DB."""
    out: list[dict[str, Any]] = []
    for pair in pairs or FX_PAIRS:
        latest = latest_by_pair.get(pair)
        lag = business_days_after(latest, today) if latest else None
        if latest is None or (lag is not None and lag >= threshold):
            out.append({"pair": pair, "latest": latest.isoformat() if latest else None, "lag": lag})
    return out


def describe(stale: list[dict[str, Any]]) -> str:
    """'USD/JPY 02/09 (trễ 7 phiên), USD/CNY chưa có dữ liệu' — dùng cho nhật ký quét + email."""
    parts = []
    for s in stale:
        if not s.get("latest"):
            parts.append(f"{s['pair']} chưa có dữ liệu")
            continue
        d = date.fromisoformat(str(s["latest"]))
        parts.append(f"{s['pair']} {d:%d/%m} (trễ {s['lag']} phiên)")
    return ", ".join(parts)


def latest_dates() -> dict[str, date]:
    """Ngày mới nhất có giá (> 0) của từng cặp tỷ giá tự động trong fact_price.

    Cố ý KHÔNG gọi `ensure_schema()`: hàm này chỉ đọc, chạy được cả trên bản sao DB chỉ-đọc.
    """
    with session_scope() as db:
        rows = db.execute(
            text("SELECT grade, MAX(as_of) FROM fact_price "
                 "WHERE source = :s AND grade = ANY(:pairs) AND price > 0 GROUP BY grade"),
            {"s": FX_SOURCE, "pairs": list(FX_PAIRS)},
        ).all()
    return {str(g): d for g, d in rows if d is not None}


def read_threshold() -> int:
    """Ngưỡng từ app_config (đọc thẳng, không ensure_schema — cùng lý do như `latest_dates`)."""
    try:
        with session_scope() as db:
            raw = db.execute(text("SELECT value FROM app_config WHERE key = :k"),
                             {"k": THRESHOLD_KEY}).scalar()
    except Exception:  # noqa: BLE001 - chưa có bảng cấu hình → dùng mặc định
        return DEFAULT_THRESHOLD
    return parse_threshold(raw)


def stale_pairs(today: date | None = None, threshold: int | None = None) -> list[dict[str, Any]]:
    """Các cặp tỷ giá quá cũ tính tới `today` (mặc định hôm nay giờ VN)."""
    return find_stale(latest_dates(), today or today_vn(),
                      threshold if threshold is not None else read_threshold())


def health(today: date | None = None) -> dict[str, Any]:
    """Payload cho GET /api/prices/fx-health."""
    threshold = read_threshold()
    return {
        "stale": stale_pairs(today, threshold),
        "checked_at": now_vn().isoformat(timespec="seconds"),
        "threshold": threshold,
    }
