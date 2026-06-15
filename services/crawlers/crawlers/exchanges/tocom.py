"""TOCOM (OSE/JPX) — giá SETTLEMENT chính thức: Rubber (RSS3) & Rubber (TSR20).

Nguồn: JPX settlement-price CSV `rb_e{YYYYMMDD}.csv` — tải HTTP trực tiếp (encoding cp932).
URL khám phá 1 lần bằng browser; runtime chỉ cần HTTP. Nếu JPX đổi đường dẫn → tự fallback
Playwright tìm lại link (self-healing). Spec: lay-gia-cac-san.md.

Chọn kỳ hạn: hiện lấy kỳ hạn gần nhất (front month) làm headline + đính kèm TOÀN BỘ đường cong
ở `extra`. Chọn theo max Trading Value cần file volume riêng của JPX (refinement — open item).
"""

from __future__ import annotations

import csv
import io
from datetime import date

from ..base.fetcher import fetch_bytes
from ..base.models import CrawlResult, PriceRecord, Source, Status

_BASE = "https://www.jpx.co.jp/english/markets/derivatives/settlement-price"
_ATT = "tvdivq00000014l6-att"  # thư mục attachment (ổn định; fallback browser nếu đổi)
_SETTLE_PAGE = f"{_BASE}/index.html"

# Underlying Name trong CSV → mã grade
_GRADES = {"Rubber (RSS3)": "RSS3", "Rubber (TSR20)": "TSR20"}


def _csv_url(as_of: date) -> str:
    return f"{_BASE}/{_ATT}/rb_e{as_of:%Y%m%d}.csv"


def _parse(raw: bytes) -> dict[str, list[dict]]:
    text = raw.decode("cp932", errors="replace")
    out: dict[str, list[dict]] = {g: [] for g in _GRADES.values()}
    for r in csv.reader(io.StringIO(text)):
        if len(r) < 12 or r[11].strip() not in _GRADES or not r[5].strip():
            continue
        try:
            settle = float(r[5])
        except ValueError:
            continue
        days = int(r[10]) if r[10].strip().lstrip("-").isdigit() else None
        out[_GRADES[r[11].strip()]].append(
            {"contract": r[3].strip(), "settle": settle, "days": days}
        )
    return out


def _front(contracts: list[dict]) -> dict | None:
    live = [c for c in contracts if c["days"] is not None and c["days"] > 0]
    if live:
        return min(live, key=lambda c: c["days"])
    return contracts[0] if contracts else None


def _fetch(day: date) -> bytes:
    """HTTP trực tiếp; nếu lỗi (URL đổi) → fallback Playwright tìm link CSV hiện hành."""
    try:
        return fetch_bytes(_csv_url(day))
    except Exception:
        url = _discover_url()
        if not url:
            raise
        return fetch_bytes(url)


def _discover_url() -> str | None:
    """Mở trang settlement bằng Playwright, lấy link rb_e*.csv hiện hành (self-healing)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(extra_http_headers={"Accept-Language": "en-US,en"})
            page.goto(_SETTLE_PAGE, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            links = page.eval_on_selector_all(
                "a", r"els => els.map(e => e.href).filter(h => /rb_e\d+\.csv$/i.test(h))"
            )
            return links[0] if links else None
        finally:
            browser.close()


def crawl(as_of: date | None = None) -> CrawlResult:
    day = as_of or date.today()
    try:
        parsed = _parse(_fetch(day))
        records: list[PriceRecord] = []
        for grade, contracts in parsed.items():
            front = _front(contracts)
            if not front:
                continue
            records.append(
                PriceRecord(
                    source=Source.TOCOM,
                    grade=grade,
                    price=front["settle"],
                    currency="JPY",
                    unit="JPY/kg",
                    price_type="settlement",
                    as_of=day,
                    contract=front["contract"],
                    extra={"exchange": "OSE/TOCOM", "selection": "front-month", "curve": contracts},
                )
            )
        if records:
            return CrawlResult(source=Source.TOCOM, status=Status.OK, records=records)
        return CrawlResult(source=Source.TOCOM, status=Status.EMPTY, note=f"Không có dòng rubber {day}")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.TOCOM, status=Status.ERROR, note=str(exc))
