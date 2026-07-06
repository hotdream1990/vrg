"""SGX / SICOM — TSR20 (mã TF) & RSS3 (mã RT): SETTLE của kỳ hạn hoạt động nhất.

Nguồn: `api.sgx.com/derivatives/v1.0/contract-code/{code}` (JSON) — chính request mà trang
`delayed-prices-futures?cc=TF&category=rubber` của SGX gọi (cần Origin/Referer sgx.com).
Feed delayed nên volume phiên = 0 → chọn kỳ hạn có **open-interest lớn nhất** (contract
benchmark); khi có volume phiên thì ưu tiên volume. Giá = preliminary settlement (US cents/kg).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status

URL = ("https://api.sgx.com/derivatives/v1.0/contract-code/{code}"
       "?order=asc&orderby=delivery-month&category=futures&session=-1")
SYMBOLS = {"TF": "TSR20", "RT": "RSS3"}  # mã SGX → grade bản tin
_HEADERS = {"Accept": "*/*", "Origin": "https://www.sgx.com", "Referer": "https://www.sgx.com/"}


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _pick(rows: list[dict]) -> dict | None:
    """Kỳ hạn đại diện: volume phiên lớn nhất; nếu volume=0 hết (feed delayed) → OI lớn nhất."""
    valid = [r for r in rows if _num(r.get("preliminary-settlement-price-abs")) is not None]
    if not valid:
        return None
    by_vol = max(valid, key=lambda r: _num(r.get("total-volume")) or 0.0)
    if (_num(by_vol.get("total-volume")) or 0.0) > 0:
        return by_vol
    return max(valid, key=lambda r: _num(r.get("open-interest")) or 0.0)


def _weekday(d: date) -> date:
    """Kẹp ngày cuối tuần về Thứ 6 liền trước (thị trường đóng cửa T7/CN — giá là của phiên T6).

    SGX feed delayed đôi khi đóng dấu base-date là ngày cuối tuần / phiên kế; fallback hôm nay
    cũng có thể rơi vào cuối tuần. Kẹp về T6 để dữ liệu nằm đúng ngày giao dịch (dễ track).
    """
    if d.weekday() >= 5:  # 5=T7, 6=CN
        d -= timedelta(days=d.weekday() - 4)
    return d


def _as_of(row: dict) -> date:
    """Ngày phiên dữ liệu (base-date YYYYMMDD do SGX trả), fallback hôm nay — kẹp về ngày giao dịch."""
    try:
        d = datetime.strptime(str(row.get("base-date")), "%Y%m%d").date()
    except ValueError:
        d = date.today()
    return _weekday(d)


def crawl() -> CrawlResult:
    try:
        records: list[PriceRecord] = []
        for code, grade in SYMBOLS.items():
            data = fetch_json(URL.format(code=code), headers=_HEADERS)
            best = _pick(data.get("data") or [])
            settle = _num(best.get("preliminary-settlement-price-abs")) if best else None
            if best and settle is not None:
                records.append(
                    PriceRecord(
                        source=Source.SGX,
                        grade=grade,
                        price=settle,
                        currency="USD",
                        unit="US cents/kg",
                        price_type="settlement",
                        as_of=_as_of(best),
                        contract=str(best.get("delivery-month") or ""),
                    )
                )
        if records:
            return CrawlResult(source=Source.SGX, status=Status.OK, records=records)
        return CrawlResult(source=Source.SGX, status=Status.EMPTY,
                           note="SGX contract-code trả rỗng cho TF/RT.")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.SGX, status=Status.ERROR, note=str(exc))
