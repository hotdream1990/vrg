"""Crawler giá Asian physical rubber từ marketscreener.com (chuỗi Reuters hằng ngày).

Akamai chặn headless CHROMIUM → DÙNG FIREFOX (vân tay khác, qua được). Bài giá là member
content → cần đăng nhập (MARKETSCREENER_USER/PASS trong .env). Mỗi bài "Asian physical rubber
prices - <ngày>" có bảng grade→giá (baht/kg cho Thái, $/kg cho Malaysia/Indonesia).

Chạy thử: uv run python -m crawlers.marketscreener   (in dữ liệu vài bài gần nhất)
"""
from __future__ import annotations

import os
import re
import time
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


def _proxy_opt() -> dict[str, str] | None:
    """Proxy tùy chọn (MARKETSCREENER_PROXY=http://user:pass@host:port). Akamai chặn theo
    IP+fingerprint: Firefox qua được từ IP residential/mobile sạch; IP bị gắn cờ thì cần
    proxy residential. Proxy datacenter thường vẫn bị 403."""
    raw = os.environ.get("MARKETSCREENER_PROXY")
    if not raw:
        return None
    from urllib.parse import urlparse
    u = urlparse(raw)
    return {"server": f"{u.scheme}://{u.hostname}:{u.port}",
            "username": u.username or "", "password": u.password or ""}


def _cookie(pg) -> None:
    for sel in ("#didomi-notice-agree-button", "button:has-text('Agree')", "button:has-text('Accept')"):
        try:
            el = pg.query_selector(sel)
            if el and el.is_visible():
                el.click(); pg.wait_for_timeout(600); return
        except Exception:  # noqa: BLE001
            pass


_LOGIN_RETRIES = 4  # anti-bot marketscreener chập chờn → thử lại vài lần (mỗi lần 1 context sạch)


def _login_probe(pg, u: str, p: str) -> dict[str, Any]:
    """1 lần thử đăng nhập (KHÔNG raise) → {ok, stage, message}. Dùng chung cho fetch + test_login."""
    pg.goto(BASE + "/login/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(1800); _cookie(pg)
    if "Access Denied" in (pg.title() or ""):
        return {"ok": False, "stage": "akamai", "message": "Akamai chặn IP (403). Cần proxy residential/mobile sạch."}
    pg.fill("input[type=email]", u)
    pg.click("button:has-text('Continue with an email')"); pg.wait_for_timeout(2200); _cookie(pg)
    pg.wait_for_selector("input[type=password]", timeout=10000)
    pg.fill("input[type=password]", p)
    for sel in ("button:has-text('Log in')", "button:has-text('Sign in')", "button:has-text('Continue')", "button[type=submit]"):
        el = pg.query_selector(sel)
        if el and el.is_visible():
            el.click(); break
    pg.wait_for_timeout(5000)
    if "login" not in pg.url.lower():
        return {"ok": True, "stage": "done", "message": "Đăng nhập thành công."}
    body = pg.inner_text("body").lower()
    if "session has expired" in body:
        return {"ok": False, "stage": "login",
                "message": "Bị 'session expired' — IP proxy bị anti-bot chặn ở bước login (chập chờn)."}
    if "invalid" in body or "incorrect" in body or "wrong" in body:
        return {"ok": False, "stage": "login", "message": "Sai tài khoản hoặc mật khẩu."}
    return {"ok": False, "stage": "login", "message": "Đăng nhập không thành công (sai mật khẩu hoặc anti-bot chặn)."}


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


def _load_config_from_db() -> None:
    """Nạp tài khoản/proxy từ app_config (admin cấu hình trên UI) vào os.environ — ƯU TIÊN hơn .env.

    DB không sẵn sàng → bỏ qua, dùng .env như cũ.
    """
    try:
        import psycopg
        dsn = os.environ.get("DATABASE_URL", "postgresql://vrg:changeme@localhost:5433/vrg_caosu")
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_config WHERE key LIKE 'MARKETSCREENER%' "
                "AND value IS NOT NULL AND value <> ''"
            ).fetchall()
        for k, v in rows:
            os.environ[k] = v
    except Exception:  # noqa: BLE001 - DB chưa sẵn sàng → dùng .env
        pass


def fetch(n: int = 5) -> list[dict[str, Any]]:
    """Đăng nhập (thử lại vì anti-bot chập chờn) + lấy n bài 'Asian physical rubber prices', parse bảng giá."""
    _load_config_from_db()
    u, p = os.environ.get("MARKETSCREENER_USER"), os.environ.get("MARKETSCREENER_PASS")
    if not u or not p:
        raise RuntimeError("Thiếu MARKETSCREENER_USER / MARKETSCREENER_PASS trong cấu hình")
    with sync_playwright() as pw:
        b = pw.firefox.launch(headless=True)
        try:
            for attempt in range(_LOGIN_RETRIES):
                ctx_opts: dict[str, Any] = {"locale": "en-US", "viewport": {"width": 1366, "height": 1000}}
                if (px := _proxy_opt()):
                    ctx_opts["proxy"] = px
                ctx = b.new_context(**ctx_opts)
                pg = ctx.new_page()
                try:
                    if _login_probe(pg, u, p)["ok"]:
                        return [d for url in _article_urls(pg, n) if (d := _parse_article(pg, url))]
                except Exception:  # noqa: BLE001 - Akamai/timeout/anti-bot → thử lại
                    pass
                finally:
                    ctx.close()
                if attempt < _LOGIN_RETRIES - 1:
                    time.sleep(6)  # nghỉ giữa các lần → tránh rate-limit
            raise RuntimeError("Đăng nhập marketscreener thất bại sau nhiều lần (anti-bot chặn)")
        finally:
            b.close()


def _to_usd_tonne(value: float, unit: str, thb: float | None) -> int | None:
    """baht/kg → USD/T (cần tỷ giá USD/THB); USD/kg → USD/T (×1000)."""
    if unit == "USD/kg":
        return round(value * 1000)
    if unit == "baht/kg" and thb:
        return round(value * 1000 / thb)
    return None


def persist(n: int = 60, dsn: str | None = None) -> int:
    """Lấy n bài + quy đổi USD/T + upsert fact_price (reuters, physical) + ghi meta_crawl_run.

    Ghi lại lần quét (ok/empty/error) vào meta_crawl_run để hiện trên Nhật ký quét của UI;
    lỗi (vd Akamai 403) vẫn được ghi rồi raise lại để cron biết exit code.
    """
    import psycopg
    from datetime import datetime, timezone
    dsn = dsn or os.environ.get("DATABASE_URL", "postgresql://vrg:changeme@localhost:5433/vrg_caosu")
    started = datetime.now(timezone.utc)
    status, err, recs = "ok", None, []
    try:
        arts = fetch(n)
    except Exception as exc:  # noqa: BLE001 - vẫn ghi run lỗi để hiện trên Nhật ký
        arts, status, err = [], "error", str(exc)[:400]
    with psycopg.connect(dsn) as conn:
        if arts:
            thb_rows = conn.execute("SELECT as_of, price FROM fact_price WHERE source='fx' "
                                    "AND grade='USD/THB' ORDER BY as_of").fetchall()
            def thb_at(d):  # tỷ giá USD/THB gần nhất <= ngày bài
                prior = [r for r in thb_rows if str(r[0]) <= d]
                return float(prior[-1][1]) if prior else None
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
        if status != "error" and not recs:
            status = "empty"
        conn.execute(
            "INSERT INTO meta_crawl_run (started_at, finished_at, sources, status, rows, error) "
            "VALUES (%s, now(), 'marketscreener', %s, %s, %s)", (started, status, len(recs), err))
        conn.commit()
    if status == "error":
        raise RuntimeError(err)
    return len(recs)


def test_login(retries: int = 3) -> dict[str, Any]:
    """Chạy thử ĐĂNG NHẬP (thử lại vài lần vì anti-bot chập chờn) → {ok, stage, message} cho nút 'Chạy thử'.

    Không lấy bài, chỉ kiểm tra login. Dừng sớm khi thành công / thiếu creds / Akamai chặn.
    Dùng chung flow _login_probe với fetch().
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    _load_config_from_db()
    u, p = os.environ.get("MARKETSCREENER_USER"), os.environ.get("MARKETSCREENER_PASS")
    if not u or not p:
        return {"ok": False, "stage": "config", "message": "Thiếu tài khoản hoặc mật khẩu marketscreener."}
    last: dict[str, Any] = {"ok": False, "stage": "error", "message": "Chưa chạy được."}
    with sync_playwright() as pw:
        b = pw.firefox.launch(headless=True)
        try:
            for attempt in range(retries):
                opts: dict[str, Any] = {"locale": "en-US", "viewport": {"width": 1366, "height": 900}}
                if (px := _proxy_opt()):
                    opts["proxy"] = px
                ctx = b.new_context(**opts)
                pg = ctx.new_page()
                try:
                    last = _login_probe(pg, u, p)
                except PWTimeout:
                    last = {"ok": False, "stage": "akamai", "message": "Timeout tải trang — proxy không thông hoặc mạng chặn."}
                except Exception as exc:  # noqa: BLE001
                    last = {"ok": False, "stage": "error", "message": f"Lỗi: {str(exc)[:120]}"}
                finally:
                    ctx.close()
                if last["ok"] or last["stage"] in ("config", "akamai"):
                    break
                if attempt < retries - 1:
                    time.sleep(5)
        finally:
            b.close()
    if not last["ok"] and last.get("stage") == "login":
        last["message"] += f" (đã thử {retries} lần)"
    return last


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        import json
        print(json.dumps(test_login(), ensure_ascii=False))
    elif "--persist" in sys.argv:
        n = next((int(a) for a in sys.argv if a.isdigit()), 60)
        print(f"[marketscreener] upsert {persist(n)} bản ghi physical vào fact_price")
    else:
        for d in fetch(3):
            print(f"\n{d['as_of']} — {d['url'].rsplit('/', 1)[-1][:50]}")
            for r in d["rows"]:
                print(f"  {r['grade']:24} {r['value']:>7} {r['unit']}")
