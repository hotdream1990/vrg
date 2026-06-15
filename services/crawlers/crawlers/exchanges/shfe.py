"""SHFE — Natural Rubber (ru): SETTLE của kỳ hạn có VOLUME lớn nhất.

Nguồn: https://www.shfe.com.cn/data/dailydata/kx/kx{YYYYMMDD}.dat (JSON). Spec: lay-gia-cac-san.md.
Lưu ý: endpoint hiện 404 từ môi trường này (cần ngày giao dịch thật / proxy) → BLOCKED;
logic parse + chọn kỳ hạn theo max volume đã sẵn sàng khi truy cập được.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..base.fetcher import fetch_json
from ..base.models import ContractQuote, CrawlResult, PriceRecord, Source, Status
from ..base.selection import SelectionStrategy

URL = "https://www.shfe.com.cn/data/dailydata/kx/kx{ymd}.dat"


def _latest_trading_day(today: date | None = None) -> date:
    d = (today or date.today()) - timedelta(days=1)
    while d.weekday() >= 5:  # bỏ T7/CN
        d -= timedelta(days=1)
    return d


def _parse(payload: dict) -> list[ContractQuote]:
    rows = payload.get("o_curinstrument") or payload.get("Data") or []
    quotes: list[ContractQuote] = []
    for r in rows:
        pid = str(r.get("PRODUCTID") or r.get("INSTRUMENTID") or "").lower()
        if not pid.startswith("ru"):
            continue
        settle = r.get("SETTLEMENTPRICE") or r.get("settle")
        vol = r.get("VOLUME") or r.get("volume")
        if settle in (None, "", 0):
            continue
        try:
            quotes.append(
                ContractQuote(settle=float(settle), volume=float(vol) if vol else None)
            )
        except (TypeError, ValueError):
            continue
    return quotes


def crawl(as_of: date | None = None) -> CrawlResult:
    day = as_of or _latest_trading_day()
    try:
        data = fetch_json(URL.format(ymd=day.strftime("%Y%m%d")))
        best = SelectionStrategy.MAX_VOLUME.pick(_parse(data))
        if best and best.settle is not None:
            return CrawlResult(
                source=Source.SHFE,
                status=Status.OK,
                records=[
                    PriceRecord(
                        source=Source.SHFE,
                        grade="RU",
                        price=best.settle,
                        currency="CNY",
                        unit="CNY/tonne",
                        price_type="settlement",
                        as_of=day,
                    )
                ],
            )
        return CrawlResult(source=Source.SHFE, status=Status.EMPTY, note=f"Không có ru ngày {day}")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(
            source=Source.SHFE,
            status=Status.BLOCKED,
            note=f"SHFE .dat không truy cập được (cần ngày giao dịch thật/proxy): {exc}",
        )
