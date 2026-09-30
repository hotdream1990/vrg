"""Test chặn dồn tải SCADA (khoá theo nhà máy + cache 60s) và khung kỳ/truy vấn của `/meters/daily`
— thuần hàm, không cần DB/SQL Server."""

from __future__ import annotations

import threading
from datetime import date, datetime

import pytest
from fastapi import HTTPException

from app.routers.smart_factory import query_bounds, resolve_period
from app.services import scada_read_guard as guard

F = {"id": 901, "updated_at": datetime(2026, 9, 30, 15, 0)}
START, END = datetime(2026, 9, 1), datetime(2026, 9, 3, 1)
TODAY = date(2026, 9, 30)


@pytest.fixture(autouse=True)
def _fresh_cache():
    guard.clear_cache()
    yield
    guard.clear_cache()


def _reader(calls: list):
    def read(factory, start, end):
        calls.append((factory["id"], start, end))
        return [("hourly", len(calls))], []
    return read


# ── Cache ──

def test_cache_hit_within_ttl_and_expires_after(monkeypatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr(guard, "_clock", lambda: clock[0])
    calls: list = []
    first = guard.read(F, START, END, _reader(calls))
    assert guard.read(F, START, END, _reader(calls)) == first and len(calls) == 1
    clock[0] += guard.CACHE_TTL_S - 1
    guard.read(F, START, END, _reader(calls))
    assert len(calls) == 1
    clock[0] += 2  # quá 60s → đọc lại SCADA
    assert guard.read(F, START, END, _reader(calls)) != first and len(calls) == 2


def test_cache_key_includes_config_version_and_period() -> None:
    calls: list = []
    guard.read(F, START, END, _reader(calls))
    guard.read({**F, "updated_at": datetime(2026, 9, 30, 16, 0)}, START, END, _reader(calls))
    guard.read(F, START, None, _reader(calls))
    guard.read({**F, "id": 902}, START, END, _reader(calls))
    assert len(calls) == 4


def test_errors_are_not_cached() -> None:
    calls: list = []

    def boom(factory, start, end):
        calls.append(1)
        raise RuntimeError("SCADA lỗi")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            guard.read(F, START, END, boom)
    assert len(calls) == 2
    assert not guard.factory_lock(F["id"]).locked()  # lỗi vẫn nhả khoá


# ── Khoá theo nhà máy ──

def test_busy_factory_raises_after_wait(monkeypatch) -> None:
    monkeypatch.setattr(guard, "LOCK_WAIT_S", 0.05)
    calls: list = []
    lock = guard.factory_lock(F["id"])
    lock.acquire()
    try:
        with pytest.raises(guard.ScadaBusyError, match="Đang đọc số liệu SCADA"):
            guard.read(F, START, END, _reader(calls))
        guard.read({**F, "id": 903}, START, END, _reader(calls))  # nhà máy khác không bị chặn
    finally:
        lock.release()
    assert calls == [(903, START, END)]


def test_waiting_request_reuses_result_of_the_running_one() -> None:
    """Lượt 2 chờ khoá trong lúc lượt 1 đang đọc cùng kỳ → nhận luôn kết quả, không đọc lại."""
    calls: list = []
    started, release = threading.Event(), threading.Event()

    def slow(factory, start, end):
        calls.append(1)
        started.set()
        release.wait(2)
        return ["slow"], []
    results: list = []
    t1 = threading.Thread(target=lambda: results.append(guard.read(F, START, END, slow)))
    t1.start()
    started.wait(2)
    t2 = threading.Thread(target=lambda: results.append(guard.read(F, START, END, slow)))
    t2.start()
    release.set()
    t1.join(3)
    t2.join(3)
    assert len(calls) == 1 and results == [(["slow"], []), (["slow"], [])]


# ── Kỳ xem + khung truy vấn ──

def test_resolve_period_92_days_ok_93_rejected() -> None:
    assert resolve_period("2026-07-01", "2026-09-30", TODAY) == (date(2026, 7, 1), TODAY)
    with pytest.raises(HTTPException) as err:
        resolve_period("2026-06-30", "2026-09-30", TODAY)
    assert err.value.status_code == 400 and "tối đa 92 ngày" in err.value.detail


def test_resolve_period_future_from_and_clamp_to() -> None:
    with pytest.raises(HTTPException) as err:
        resolve_period("2026-10-01", None, TODAY)
    assert err.value.detail == "Từ ngày không được sau hôm nay."
    assert resolve_period("2026-09-29", "2026-12-31", TODAY) == (date(2026, 9, 29), TODAY)
    assert resolve_period(None, None, TODAY) == (date(2026, 9, 1), TODAY)
    with pytest.raises(HTTPException) as err:
        resolve_period("2026-09-10", "2026-09-01", TODAY)
    assert "từ ngày sau đến ngày" in err.value.detail


def test_query_bounds_past_period_adds_one_hour_today_uses_scada_clock() -> None:
    assert query_bounds(date(2026, 9, 1), date(2026, 9, 2), TODAY) == (START, END)
    assert query_bounds(date(2026, 9, 1), TODAY, TODAY) == (START, None)
