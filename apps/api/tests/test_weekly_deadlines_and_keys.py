"""Báo cáo tuần — hạn chờ tổng (khối ngữ cảnh AI, chỉ số Yahoo song song), làm tròn nửa lên của chỉ số,
chuẩn hoá khoá tuần ở router (hàm thuần/monkeypatch — không DB, không mạng)."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app.routers.weekly_reports import week_key_or_400
from app.services import weekly_market_feed as feed
from app.services import weekly_period, weekly_source_repo
from app.services.weekly_ai_context import run_blocks


def _slow() -> list[str]:
    time.sleep(2)
    return ["không kịp"]


def _boom() -> list[str]:
    raise RuntimeError("hỏng")


def test_run_blocks_drops_timed_out_and_failed_blocks() -> None:
    t0 = time.monotonic()
    blocks = run_blocks([("nhanh", lambda: ["a"]), ("chậm", _slow), ("lỗi", _boom)], deadline_s=0.3)
    assert blocks == [["a"], [], []]
    assert time.monotonic() - t0 < 1.5            # không chờ luồng chậm chạy xong


def test_summarize_closes_rounds_half_up_on_displayed_values() -> None:
    weeks = weekly_period.period("2026-08-24", 1)["weeks"]
    closes = [("2026-08-17", 98.125), ("2026-08-24", 98.135), ("2026-08-25", 98.135)]
    s = feed.summarize_closes(closes, weeks)
    assert s["values"] == [98.13, 98.14]          # round() Python sẽ cho 98.12 (làm tròn về số chẵn)
    assert s["changes"] == [0.01] and s["changes_pct"] == [0.01]
    assert s["last_closes"] == [98.13, 98.14] and s["high"] == {"value": 98.14, "date": "24/08"}


def test_weekly_indicators_parallel_with_total_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    srcs = [{"id": i, "name": n, "role": "r", "url": "u", "mode": "market_feed", "feed_symbol": sym}
            for i, (n, sym) in enumerate([("DXY", "DX-Y.NYB"), ("WTI", "CL=F"), ("Brent", "BZ=F")])]
    monkeypatch.setattr(weekly_source_repo, "list_sources", lambda enabled_only=False: srcs)
    monkeypatch.setattr(feed, "FEED_DEADLINE_S", 0.5)

    def fake_fetch(symbol, date_from, date_to):
        if symbol == "CL=F":
            time.sleep(3)
        return [("2026-08-24", 100.0)]

    monkeypatch.setattr(feed, "fetch_daily_closes", fake_fetch)
    t0 = time.monotonic()
    items = feed.weekly_indicators(weekly_period.period("2026-08-24", 1)["weeks"])
    assert time.monotonic() - t0 < 2
    assert [i["symbol"] for i in items] == ["DX-Y.NYB", "CL=F", "BZ=F"]   # giữ thứ tự nguồn
    assert items[0]["error"] is None and items[0]["values"] == [None, 100.0]
    assert "quá hạn" in items[1]["error"] and items[1]["values"] == [None, None]


def test_week_key_normalized_to_iso_monday() -> None:
    assert week_key_or_400("2026-08-27") == "2026-08-24"
    assert week_key_or_400("2026-08-24") == "2026-08-24"
    with pytest.raises(HTTPException) as exc:
        week_key_or_400("2026-13-01")
    assert exc.value.status_code == 400
