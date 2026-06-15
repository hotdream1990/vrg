"""Tỷ giá USD — phục vụ theo dõi USD/VNĐ và quy đổi giá physical (Latex, Sen/Kg...).

Nguồn: open.er-api.com (latest, không cần key/ngày). Spec: lay-gia-cac-san.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status

URL = "https://open.er-api.com/v6/latest/USD"
PAIRS = ["VND", "CNY", "THB", "JPY", "MYR"]  # USD/VNĐ + các đồng cho quy đổi sàn


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
