"""Fixture dùng chung cho test.

Nhật ký hoạt động ghi tự động mỗi khi test ghi/xoá số liệu → dọn sạch sau khi chạy để
KHÔNG để rác trong DB dev (mọi dòng sinh ra trong phiên test đều là dữ liệu test).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope


@pytest.fixture(autouse=True, scope="session")
def _clean_audit_rows():
    if not db_healthy():
        yield
        return
    with session_scope() as db:
        start_id = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM audit_log")).scalar() or 0
    yield
    with session_scope() as db:
        db.execute(text("DELETE FROM audit_log WHERE id > :i"), {"i": start_id})
