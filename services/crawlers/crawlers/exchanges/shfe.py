"""SHFE — Natural Rubber (天然橡胶, RU): SETTLEMENT của kỳ hạn có VOLUME lớn nhất (đúng spec).

Nguồn CHÍNH THỨC: SHFE daily market data (JSON)
  https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{YYYYMMDD}.dat
`o_curinstrument[]`: PRODUCTID 'ru_f' · DELIVERYMONTH (vd '2609') · SETTLEMENTPRICE · VOLUME · OPENINTEREST.
Bỏ dòng tổng (小计/total). Chọn kỳ hạn MAX VOLUME → giá Settlement (spec lay-gia-cac-san.md). Đơn vị CNY/tấn.
Tự lùi ngày để lấy báo cáo mới nhất có sẵn (T7/CN/nghỉ hoặc hôm nay chưa đăng).
"""

from __future__ import annotations

from datetime import date, timedelta

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status

_URL = "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{ymd}.dat"
_HEADERS = {"Referer": "https://www.shfe.com.cn/"}


def _recent_days(today: date, n: int = 7) -> list[date]:
    """today lùi dần, bỏ T7/CN — thử báo cáo mới nhất có sẵn."""
    days, d = [], today
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days


def _pick_ru(rows: list[dict]) -> dict | None:
    """Kỳ hạn RU có VOLUME lớn nhất (bỏ dòng tổng & kỳ hạn không có settlement)."""
    best: dict | None = None
    for x in rows:
        if not str(x.get("PRODUCTID", "")).strip().lower().startswith("ru_f"):
            continue
        month = str(x.get("DELIVERYMONTH", "")).strip()
        if not month.isdigit():  # bỏ 小计/total
            continue
        try:
            settle = float(x.get("SETTLEMENTPRICE"))
            volume = float(x.get("VOLUME"))
        except (TypeError, ValueError):
            continue
        if settle <= 0:
            continue
        cur = {"month": month, "settle": settle, "volume": volume, "oi": x.get("OPENINTEREST")}
        if best is None or volume > best["volume"]:
            best = cur
    return best


def crawl(as_of: date | None = None) -> CrawlResult:
    try:
        for d in _recent_days(as_of or date.today()):
            try:
                data = fetch_json(_URL.format(ymd=d.strftime("%Y%m%d")), headers=_HEADERS, retries=1)
            except Exception:  # noqa: BLE001 - ngày này chưa có, thử ngày trước
                continue
            best = _pick_ru(data.get("o_curinstrument") or [])
            if not best:
                continue
            rec = PriceRecord(
                source=Source.SHFE,
                grade="RU",
                price=best["settle"],
                currency="CNY",
                unit="CNY/tonne",
                price_type="settlement",
                as_of=d,
                contract=best["month"],
                extra={
                    "selection": "max_volume",
                    "volume": best["volume"],
                    "open_interest": best["oi"],
                    "exchange": "SHFE",
                },
            )
            return CrawlResult(source=Source.SHFE, status=Status.OK, records=[rec])
        return CrawlResult(source=Source.SHFE, status=Status.EMPTY, note="Không tải được SHFE daily data (kx)")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.SHFE, status=Status.ERROR, note=str(exc))
