"""Test email cảnh báo quét giá (services/scan_alert_email.py) — không DB, không SMTP thật.

`config_repo.get_value/set_value` được thay bằng dict trong bộ nhớ; `send` là hàm giả đếm số lần gửi.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import config_repo
from app.services import scan_alert_email as alert

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
MORNING = datetime(2026, 9, 13, 6, 30, tzinfo=TZ)
EVENING = datetime(2026, 9, 13, 18, 0, tzinfo=TZ)
NEXT_DAY = datetime(2026, 9, 14, 6, 30, tzinfo=TZ)

_STALE = [{"pair": "USD/JPY", "latest": "2026-09-02", "lag": 7}]


def _result(stale=_STALE, fx_note="x-rates thiếu: JPY,CNY,THB", lgm_status="ok", db="ok") -> dict:
    return {
        "run_id": 42, "db": db, "stale_fx": list(stale),
        "sources": [
            {"source": "fx", "status": "ok", "count": 6, "note": fx_note},
            {"source": "lgm", "status": lgm_status, "count": 0 if lgm_status != "ok" else 5,
             "note": "[Errno 113] No route to host" if lgm_status != "ok" else None},
        ],
        "warnings": ["Tỷ giá: x-rates thiếu: JPY,CNY,THB", "Tỷ giá quá cũ: USD/JPY 02/09 (trễ 7 phiên)"],
    }


@pytest.fixture()
def store(monkeypatch):
    data: dict[str, str] = {alert.RECIPIENTS_KEY: "it@vrg.vn, ttkd@vrg.vn;it@vrg.vn"}
    monkeypatch.setattr(config_repo, "get_value", lambda k, fallback=None: data.get(k) or fallback)
    monkeypatch.setattr(config_repo, "set_value", lambda k, v, by=None: data.__setitem__(k, v))
    return data


class FakeSend:
    def __init__(self, ok: bool = True) -> None:
        self.calls: list[tuple[list[str], str, str]] = []
        self.ok = ok

    def __call__(self, to, subject, body):
        self.calls.append((to, subject, body))
        return (True, "") if self.ok else (False, "SMTP down")


def test_same_issue_set_sends_once_per_day(store) -> None:
    send = FakeSend()
    assert alert.notify(_result(), send=send, now=MORNING) == "sent"
    assert alert.notify(_result(), send=send, now=EVENING) == "duplicate"
    assert len(send.calls) == 1
    to, subject, body = send.calls[0]
    assert to == ["it@vrg.vn", "ttkd@vrg.vn"]
    assert "tỷ giá quá cũ" in subject and "USD/JPY 02/09 (trễ 7 phiên)" in body
    # Sang ngày mới, vấn đề vẫn còn → nhắc lại 1 lần.
    assert alert.notify(_result(), send=send, now=NEXT_DAY) == "sent"
    assert len(send.calls) == 2


def test_different_issue_set_same_day_sends_again(store) -> None:
    send = FakeSend()
    assert alert.notify(_result(), send=send, now=MORNING) == "sent"
    assert alert.notify(_result(lgm_status="error"), send=send, now=EVENING) == "sent"
    # Quay lại đúng tập vấn đề đã gửi sáng nay → không gửi nữa.
    assert alert.notify(_result(), send=send, now=EVENING) == "duplicate"
    assert len(send.calls) == 2


def test_digits_in_notes_do_not_break_dedupe() -> None:
    a = _result(fx_note="SGX chưa có báo cáo phiên 12/09/2026")
    b = _result(fx_note="SGX chưa có báo cáo phiên 13/09/2026")
    assert alert.issue_keys(a) == alert.issue_keys(b)


def test_clean_run_or_no_recipients_sends_nothing(store) -> None:
    send = FakeSend()
    clean = {"run_id": 1, "db": "ok", "stale_fx": [], "warnings": [],
             "sources": [{"source": "fx", "status": "ok", "count": 6, "note": None}]}
    assert alert.notify(clean, send=send, now=MORNING) == "clean"
    store[alert.RECIPIENTS_KEY] = "  "
    assert alert.notify(_result(), send=send, now=MORNING) == "no_recipients"
    assert send.calls == []


def test_failed_send_is_retried_next_scan(store) -> None:
    assert alert.notify(_result(), send=FakeSend(ok=False), now=MORNING) == "send_failed"
    assert alert.LAST_KEY not in store
    assert alert.notify(_result(), send=FakeSend(), now=EVENING) == "sent"


def test_exceptions_never_escape(store, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("DB down")

    monkeypatch.setattr(config_repo, "get_value", boom)
    assert alert.notify(_result(), send=FakeSend(), now=MORNING) == "error"


def test_db_write_failure_is_an_issue(store) -> None:
    keys = alert.issue_keys(_result(stale=[], fx_note=None, db="error:IntegrityError"))
    assert keys == ["db:error:IntegrityError"]


def test_corrupt_last_value_is_ignored(store) -> None:
    store[alert.LAST_KEY] = "{not json"
    assert alert.notify(_result(), send=FakeSend(), now=MORNING) == "sent"
