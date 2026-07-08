"""SGX / SICOM — TSR20 (mã TF) & RSS3 (mã RT): settlement của kỳ hạn giao THÁNG SAU.

Nguồn: `api.sgx.com/derivatives/v1.0/contract-code/{code}` (JSON) — chính request mà trang
`delayed-prices-futures?cc=TF&category=rubber` của SGX gọi (cần Origin/Referer sgx.com).
Chọn **hợp đồng giao tháng sau** (next month so với ngày hiện tại theo giờ Singapore UTC+8)
đúng chỉ số chuyên viên. Giá = `preliminary-settlement-price-abs` (US cents/kg).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

_SGT = timezone(timedelta(hours=8))  # SGX = giờ Singapore (UTC+8) — căn ngày hiện tại theo múi này

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


def _target_delivery_month(today: date | None = None) -> str:
    """Kỳ hạn cần lấy = THÁNG SAU tháng của NGÀY HIỆN TẠI (giờ Singapore UTC+8).

    Theo chỉ số chuyên viên: đọc hợp đồng giao "tháng sau" (next month). VD ngày xử lý
    2026-07-08 (tháng 7) → hợp đồng giao **2026-08**. Định dạng "YYYY-MM" khớp field
    `delivery-month` của SGX. API là live nên căn theo ngày hiện tại UTC+8 (không theo base-date).
    """
    d = today or datetime.now(_SGT).date()
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return f"{y:04d}-{m:02d}"


def _pick(rows: list[dict]) -> dict | None:
    """Chọn hợp đồng giao THÁNG SAU (next month, giờ Singapore) có settle > 0.

    (settle > 0: sáng sớm sàn chưa ra settlement → 0/None → bỏ, không lưu 0 USD/T vào DB.)
    Không khớp tháng-sau/không có settle → None (grade đó để trống, không bịa số).
    """
    target = _target_delivery_month()
    for r in rows:
        if str(r.get("delivery-month")) == target and (_num(r.get("preliminary-settlement-price-abs")) or 0) > 0:
            return r
    return None


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
                        currency="USc",  # US cents (không phải USD) — giá yết bằng cent/kg
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
