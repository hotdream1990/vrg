"""Chỉ số thị trường cho Báo cáo tuần (DXY · WTI · Brent …) — giá đóng cửa NGÀY, gom theo tuần.

Investing.com (link trong danh mục nguồn) chặn bot HTTP 403 → số lấy qua `weekly_market_feed_sources`
(CNBC chính, Yahoo Finance dự phòng) theo `feed_symbol` của nguồn `mode=market_feed`. Nguyên tắc số liệu:
  - Ngày = ngày giao dịch của sàn, KHÔNG dùng giờ máy chủ.
  - Phiên không có giá đóng cửa → bỏ; tuần không có phiên nào → None. KHÔNG lấy giá ngày khác bù vào.
  - Lỗi 1 mã chỉ ghi `error` cho mã đó, các mã khác vẫn trả số. Các mã lấy SONG SONG, hạn chờ tổng
    `FEED_DEADLINE_S`; mã quá hạn ghi `error`.
  - Làm tròn 2 số lẻ nửa LÊN (`r2` của bulletin.convert); +/- và % tính trên số TB ĐÃ làm tròn (khớp số
    hiển thị).
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date
from typing import Any

from app.services.weekly_market_feed_sources import fetch_any, parse_chart  # noqa: F401 - parse_chart dùng lại ở test
from app.services.weekly_report_tables import r2

logger = logging.getLogger(__name__)

CACHE_TTL_S = 30 * 60
FEED_DEADLINE_S = 30   # hạn chờ TỔNG mọi mã (mỗi mã: CNBC rồi tới 2 host Yahoo, mỗi lượt ≤ 15 giây)
_FEED_WORKERS = 4
_cache: dict[tuple[str, str, str], tuple[float, list[tuple[str, float]]]] = {}


def fetch_daily_closes(symbol: str, date_from: date, date_to: date) -> list[tuple[str, float]]:
    """Giá đóng cửa ngày trong [date_from, date_to] (cache 30'). CNBC → Yahoo; ném lỗi nếu cả hai hỏng."""
    key = (symbol, date_from.isoformat(), date_to.isoformat())
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    rows = [(d, c) for d, c in fetch_any(symbol, date_from, date_to)
            if date_from.isoformat() <= d <= date_to.isoformat()]
    _cache[key] = (time.monotonic(), rows)
    return rows


def _r(v: float | None) -> float | None:
    return None if v is None else r2(v)


def _dm(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m")


def summarize_closes(closes: list[tuple[str, float]], weeks: list[dict[str, Any]]) -> dict[str, Any]:
    """Gom giá đóng cửa ngày theo tuần (hàm thuần): TB tuần, giá chốt tuần, +/- và cao/thấp CẢ KỲ.

    `weeks` = period()['weeks'] — [tuần mốc, tuần 1..n]; cao/thấp chỉ xét các tuần TRONG KỲ.
    """
    per_week = [[(d, c) for d, c in closes if w["mon"] <= d <= w["fri"]] for w in weeks]
    values = [_r(sum(c for _, c in pts) / len(pts)) if pts else None for pts in per_week]
    last_closes = [_r(pts[-1][1]) if pts else None for pts in per_week]
    changes, changes_pct = [], []
    for a, b in zip(values, values[1:]):
        ok = a is not None and b is not None
        changes.append(_r(b - a) if ok else None)
        changes_pct.append(_r((b - a) / a * 100) if ok and a else None)
    in_span = [p for pts in per_week[1:] for p in pts]
    high = max(in_span, key=lambda p: p[1]) if in_span else None
    low = min(in_span, key=lambda p: p[1]) if in_span else None
    return {
        "values": values, "changes": changes, "changes_pct": changes_pct, "last_closes": last_closes,
        "high": {"value": _r(high[1]), "date": _dm(high[0])} if high else None,
        "low": {"value": _r(low[1]), "date": _dm(low[0])} if low else None,
    }


def _empty(n: int) -> dict[str, Any]:
    return {"values": [None] * n, "changes": [None] * max(n - 1, 0),
            "changes_pct": [None] * max(n - 1, 0), "last_closes": [None] * n, "high": None, "low": None}


def _base_item(src: dict[str, Any]) -> dict[str, Any]:
    return {"source_id": src["id"], "name": src["name"], "role": src["role"], "url": src["url"],
            "symbol": src["feed_symbol"], "error": None}


def _indicator(src: dict[str, Any], weeks: list[dict[str, Any]], date_from: date, date_to: date) -> dict[str, Any]:
    item = _base_item(src)
    try:
        return item | summarize_closes(fetch_daily_closes(src["feed_symbol"], date_from, date_to), weeks)
    except Exception as exc:  # noqa: BLE001 - lỗi 1 mã không làm hỏng mã khác
        logger.warning("[weekly-feed] %s lỗi: %s", src["feed_symbol"], exc)
        return _failed(item, len(weeks), f"({str(exc)[:160]})")


def _failed(item: dict[str, Any], n: int, why: str) -> dict[str, Any]:
    return item | _empty(n) | {"error": f"Không lấy được số liệu mã {item['symbol']} (CNBC/Yahoo Finance) {why}."}


def weekly_indicators(weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mọi nguồn đang bật `mode=market_feed` → số liệu theo tuần của kỳ báo cáo (giữ thứ tự nguồn)."""
    from app.services import weekly_source_repo

    if not weeks:
        return []
    date_from, date_to = date.fromisoformat(weeks[0]["mon"]), date.fromisoformat(weeks[-1]["fri"])
    srcs = [s for s in weekly_source_repo.list_sources(enabled_only=True)
            if s["mode"] == "market_feed" and s.get("feed_symbol")]
    if not srcs:
        return []
    pool = ThreadPoolExecutor(max_workers=_FEED_WORKERS)
    try:
        futures = [pool.submit(_indicator, s, weeks, date_from, date_to) for s in srcs]
        wait(futures, timeout=FEED_DEADLINE_S)
        out = []
        for src, f in zip(srcs, futures):
            if f.done():
                out.append(f.result())
                continue
            logger.warning("[weekly-feed] %s quá hạn %ss", src["feed_symbol"], FEED_DEADLINE_S)
            out.append(_failed(_base_item(src), len(weeks), f"(quá hạn {FEED_DEADLINE_S} giây)"))
        return out
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
