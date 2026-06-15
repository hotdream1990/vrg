"""SGX / SICOM — TSR20 (mã TF) & RSS3 (mã RT), lấy SETTLE kỳ hạn có volume lớn nhất.

Nguồn: api.sgx.com (JSON). Spec: lay-gia-cac-san.md.
Lưu ý (đã kiểm chứng 2026-06-15): API v1.0 đổi format params — trả SGX_4015/4020 cho MỌI mã
(kể cả flagship FEF). Không dò mù được → BLOCKED. Cần param spec hiện hành (capture từ browser)
hoặc licensed feed. Logic parse vẫn sẵn sàng khi có dữ liệu hợp lệ.
"""

from __future__ import annotations

from datetime import date

from ..base.fetcher import fetch_json
from ..base.models import ContractQuote, CrawlResult, PriceRecord, Source, Status
from ..base.selection import SelectionStrategy

URL = "https://api.sgx.com/derivatives/v1.0/history/symbol/{sym}"
SYMBOLS = {"TF": "TSR20", "RT": "RSS3"}  # mã SGX → grade


def _to_quote(row: dict) -> ContractQuote | None:
    settle = row.get("settle") or row.get("p") or row.get("c")
    vol = row.get("vo") or row.get("v") or row.get("volume")
    if settle is None:
        return None
    try:
        return ContractQuote(settle=float(settle), volume=float(vol) if vol is not None else None)
    except (TypeError, ValueError):
        return None


def crawl() -> CrawlResult:
    try:
        records: list[PriceRecord] = []
        for sym, grade in SYMBOLS.items():
            data = fetch_json(URL.format(sym=sym))
            rows = data.get("data") or []
            quotes = [q for q in (_to_quote(r) for r in rows) if q]
            best = SelectionStrategy.MAX_VOLUME.pick(quotes)
            if best and best.settle is not None:
                records.append(
                    PriceRecord(
                        source=Source.SGX,
                        grade=grade,
                        price=best.settle,
                        currency="USD",
                        unit="US cents/kg",
                        price_type="settlement",
                        as_of=date.today(),
                        contract=f"{best.expiry_month}/{best.expiry_year}",
                    )
                )
        if records:
            return CrawlResult(source=Source.SGX, status=Status.OK, records=records)
        return CrawlResult(
            source=Source.SGX,
            status=Status.BLOCKED,
            note="SGX API v1.0 đổi format params (SGX_4015/4020 cho mọi mã) — cần param spec hiện hành (capture từ browser) hoặc licensed feed. (Open item)",
        )
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.SGX, status=Status.ERROR, note=str(exc))
