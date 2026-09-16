"""Fixture dùng chung cho test.

Nhật ký hoạt động + Lịch sử truy cập ghi tự động mỗi khi test ghi số liệu/đăng nhập → dọn sạch
sau khi chạy để KHÔNG để rác trong DB dev (mọi dòng sinh ra trong phiên test đều là dữ liệu test).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, ensure_schema, session_scope


@pytest.fixture(autouse=True, scope="session")
def _clean_log_rows():
    if not db_healthy():
        yield
        return
    ensure_schema()  # bảng nhật ký phải có trước khi đọc mốc id (DB test thường trống)
    with session_scope() as db:
        start_id = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM audit_log")).scalar() or 0
        start_access = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM access_log")).scalar() or 0
    yield
    with session_scope() as db:
        db.execute(text("DELETE FROM audit_log WHERE id > :i"), {"i": start_id})
        db.execute(text("DELETE FROM access_log WHERE id > :i"), {"i": start_access})
