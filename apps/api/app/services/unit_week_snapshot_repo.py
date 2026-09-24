"""Kho bản lưu số liệu tuần (`unit_week_snapshot`) — CHỈ THÊM, không bao giờ sửa hay ghi đè.

Bản lưu là mốc cố định để đối chiếu về sau: chụp rồi thì số liệu gốc có đổi (đơn vị được duyệt đề
nghị sửa, admin sửa hộ…) bản lưu vẫn giữ nguyên. Vì vậy ghi bằng `ON CONFLICT DO NOTHING` — hai
lượt chụp chạy trùng (job + admin bấm "Chụp ngay") thì chỉ một lượt được ghi.

Số không hữu hạn (NaN/±inf — vd một ô kế hoạch bẩn làm % KH thành NaN) được quy về null trước khi
ghi: `json.dumps` in ra `NaN` mà jsonb không nhận, một ô bẩn sẽ làm job chụp lỗi MỌI ngày và mất
bản lưu cả tuần.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_SUMMARY_COLS = "week_start, week_end, totals, deadline_at, taken_at, taken_by"


def _row(m: Any) -> dict[str, Any]:
    """Chuẩn hoá 1 dòng DB → dict JSON được (ngày ISO; giờ ISO quy về giờ Việt Nam)."""
    d = dict(m)
    for k in ("week_start", "week_end"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    for k in ("deadline_at", "taken_at"):
        if d.get(k) is not None:
            d[k] = d[k].astimezone(_TZ).isoformat()
    return d


def _finite(v: Any) -> Any:
    """Duyệt sâu dict/list, thay float NaN/±inf bằng None (giữ nguyên mọi giá trị khác)."""
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {k: _finite(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_finite(x) for x in v]
    return v


def _json(v: Any) -> str:
    return json.dumps(_finite(v), default=str, allow_nan=False)


def get_summary(week_start: str) -> dict[str, Any] | None:
    """Phần tóm tắt của 1 tuần (không kéo 2 biểu từng đơn vị) — None nếu tuần chưa được chụp."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(f"SELECT {_SUMMARY_COLS} FROM unit_week_snapshot "
                              "WHERE week_start = CAST(:w AS date)"),
                         {"w": week_start}).mappings().first()
    return _row(row) if row else None


def insert(snap: dict[str, Any], deadline_at: datetime, taken_by: str) -> dict[str, Any] | None:
    """Ghi bản lưu MỚI; tuần đã có bản lưu thì KHÔNG đụng tới và trả None."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("INSERT INTO unit_week_snapshot "
                 "(week_start, week_end, purchase, consumption, totals, deadline_at, taken_by) "
                 "VALUES (CAST(:ws AS date), CAST(:we AS date), CAST(:p AS jsonb), "
                 "CAST(:c AS jsonb), CAST(:t AS jsonb), :dl, :by) "
                 f"ON CONFLICT (week_start) DO NOTHING RETURNING {_SUMMARY_COLS}"),
            {"ws": snap["week_start"], "we": snap["week_end"],
             "p": _json(snap["purchase"]), "c": _json(snap["consumption"]),
             "t": _json(snap["totals"]),
             "dl": deadline_at, "by": taken_by},
        ).mappings().first()
    return _row(row) if row else None


def get(week_start: str) -> dict[str, Any] | None:
    """Bản lưu đầy đủ của 1 tuần (kèm 2 biểu từng đơn vị)."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text(f"SELECT {_SUMMARY_COLS}, purchase, consumption FROM unit_week_snapshot "
                 "WHERE week_start = CAST(:w AS date)"),
            {"w": week_start},
        ).mappings().first()
    return _row(row) if row else None


def list_summaries() -> list[dict[str, Any]]:
    """Mọi tuần đã chụp, mới nhất trước — CHỈ phần tóm tắt (không kéo 2 biểu từng đơn vị)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(f"SELECT {_SUMMARY_COLS} FROM unit_week_snapshot "
                               "ORDER BY week_start DESC")).mappings().all()
    return [_row(r) for r in rows]
