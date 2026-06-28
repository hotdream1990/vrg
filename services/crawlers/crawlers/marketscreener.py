"""Crawler giá Asian physical rubber từ marketscreener.com (chuỗi Reuters hằng ngày).

Akamai chặn headless CHROMIUM → DÙNG FIREFOX (vân tay khác, qua được). Bài giá là member
content → cần đăng nhập (MARKETSCREENER_USER/PASS trong .env). Mỗi bài "Asian physical rubber
prices - <ngày>" có bảng grade→giá (baht/kg cho Thái, $/kg cho Malaysia/Indonesia).

Chạy thử: uv run python -m crawlers.marketscreener   (in dữ liệu vài bài gần nhất)
"""
from __future__ import annotations

import os
import re
from typing import Any

from playwright.sync_api import sync_playwright

BASE = "https://www.marketscreener.com"
SEARCH = BASE + "/search/?q=Asian+physical+rubber+prices"
# tên grade trong bài → grade chuẩn của hệ thống (khớp source 'reuters' đã có)
GRADE_MAP = [
    ("rss3", "RSS3"), ("str20", "STR20"), ("smr20", "SMR20"), ("sir20", "SIR20"),
    ("latex", "Thai Latex 60% (Bulk)"),
]
_BAHT_RE = re.compile(r"([\d.]+)\s*baht/kg", re.I)        # Thái: "96.15 baht/kg"
_USD_RE = re.compile(r"\$\s*([\d.]+)\s*/\s*kg", re.I)     # Malaysia/Indonesia: "$2.19/kg"


def _cookie(pg) -> None:
    for sel in ("#didomi-notice-agree-button", "button:has-text('Agree')", "button:has-text('Accept')"):
        try:
            el = pg.query_selector(sel)
            if el and el.is_visible():
                el.click(); pg.wait_for_timeout(600); return
        except Exception:  # noqa: BLE001
            pass


def _login(pg) -> bool:
    u, p = os.environ.get("MARKETSCREENER_USER"), os.environ.get("MARKETSCREENER_PASS")
    if not u or not p:
        raise RuntimeError("Thiếu MARKETSCREENER_USER / MARKETSCREENER_PASS trong env")
    pg.goto(BASE + "/login/", wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(1800); _cookie(pg)
    pg.fill("input[type=email]", u)
    pg.click("button:has-text('Continue with an email')"); pg.wait_for_timeout(2200); _cookie(pg)
    pg.wait_for_selector("input[type=password]", timeout=10000)
    pg.fill("input[type=password]", p)
    for sel in ("button:has-text('Log in')", "button:has-text('Sign in')", "button:has-text('Continue')", "button[type=submit]"):
        el = pg.query_selector(sel)
        if el and el.is_visible():
            el.click(); break
    pg.wait_for_timeout(4500)
    return "login" not in pg.url.lower()


def _article_urls(pg, n: int) -> list[str]:
    pg.goto(SEARCH, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(2500); _cookie(pg)
    urls: list[str] = []
    for a in pg.query_selector_all("a[href]"):
        h = a.get_attribute("href") or ""
        if "asian-physical-rubber-prices" in h.lower():
            full = BASE + h if h.startswith("/") else h
            if full not in urls:
                urls.append(full)
    return urls[:n]


def _parse_article(pg, url: str) -> dict[str, Any] | None:
    pg.goto(url, wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(2500); _cookie(pg)
    # ngày đăng (ISO) từ meta hoặc <time>
    as_of = None
    for sel, attr in (("meta[property='article:published_time']", "content"), ("time[datetime]", "datetime")):
        el = pg.query_selector(sel)
        if el and el.get_attribute(attr):
            as_of = el.get_attribute(attr)[:10]; break
    body = pg.inner_text("body")
    if "reserved for members" in body.lower():
        return None  # chưa đăng nhập / hết quyền
    rows = []
    for line in body.split("\n"):
        mb, mu = _BAHT_RE.search(line), _USD_RE.search(line)
        if not mb and not mu:
            continue
        grade = next((g for key, g in GRADE_MAP if key in line.lower()), None)
        if not grade:
            continue
        value, unit = (float(mb.group(1)), "baht/kg") if mb else (float(mu.group(1)), "USD/kg")
        rows.append({"grade": grade, "value": value, "unit": unit})
    return {"as_of": as_of, "url": url, "rows": rows} if rows else None


def fetch(n: int = 5) -> list[dict[str, Any]]:
    """Đăng nhập + lấy n bài 'Asian physical rubber prices' mới nhất, parse bảng giá."""
    with sync_playwright() as p:
        b = p.firefox.launch(headless=True)
        pg = b.new_context(locale="en-US", viewport={"width": 1366, "height": 1000}).new_page()
        try:
            if not _login(pg):
                raise RuntimeError("Đăng nhập marketscreener thất bại")
            out = [d for u in _article_urls(pg, n) if (d := _parse_article(pg, u))]
        finally:
            b.close()
    return out


def _to_usd_tonne(value: float, unit: str, thb: float | None) -> int | None:
    """baht/kg → USD/T (cần tỷ giá USD/THB); USD/kg → USD/T (×1000)."""
    if unit == "USD/kg":
        return round(value * 1000)
    if unit == "baht/kg" and thb:
        return round(value * 1000 / thb)
    return None


def persist(n: int = 60, dsn: str | None = None) -> int:
    """Lấy n bài + quy đổi USD/T + upsert vào fact_price (source='reuters', physical)."""
    import psycopg
    dsn = dsn or os.environ.get("DATABASE_URL", "postgresql://vrg:changeme@localhost:5433/vrg_caosu")
    arts = fetch(n)
    with psycopg.connect(dsn) as conn:
        thb_rows = conn.execute("SELECT as_of, price FROM fact_price WHERE source='fx' "
                                "AND grade='USD/THB' ORDER BY as_of").fetchall()
        def thb_at(d):  # tỷ giá USD/THB gần nhất <= ngày bài
            prior = [r for r in thb_rows if str(r[0]) <= d]
            return float(prior[-1][1]) if prior else None
        recs = []
        for a in arts:
            if not a["as_of"]:
                continue
            for r in a["rows"]:
                usd_t = _to_usd_tonne(r["value"], r["unit"], thb_at(a["as_of"]))
                if usd_t:
                    recs.append((a["as_of"], "reuters", r["grade"], "", "physical",
                                 usd_t, "USD", "USD/tonne"))
        if recs:
            conn.cursor().executemany(
                "INSERT INTO fact_price (as_of, source, grade, contract, price_type, price, currency, unit) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (as_of, source, grade, contract, price_type) "
                "DO UPDATE SET price=EXCLUDED.price, ingested_at=now()", recs)
            conn.commit()
    return len(recs)


if __name__ == "__main__":
    import sys
    if "--persist" in sys.argv:
        n = next((int(a) for a in sys.argv if a.isdigit()), 60)
        print(f"[marketscreener] upsert {persist(n)} bản ghi physical vào fact_price")
    else:
        for d in fetch(3):
            print(f"\n{d['as_of']} — {d['url'].rsplit('/', 1)[-1][:50]}")
            for r in d["rows"]:
                print(f"  {r['grade']:24} {r['value']:>7} {r['unit']}")
