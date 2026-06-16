"""Tỷ giá USD — phục vụ theo dõi USD/VNĐ và quy đổi giá physical (Latex, Sen/Kg...).

Latest: open.er-api.com (đủ pairs gồm VND). History: frankfurter.dev (ECB, có CNY/JPY/MYR/THB,
KHÔNG có VND). Spec: lay-gia-cac-san.md.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status

URL = "https://open.er-api.com/v6/latest/USD"
PAIRS = ["VND", "CNY", "THB", "JPY", "MYR"]  # USD/VNĐ + các đồng cho quy đổi sàn
# History ECB (không có VND) — backfill chart vĩ mô.
_HIST_URL = "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=CNY,JPY,MYR,THB"


def crawl() -> CrawlResult:
    try:
        data = fetch_json(URL)
        rates = data.get("rates", {})
        ts = data.get("time_last_update_unix")
        as_of = (
            datetime.fromtimestamp(ts, tz=timezone.utc).date()
            if ts
            else datetime.now(timezone.utc).date()
        )
        records = [
            PriceRecord(
                source=Source.FX,
                grade=f"USD/{c}",
                price=float(rates[c]),
                currency=c,
                unit=f"{c} per USD",
                price_type="fx",
                as_of=as_of,
            )
            for c in PAIRS
            if c in rates
        ]
        if records:
            return CrawlResult(source=Source.FX, status=Status.OK, records=records)
        return CrawlResult(source=Source.FX, status=Status.EMPTY, note="Không có tỷ giá")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.FX, status=Status.ERROR, note=str(exc))


def history(days: int = 90, end: date | None = None) -> list[PriceRecord]:
    """Backfill tỷ giá USD/CNY,JPY,MYR,THB (ECB qua frankfurter) — 1 request cả range.

    KHÔNG có VND (ngoài rổ ECB) → VND chỉ tích lũy tiến từ open.er-api.
    """
    end_d = end or datetime.now(timezone.utc).date()
    start_d = end_d - timedelta(days=days)
    data = fetch_json(_HIST_URL.format(start=start_d.isoformat(), end=end_d.isoformat()))
    rates = data.get("rates", {})
    out: list[PriceRecord] = []
    for day_str in sorted(rates):
        as_of = datetime.fromisoformat(day_str).date()
        for cur, val in rates[day_str].items():
            out.append(
                PriceRecord(
                    source=Source.FX,
                    grade=f"USD/{cur}",
                    price=float(val),
                    currency=cur,
                    unit=f"{cur} per USD",
                    price_type="fx",
                    as_of=as_of,
                )
            )
    return out
