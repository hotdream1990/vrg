"""Tin 'Giá cao su hôm nay' (vietnambiz) ĐÚNG KỲ báo cáo tuần — mọi bài trong kỳ, không chỉ bài mới nhất.

Đọc trang chuyên mục + các trang `/trang-N.html` (tối đa MAX_PAGES), mở từng bài lấy NGÀY ĐĂNG từ
meta `article:published_time` (dự phòng `pubdate` / JSON-LD `datePublished`) rồi giữ bài đăng trong
[date_from, date_to + 1 ngày] — bài sáng thứ Bảy tổng kết phiên thứ Sáu. Ngày trong tiêu đề/URL
không dùng (URL ghép ngày tháng không có số 0 đệm nên đọc nhập nhằng).
Lỗi mạng → trả danh sách rỗng + log, không ném ra router.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx

from app.services.market_analysis import _UA, _clean_article

logger = logging.getLogger(__name__)

MAX_PAGES = 5
_PAGE_TTL_S = 30 * 60        # trang chuyên mục đổi liên tục → nhớ 30'
_ARTICLE_CACHE_MAX = 400     # bài đã đăng không đổi ngày đăng → nhớ lâu, giới hạn số lượng
_LINK_RE = re.compile(r'href="((?:https?://vietnambiz\.vn)?/gia-cao-su-hom-nay-[^"#?]+\.htm)"')
_PUBLISHED_RES = (
    re.compile(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"', re.I),
    re.compile(r'<meta[^>]+name="pubdate"[^>]+content="([^"]+)"', re.I),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"'),
)
_TITLE_RES = (
    re.compile(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', re.I),
    re.compile(r"<title>([^<]*)</title>", re.I),
)
_page_cache: dict[str, tuple[float, str]] = {}
_article_cache: dict[str, dict[str, str]] = {}
_cache_lock = threading.Lock()


def page_url(index_url: str, n: int) -> str | None:
    """Trang thứ n của chuyên mục: '.../gia-cao-su.html' → '.../gia-cao-su/trang-2.html'."""
    if n <= 1:
        return index_url
    if not index_url.endswith(".html"):
        return None  # link cấu hình không theo khuôn chuyên mục vietnambiz → chỉ đọc trang đầu
    return f"{index_url[:-len('.html')]}/trang-{n}.html"


def article_links(page_html: str, base_url: str) -> list[str]:
    """Link bài 'Giá cao su hôm nay' trên 1 trang chuyên mục (bỏ trùng, giữ thứ tự)."""
    seen: dict[str, None] = {}
    for m in _LINK_RE.finditer(page_html or ""):
        seen.setdefault(urljoin(base_url, m.group(1)), None)
    return list(seen)


def parse_published(article_html: str) -> str | None:
    """Thời điểm đăng bài (chuỗi ISO gốc, vd '2026-08-29T07:55:00') hoặc None."""
    for rx in _PUBLISHED_RES:
        m = rx.search(article_html or "")
        if m and re.match(r"^\d{4}-\d{2}-\d{2}", m.group(1).strip()):
            return m.group(1).strip()
    return None


def parse_title(article_html: str) -> str:
    for rx in _TITLE_RES:
        m = rx.search(article_html or "")
        if m and m.group(1).strip():
            return html_lib.unescape(m.group(1).strip())
    return ""


_MAX_BYTES = 2 * 1024 * 1024   # 1 trang chuyên mục/bài vietnambiz ~200 KB — trần chặn phản hồi phình
_MAX_SECONDS = 25              # hạn TỔNG mỗi lần tải (timeout httpx chỉ tính từng lần đọc)
_MAX_REDIRECTS = 3


def _get(url: str) -> str:
    """Tải 1 trang vietnambiz. Chặn SSRF: mọi URL (kể cả đích redirect) phải thuộc vietnambiz.vn."""
    from app.services.weekly_source_repo import is_vietnambiz_url

    started = time.monotonic()
    for _ in range(_MAX_REDIRECTS + 1):
        if not is_vietnambiz_url(url):
            raise ValueError(f"Bỏ qua URL ngoài vietnambiz.vn: {url[:120]}")
        with httpx.stream("GET", url, headers={"User-Agent": _UA}, follow_redirects=False,
                          timeout=15) as resp:
            if resp.is_redirect:
                url = str(resp.url.join(resp.headers.get("location", "")))
                continue
            resp.raise_for_status()
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > _MAX_BYTES or time.monotonic() - started > _MAX_SECONDS:
                    raise ValueError(f"Trang quá lớn hoặc tải quá lâu: {url[:120]}")
                chunks.append(chunk)
            return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    raise ValueError(f"Chuyển hướng quá nhiều lần: {url[:120]}")


def _page(url: str) -> str:
    hit = _page_cache.get(url)
    if hit and time.monotonic() - hit[0] < _PAGE_TTL_S:
        return hit[1]
    body = _get(url)
    _page_cache[url] = (time.monotonic(), body)
    return body


def _article(url: str) -> dict[str, str] | None:
    """{url, title, published_at, body} — None nếu lỗi mạng hoặc không đọc được ngày đăng."""
    if url in _article_cache:
        return _article_cache[url]
    try:
        raw = _get(url)
    except Exception as exc:  # noqa: BLE001 - 1 bài lỗi thì bỏ bài đó
        logger.warning("[weekly-news] Không mở được bài %s: %s", url, exc)
        return None
    published = parse_published(raw)
    if not published:
        return None
    item = {"url": url, "title": parse_title(raw), "published_at": published, "body": _clean_article(raw)}
    with _cache_lock:  # các bài được mở song song
        if len(_article_cache) >= _ARTICLE_CACHE_MAX:
            _article_cache.pop(next(iter(_article_cache)))
        _article_cache[url] = item
    return item


def _spread(items: list[Any], k: int) -> list[Any]:
    """Chọn k phần tử trải đều cả kỳ (giữ bài đầu và bài cuối) khi có nhiều bài hơn trần."""
    n = len(items)
    if n <= k:
        return items
    if k <= 1:
        return items[-1:] if k == 1 else []
    return [items[round(i * (n - 1) / (k - 1))] for i in range(k)]


def fetch_period_articles(index_url: str, date_from: date, date_to: date, max_articles: int = 12,
                          max_chars_each: int = 1800) -> list[dict[str, str]]:
    """Mọi bài 'Giá cao su hôm nay' đăng trong kỳ → [{url, title, published 'YYYY-MM-DD', body}] tăng dần."""
    lo, hi = date_from.isoformat(), (date_to + timedelta(days=1)).isoformat()
    found: dict[str, dict[str, str]] = {}
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for n in range(1, MAX_PAGES + 1):
                url = page_url(index_url, n)
                if not url:
                    break
                links = article_links(_page(url), url)
                articles = [a for a in pool.map(_article, links) if a]
                if not articles:
                    break
                for a in articles:
                    if lo <= a["published_at"][:10] <= hi:
                        found[a["url"]] = a
                # Cả trang (kể cả bài mới nhất) đã cũ hơn đầu kỳ → các trang sau chỉ còn bài cũ hơn.
                # Xét bài MỚI nhất chứ không phải cũ nhất: trang chuyên mục hay chèn vài bài cũ nổi bật.
                if max(a["published_at"][:10] for a in articles) < lo:
                    break
    except Exception as exc:  # noqa: BLE001 - thiếu trang = thiếu bài trong kỳ → không trả nửa vời
        logger.warning("[weekly-news] Đọc chuyên mục %s lỗi: %s", index_url, exc)
        return []
    ordered = sorted(found.values(), key=lambda a: (a["published_at"], a["url"]))
    return [{"url": a["url"], "title": a["title"], "published": a["published_at"][:10],
             "body": a["body"][:max_chars_each]} for a in _spread(ordered, max_articles)]
