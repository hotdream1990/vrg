"""SHFE — Natural Rubber (天然橡胶, RU): giá mới nhất + khối lượng + open interest.

Nguồn: Sina futures (hq.sinajs.cn/list=nf_RU0) — tự động được, ổn định (cần header Referer).
LƯU Ý ĐỘ CHÍNH XÁC: Sina trả giá GIAO DỊCH MỚI NHẤT (last), KHÔNG phải giá settlement
chính thức cuối ngày của SHFE. Settlement chính thức cần file EOD của sàn hoặc feed có license.
Đủ dùng làm tín hiệu giá/cầu Trung Quốc; là tham chiếu, không thay cho giá settlement chính thức.
"""

from __future__ import annotations

from datetime import datetime

from ..base.fetcher import fetch_text
from ..base.models import CrawlResult, PriceRecord, Source, Status

URL = "https://hq.sinajs.cn/list=nf_RU0"  # RU0 = hợp đồng chính (continuous)
_HEADERS = {"Referer": "https://finance.sina.com.cn"}

# Vị trí cột trong chuỗi CSV của Sina nf_ (map từ dữ liệu thật, xem phase-02)
_OPEN, _HIGH, _LOW, _LAST, _VOL, _OI, _DATE = 2, 3, 4, 7, 13, 14, 17


def _parse(text: str) -> PriceRecord | None:
    if '"' not in text:
        return None
    f = text.split('"', 2)[1].split(",")
    if len(f) <= _DATE or not f[_LAST]:
        return None
    try:
        return PriceRecord(
            source=Source.SHFE,
            grade="RU",
            price=float(f[_LAST]),
            currency="CNY",
            unit="CNY/tonne",
            price_type="last",
            as_of=datetime.strptime(f[_DATE], "%Y-%m-%d").date(),
            contract="RU0",
            extra={
                "open": float(f[_OPEN]),
                "high": float(f[_HIGH]),
                "low": float(f[_LOW]),
                "volume": float(f[_VOL]),
                "open_interest": float(f[_OI]),
                "exchange": "SHFE",
            },
        )
    except (ValueError, IndexError):
        return None


def crawl() -> CrawlResult:
    try:
        rec = _parse(fetch_text(URL, headers=_HEADERS))
        if rec:
            return CrawlResult(source=Source.SHFE, status=Status.OK, records=[rec])
        return CrawlResult(source=Source.SHFE, status=Status.EMPTY, note="Sina trả rỗng cho nf_RU0")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.SHFE, status=Status.ERROR, note=str(exc))
