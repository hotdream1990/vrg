"""Tỷ giá USD — Close hằng ngày từ exchangerates.org.uk (đúng nguồn Ban TTKD dùng).

exchangerates.org.uk đứng sau Cloudflare → httpx bị 403; phải dùng trình duyệt thật (Playwright).
GOTCHA: CF chỉ cho qua lần tải ĐẦU của mỗi BrowserContext → mỗi đồng tiền dùng 1 context MỚI
(điều hướng nhiều trang trong cùng context bị WAF chặn 403). Lấy dòng Close mới nhất ("DD Month
YYYY  1 USD = <rate> <CUR>") trong bảng "Exchange Rate History" của trang conversion.
VND: lấy TỪ VIETCOMBANK (API công khai có date param) — 2 giá "USD/VND (Mua)" (chuyển khoản)
và "USD/VND (Bán)", đồng bộ với phiếu Báo giá mủ. Backfill VND theo từng ngày qua VCB.
Backfill 4 đồng còn lại: history() đọc bảng lịch sử exchangerates (~7 phiên) → khớp data live.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status

# Đồng tiền quy trình giá sàn: CNY/JPY (quy futures→USD), MYR (Ringgit), THB (physical Thái).
_PAGES = {
    "CNY": "https://www.exchangerates.org.uk/Dollars-to-Yuan-currency-conversion-page.html",
    "JPY": "https://www.exchangerates.org.uk/Dollars-to-YEN-currency-conversion-page.html",
    "THB": "https://www.exchangerates.org.uk/Dollars-to-Baht-currency-conversion-page.html",
    "MYR": "https://www.exchangerates.org.uk/Dollars-to-Malaysian-Ringgit-currency-conversion-page.html",
}
_VCB_URL = "https://www.vietcombank.com.vn/api/exchangerates?date={d}"  # VND: nguồn Vietcombank
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# 1 dòng lịch sử: "23 June 2026  1 USD = 6.7908 CNY" (bỏ qua thứ đứng trước số ngày).
_ROW = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+1 USD = ([\d.]+)\s+([A-Z]{3})")


def _parse_latest(text: str, code: str) -> tuple[date, float] | None:
    """Dòng Close MỚI NHẤT cho `code` trong bảng lịch sử (newest-first). Offline-testable.

    Bỏ qua dòng spot không có ngày (vd 'Live: 1 USD = ...') vì regex bắt buộc có ngày đứng trước.
    """
    for m in _ROW.finditer(text):
        d, mon, yr, rate, cur = m.groups()
        if cur != code:
            continue
        try:
            as_of = datetime.strptime(f"{d} {mon} {yr}", "%d %B %Y").date()
        except ValueError:
            continue
        return as_of, float(rate)
    return None


def _rec(code: str, as_of: date, rate: float) -> PriceRecord:
    return PriceRecord(source=Source.FX, grade=f"USD/{code}", price=rate, currency=code,
                       unit=f"{code} per USD", price_type="fx", as_of=as_of)


def _cf_wait(page, sec: int = 15) -> None:
    """Chờ Cloudflare giải JS challenge (title rời 'Just a moment'/'Attention Required')."""
    for _ in range(sec):
        title = page.title().lower()
        if "just a moment" not in title and "attention" not in title:
            page.wait_for_timeout(2000)  # để bảng lịch sử render xong
            return
        page.wait_for_timeout(1000)


def _scrape(pages: dict[str, str]) -> tuple[list[PriceRecord], list[str]]:
    """Scrape Close từng đồng bằng 1 context riêng. Trả (records, danh sách đồng lỗi)."""
    from playwright.sync_api import sync_playwright

    records: list[PriceRecord] = []
    failed: list[str] = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        try:
            for code, url in pages.items():
                ctx = browser.new_context(user_agent=_UA, locale="en-US")
                try:
                    page = ctx.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    _cf_wait(page)
                    parsed = _parse_latest(page.inner_text("body"), code)
                    if parsed:
                        records.append(_rec(code, *parsed))
                    else:
                        failed.append(code)
                except Exception:  # noqa: BLE001 - cô lập từng đồng (CF chặn 1 ≠ chặn cả)
                    failed.append(code)
                finally:
                    ctx.close()
        finally:
            browser.close()
    return records, failed


def _vcb_usd(day: date | None = None) -> tuple[date, float | None, float | None] | None:
    """(ngày, mua CK, bán) USD từ VCB theo ngày (mặc định hôm nay). None nếu lỗi/không có USD."""
    d = (day or datetime.now(timezone.utc).date()).isoformat()
    try:
        data = fetch_json(_VCB_URL.format(d=d),
                          headers={"User-Agent": _UA, "Accept": "application/json"})
    except Exception:  # noqa: BLE001
        return None
    usd = next((x for x in data.get("Data", []) if x.get("currencyCode") == "USD"), None)
    if not usd:
        return None

    def _num(v: object) -> float | None:
        s = str(v).replace(",", "").strip()
        try:
            return float(s) if s and s != "-" else None
        except ValueError:
            return None

    src = str(data.get("Date") or d)[:10]
    try:
        as_of = date.fromisoformat(src)
    except ValueError:
        as_of = date.fromisoformat(d)
    return as_of, _num(usd.get("transfer")), _num(usd.get("sell"))


def _vnd_records(day: date | None = None) -> list[PriceRecord]:
    """USD/VND Mua (chuyển khoản) + Bán từ VCB → list PriceRecord (rỗng nếu lỗi)."""
    got = _vcb_usd(day)
    if not got:
        return []
    as_of, ck, ban = got
    out: list[PriceRecord] = []
    if ck is not None:
        out.append(PriceRecord(source=Source.FX, grade="USD/VND (Mua)", price=ck,
                               currency="VND", unit="VND per USD", price_type="fx", as_of=as_of))
    if ban is not None:
        out.append(PriceRecord(source=Source.FX, grade="USD/VND (Bán)", price=ban,
                               currency="VND", unit="VND per USD", price_type="fx", as_of=as_of))
    return out


def crawl() -> CrawlResult:
    """Quét tỷ giá Close (CNY/JPY/THB/MYR qua Playwright) + VND (open.er-api). Cô lập lỗi."""
    notes: list[str] = []
    try:
        records, failed = _scrape(_PAGES)
        if failed:
            notes.append("Cloudflare/parse chặn: " + ",".join(failed))
    except Exception as exc:  # noqa: BLE001 - Playwright/Firefox hỏng → cả nhóm scrape fail
        records, notes = [], [f"scrape lỗi: {str(exc)[:100]}"]
    vnd = _vnd_records()
    if vnd:
        records.extend(vnd)
    else:
        notes.append("VND (VCB) lỗi")
    note = "; ".join(notes) or None
    if records:
        return CrawlResult(source=Source.FX, status=Status.OK, records=records, note=note)
    return CrawlResult(source=Source.FX, status=Status.BLOCKED, note=note or "Không lấy được tỷ giá")


def _parse_history(text: str, code: str, since: date) -> list[tuple[date, float]]:
    """Mọi dòng Close cho `code` (bảng lịch sử) từ ngày >= since. Offline-testable."""
    out: list[tuple[date, float]] = []
    for m in _ROW.finditer(text):
        d, mon, yr, rate, cur = m.groups()
        if cur != code:
            continue
        try:
            as_of = datetime.strptime(f"{d} {mon} {yr}", "%d %B %Y").date()
        except ValueError:
            continue
        if as_of >= since:
            out.append((as_of, float(rate)))
    return out


def history(days: int) -> list[PriceRecord]:
    """Backfill Close CNY/JPY/THB/MYR các phiên gần đây từ CHÍNH exchangerates (bảng lịch sử).

    Cùng nguồn với crawl() → giá trị KHỚP TUYỆT ĐỐI với data live. Bảng chỉ giữ ~7 phiên gần
    nhất nên chỉ lấp được lỗ trong khoảng đó (đủ khi lỡ quên quét vài phiên). VND: bỏ qua
    (exchangerates không có). Mỗi đồng dùng 1 context mới (CF chặn điều hướng nhiều trang).
    """
    from playwright.sync_api import sync_playwright

    since = datetime.now(timezone.utc).date() - timedelta(days=days)
    records: list[PriceRecord] = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        try:
            for code, url in _PAGES.items():
                ctx = browser.new_context(user_agent=_UA, locale="en-US")
                try:
                    page = ctx.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    _cf_wait(page)
                    for as_of, rate in _parse_history(page.inner_text("body"), code, since):
                        records.append(_rec(code, as_of, rate))
                except Exception:  # noqa: BLE001 - cô lập từng đồng (CF chặn 1 ≠ chặn cả)
                    pass
                finally:
                    ctx.close()
        finally:
            browser.close()

    # VND (Mua/Bán) từ VCB — API có date param nên backfill được từng ngày trong khoảng.
    day = datetime.now(timezone.utc).date()
    for _ in range(days + 1):
        records.extend(_vnd_records(day))
        day -= timedelta(days=1)
    return records
