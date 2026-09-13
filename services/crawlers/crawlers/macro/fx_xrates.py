"""Tỷ giá CNY/JPY/THB DỰ PHÒNG — x-rates.com, trang "Historical Rates" theo ngày (HTTP thường).

Chỉ dùng khi exchangerates.org.uk (nguồn chính, Ban TTKD dùng) lỗi cho một đồng — xem `fx.py`.
Lệch trung vị so với exchangerates (43 phiên 06/07–02/09/2026): JPY 1,2 · CNY 0,8 · THB 2,4 bps.
GOTCHA ngày: trang ngày X là ẢNH CHỤP lúc ~00:00 UTC ngày X = giá đóng cửa ngày X-1
(đo khớp giờ với Yahoo). Vì vậy Close ngày D = trang ngày D+1.
GOTCHA "hôm nay": trang của ngày chưa chốt trả tỷ giá LIVE (nhãn giờ = giờ hiện tại) → chỉ nhận
ngày X < hôm nay (UTC) VÀ nhãn giờ đúng nhãn ảnh chụp đã chốt; sai → bỏ, không đoán.
Chỉ lấy Thứ 2–6 (không nhân bản giá thứ Sáu sang cuối tuần).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, timedelta

from ..base.fetcher import fetch_text
from ..base.models import PriceRecord

_URL = "https://www.x-rates.com/historical/?from=USD&amount=1&date={d}"
# Nhãn giờ của trang ngày ĐÃ CHỐT (mọi ngày quá khứ đều in đúng nhãn này); trang live in giờ hiện tại.
_SNAPSHOT_STAMP = "16:00 UTC"
_STAMP = re.compile(r'class="ratesTimestamp">([^<]+)<')
_RATE = re.compile(r"from=USD&amp;to=([A-Z]{3})'>([\d.]+)<")


def parse_snapshot(html: str, codes: tuple[str, ...]) -> dict[str, float]:
    """{mã: tỷ giá} từ 1 trang lịch sử x-rates ĐÃ CHỐT. Trang live/lạ/bị chặn → {}. Offline-testable."""
    stamp = _STAMP.search(html)
    if not stamp or not stamp.group(1).strip().endswith(_SNAPSHOT_STAMP):
        return {}
    rates: dict[str, float] = {}
    for code, value in _RATE.findall(html):  # bảng xuất hiện 2 lần (top-10 + đầy đủ) → giữ lần đầu
        if code in codes and code not in rates:
            rates[code] = round(float(value), 4)
    return rates


def closes(first: date, last: date, today: date, codes: tuple[str, ...],
           make: Callable[[str, date, float], PriceRecord]) -> list[PriceRecord]:
    """Close các ngày Thứ 2–6 trong [first, last] cho `codes`. Close ngày D = ảnh chụp ngày D+1.

    Chỉ nhận ảnh chụp của ngày < hôm nay (UTC). Lỗi mạng → dừng luôn (không kéo dài cả lượt quét).
    """
    out: list[PriceRecord] = []
    d = first
    while d <= last:
        snap = d + timedelta(days=1)
        if snap >= today:
            break
        if d.weekday() < 5:
            try:
                html = fetch_text(_URL.format(d=snap.isoformat()), retries=2)
            except Exception:  # noqa: BLE001 - nguồn sập → dừng, fx.crawl() ghi chú thiếu cặp nào
                break
            out.extend(make(code, d, rate) for code, rate in parse_snapshot(html, codes).items())
        d += timedelta(days=1)
    return out
