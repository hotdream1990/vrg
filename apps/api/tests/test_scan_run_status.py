"""Test trạng thái TRUNG THỰC của lượt quét (scan_run_summary + scan_service + ScanResponse).

Sự cố 09/2026: crawler tỷ giá trả OK + note "x-rates thiếu" mà lượt quét vẫn ghi `ok` → 11 ngày
không ai biết. Nay lượt quét phải ra `warning` và ghi lý do vào meta_crawl_run.error.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.schemas.price import ScanResponse
from app.services import fx_freshness, scan_service
from app.services import scan_run_summary as s

_OK = {"source": "sgx", "status": "ok", "count": 2, "note": None}
_STALE = [{"pair": "USD/JPY", "latest": "2026-09-02", "lag": 7}]


def test_clean_run_is_ok() -> None:
    w = s.run_warnings([_OK, {"source": "shfe", "status": "ok", "count": 1, "note": None}], [])
    assert w == [] and s.run_status("ok", w) == "ok" and s.run_note(w) is None


def test_ok_source_with_error_note_is_warning() -> None:
    """Đúng ca thật: fx OK (VND/MYR vẫn lấy được) nhưng thiếu JPY/CNY/THB."""
    fx = {"source": "fx", "status": "ok", "count": 6, "note": "x-rates thiếu: JPY,CNY,THB"}
    w = s.run_warnings([_OK, fx], _STALE)
    assert s.run_status("ok", w) == "warning"
    assert s.run_note(w) == ("Tỷ giá: x-rates thiếu: JPY,CNY,THB · "
                             "Tỷ giá quá cũ: USD/JPY 02/09 (trễ 7 phiên)")


def test_informational_notes_do_not_warn() -> None:
    """No Trading / lấy phiên trước (báo cáo hôm nay chưa đăng) là bình thường — không báo động giả."""
    srcs = [
        {"source": "sgx", "status": "ok", "count": 2,
         "note": "Phiên 10/08/2026: SGX không ra settlement cho cao su (No Trading)."},
        {"source": "tocom", "status": "ok", "count": 2,
         "note": "OSE chưa có báo cáo ngày 13/09/2026 — lấy phiên 11/09/2026."},
    ]
    assert s.run_warnings(srcs, []) == []


def test_non_ok_status_and_mixed_note_warn() -> None:
    srcs = [
        {"source": "lgm", "status": "error", "count": 0, "note": "[Errno 113] No route to host"},
        {"source": "shfe", "status": "empty", "count": 0, "note": None},
        {"source": "fx", "status": "blocked", "count": 0, "note": None},
        {"source": "tocom", "status": "ok", "count": 1, "note": "lấy phiên 11/09; parse lỗi cột SETTLE"},
    ]
    assert s.run_warnings(srcs, []) == [
        "MRB: lỗi — [Errno 113] No route to host", "SHFE: không có dữ liệu",
        "Tỷ giá: bị chặn", "OSE: parse lỗi cột SETTLE",
    ]


def test_stale_fx_alone_is_warning_and_db_failure_is_error() -> None:
    w = s.run_warnings([_OK], _STALE)
    assert s.run_status("ok", w) == "warning"
    assert s.run_status("error:OperationalError", w) == "error"
    assert s.run_status("skipped:OperationalError", []) == "error"


def test_run_note_is_capped_at_400_chars() -> None:
    note = s.run_note([f"Nguồn {i}: " + "x" * 60 for i in range(20)])
    assert note is not None and len(note) == s.MAX_NOTE_CHARS and note.endswith("…")


def test_scan_response_backward_compatible() -> None:
    """Payload cũ (không có status/warnings/stale_fx) vẫn hợp lệ; payload mới giữ đủ trường."""
    old = ScanResponse(records=[], sources=[], persisted=0, run_id=None, db="ok")
    assert old.status == "ok" and old.warnings == [] and old.stale_fx == []
    new = ScanResponse(records=[], sources=[_OK], persisted=0, run_id=1, db="ok",
                       status="warning", warnings=["x"], stale_fx=_STALE)
    dumped = new.model_dump(mode="json")
    assert dumped["stale_fx"][0] == {"pair": "USD/JPY", "latest": "2026-09-02", "lag": 7}


# ── Qua DB: lượt quét giả (nguồn 'test', grade __…__) — dọn sạch sau test ──

@pytest.fixture()
def fake_scan(monkeypatch):
    if not db_healthy():
        pytest.skip("DB không sẵn sàng")
    as_of = (date.today() - timedelta(days=2)).isoformat()
    data = [
        {"source": "test", "status": "ok", "note": "x-rates thiếu: JPY,CNY,THB",
         "records": [{"source": "test", "grade": "__SCAN_STATUS__", "price": 1.0, "currency": "USD",
                      "unit": "USD/t", "price_type": "settlement", "as_of": as_of}]},
    ]
    monkeypatch.setattr(scan_service, "run_crawler", lambda _src: data)
    monkeypatch.setattr(fx_freshness, "stale_pairs", lambda: list(_STALE))
    yield
    with session_scope() as db:
        db.execute(text("DELETE FROM fact_price WHERE grade = '__SCAN_STATUS__'"))
        db.execute(text("DELETE FROM meta_crawl_run WHERE sources = 'test'"))


def test_scan_and_persist_records_warning_in_meta_crawl_run(fake_scan) -> None:
    result = scan_service.scan_and_persist("test")
    assert result["db"] == "ok" and result["status"] == "warning"
    assert result["stale_fx"] == _STALE and len(result["warnings"]) == 2
    ScanResponse(**result)  # router trả được đúng schema
    with session_scope() as db:
        row = db.execute(text("SELECT status, rows, error FROM meta_crawl_run WHERE id = :i"),
                         {"i": result["run_id"]}).one()
    assert row.status == "warning" and row.rows == 1
    assert "x-rates thiếu" in row.error and "USD/JPY 02/09 (trễ 7 phiên)" in row.error
