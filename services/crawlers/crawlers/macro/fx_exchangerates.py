"""Tỷ giá CNY/JPY/THB NGUỒN CHÍNH — exchangerates.org.uk (đúng nguồn Ban TTKD dùng).

Trang conversion (giao diện từ 03/09/2026) có bảng "Recent history" ~10 phiên gần nhất, dòng dạng
`<time datetime="2026-09-11">…</time> … 1 USD to JPY = 153.5195` (JPY/CNY có thêm cột Open/High/Low,
THB không). Đọc theo thuộc tính `datetime` → không phụ thuộc cách viết tên tháng.
Cloudflare chặn HTTP thường (403) → dùng trình duyệt thật (Playwright Firefox).
GOTCHA: CF chỉ cho qua lần tải ĐẦU của mỗi BrowserContext → mỗi đồng tiền 1 context MỚI.
Bỏ dòng Thứ 7/CN (bảng THB có lẻ tẻ dòng Chủ nhật) và dòng của ngày chưa kết thúc (>= hôm nay UTC).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from ..base.models import PriceRecord

PAGES = {
    "CNY": "https://www.exchangerates.org.uk/Dollars-to-Yuan-currency-conversion-page.html",
    "JPY": "https://www.exchangerates.org.uk/Dollars-to-YEN-currency-conversion-page.html",
    "THB": "https://www.exchangerates.org.uk/Dollars-to-Baht-currency-conversion-page.html",
}
# Giữ nguyên UA đã chạy ổn nhiều tháng với Firefox headless trước 03/09/2026.
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# 1 dòng bảng lịch sử: ngày ở <time datetime>, giá ở "1 USD to XXX = rate", không vượt qua </tr>.
_ROW = re.compile(r'<time datetime="(\d{4}-\d{2}-\d{2})">(?:(?!</tr>).)*?1 USD to ([A-Z]{3}) = ([\d.]+)',
                  re.DOTALL)


def parse_history(html: str, code: str, since: date, today: date) -> list[tuple[date, float]]:
    """[(ngày, Close)] Thứ 2–6 của `code`, since <= ngày < today. Trang lạ/bị chặn → []. Offline-testable."""
    out: list[tuple[date, float]] = []
    seen: set[date] = set()  # phòng trang lặp bảng (bố cục responsive) → mỗi ngày 1 dòng
    for day, cur, rate in _ROW.findall(html):
        as_of = date.fromisoformat(day)
        if cur != code or as_of in seen or as_of.weekday() >= 5 or not since <= as_of < today:
            continue
        seen.add(as_of)
        out.append((as_of, round(float(rate), 4)))
    return out


def _cf_wait(page, sec: int = 15) -> None:
    """Chờ Cloudflare giải JS challenge (title rời 'Just a moment'/'Attention Required')."""
    for _ in range(sec):
        title = page.title().lower()
        if "just a moment" not in title and "attention" not in title:
            return
        page.wait_for_timeout(1000)


def _fetch_pages(codes: tuple[str, ...]) -> tuple[dict[str, str], dict[str, str]]:
    """({mã: HTML trang conversion}, {mã: lý do lỗi}). Mỗi đồng 1 context riêng."""
    from playwright.sync_api import sync_playwright

    pages: dict[str, str] = {}
    errors: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        try:
            for code in codes:
                ctx = browser.new_context(user_agent=_UA, locale="en-US")
                try:
                    page = ctx.new_page()
                    page.goto(PAGES[code], wait_until="domcontentloaded", timeout=30000)
                    _cf_wait(page)
                    pages[code] = page.content()
                except Exception as exc:  # noqa: BLE001 - cô lập từng đồng (CF chặn 1 ≠ chặn cả)
                    errors[code] = type(exc).__name__
                finally:
                    ctx.close()
        finally:
            browser.close()
    return pages, errors


def closes(since: date, today: date, codes: tuple[str, ...],
           make: Callable[[str, date, float], PriceRecord]) -> tuple[list[PriceRecord], dict[str, str]]:
    """(Close các phiên since..hôm qua, {mã: lý do}) — mã vắng trong records luôn có lý do đi kèm.

    Lý do: tên lỗi tải trang (vd TimeoutError), "trình duyệt: <lỗi>" (thiếu Playwright/Firefox),
    hoặc "không đọc được bảng" (bị chặn/đổi giao diện/không có phiên nào trong khoảng).
    """
    try:
        pages, errors = _fetch_pages(codes)
    except Exception as exc:  # noqa: BLE001 - thiếu Playwright/Firefox → cả nguồn lỗi, fx.py dùng dự phòng
        return [], {c: f"trình duyệt: {type(exc).__name__}" for c in codes}
    records: list[PriceRecord] = []
    for code, html in pages.items():
        rows = parse_history(html, code, since, today)
        if not rows:
            errors[code] = "không đọc được bảng"
        records.extend(make(code, as_of, rate) for as_of, rate in rows)
    return records, errors
