"""Repository «Đề nghị sửa số liệu quá khứ» (bảng `edit_request`).

Chỉ lo lưu/đọc/đổi trạng thái. Luật của từng thao tác ở `edit_request_ops*`, luật duyệt ở
`edit_request_apply`. Mọi lần đổi trạng thái đều có điều kiện `status = 'pending'` trong câu UPDATE
nên hai người bấm cùng lúc không thể cùng thắng.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

STATUSES = ("pending", "approved", "rejected", "cancelled")

_SELECT = """
    SELECT e.id, e.company, e.op, e.target_key, e.title, e.dates, e.payload, e.before, e.reason,
           e.blocked, e.status, e.requested_by, e.requested_at, e.updated_at, e.reviewed_by,
           e.reviewed_at, e.review_note, e.unlocked,
           rq.full_name AS requested_by_name, rv.full_name AS reviewed_by_name
      FROM edit_request e
      LEFT JOIN app_user rq ON rq.username = e.requested_by
      LEFT JOIN app_user rv ON rv.username = e.reviewed_by
"""


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, default=str)


def _out(r) -> dict[str, Any]:  # noqa: ANN001 - RowMapping
    from app.services.edit_request_ops import op_label  # tránh import vòng

    d = dict(r)
    for k in ("requested_at", "updated_at", "reviewed_at"):
        d[k] = d[k].isoformat() if d.get(k) else None
    d["dates"] = list(d.get("dates") or [])
    d["blocked"] = list(d.get("blocked") or [])
    d["payload"] = d.get("payload") or {}
    d["op_label"] = op_label(d["op"], d["payload"])
    return d


def get(req_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(_SELECT + " WHERE e.id = :id"), {"id": req_id}).mappings().first()
    return _out(r) if r else None


def save_pending(row: dict[str, Any], username: str) -> tuple[dict[str, Any], bool]:
    """Tạo đề nghị, hoặc GHI ĐÈ đề nghị đang chờ của cùng (đơn vị, bản ghi). Trả (đề nghị, đã ghi đè?)."""
    ensure_schema()
    with session_scope() as db:
        got = db.execute(text("""
            INSERT INTO edit_request (company, op, target_key, title, dates, payload, before,
                                      reason, blocked, requested_by)
            VALUES (:c, :op, :k, :t, CAST(:dates AS jsonb), CAST(:p AS jsonb), CAST(:b AS jsonb),
                    :r, CAST(:bl AS jsonb), :u)
            ON CONFLICT (company, target_key) WHERE status = 'pending' DO UPDATE SET
                op = EXCLUDED.op, title = EXCLUDED.title, dates = EXCLUDED.dates,
                payload = EXCLUDED.payload, before = EXCLUDED.before, reason = EXCLUDED.reason,
                blocked = EXCLUDED.blocked, requested_by = EXCLUDED.requested_by, updated_at = now()
            RETURNING id, (xmax::text <> '0') AS replaced
        """), {"c": row["company"], "op": row["op"], "k": row["target_key"], "t": row["title"],
               "dates": _json(row["dates"]), "p": _json(row["payload"]), "b": _json(row["before"]),
               "r": row["reason"], "bl": _json(row["blocked"]), "u": username}).mappings().first()
    return get(int(got["id"])) or {}, bool(got["replaced"])


def list_requests(*, status: str | None = None, companies: list[str] | None = None,
                  company: str | None = None, op: str | None = None, q: str | None = None,
                  page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Một trang đề nghị (mới gửi trước) + số đếm theo trạng thái trên CÙNG bộ lọc (trừ trạng thái)."""
    ensure_schema()
    where, params = ["1 = 1"], {}
    if companies is not None:
        where.append("e.company = ANY(:cs)")
        params["cs"] = list(companies)
    if company:
        where.append("e.company = :company")
        params["company"] = company
    if op:
        where.append("e.op = :op")
        params["op"] = op
    if q:
        where.append("(e.company ILIKE :q OR e.title ILIKE :q OR e.reason ILIKE :q)")
        params["q"] = f"%{q}%"
    base = " AND ".join(where)
    with session_scope() as db:
        counts = {s: 0 for s in STATUSES}
        for r in db.execute(text(f"SELECT e.status, count(*) AS n FROM edit_request e WHERE {base} "
                                 "GROUP BY e.status"), params).mappings():
            counts[r["status"]] = int(r["n"])
        clause = base
        if status:
            clause += " AND e.status = :status"
            params["status"] = status
        rows = db.execute(text(_SELECT + f" WHERE {clause} ORDER BY e.requested_at DESC, e.id DESC "
                                         "LIMIT :lim OFFSET :off"),
                          {**params, "lim": page_size, "off": (page - 1) * page_size}).mappings().all()
    total = counts.get(status, 0) if status else sum(counts.values())
    return {"items": [_out(r) for r in rows], "total": total, "page": page,
            "page_size": page_size, "counts": counts}


def pending_count() -> int:
    ensure_schema()
    with session_scope() as db:
        return int(db.execute(text("SELECT count(*) FROM edit_request WHERE status = 'pending'"))
                   .scalar() or 0)


def lock_for_review(db, req_id: int) -> dict[str, Any] | None:  # noqa: ANN001 - session của người gọi
    """Khoá dòng (`FOR UPDATE`) tới hết transaction của `db` — người duyệt thứ hai phải chờ."""
    r = db.execute(text("SELECT id, company, op, payload, before, dates, status, requested_by, "
                        "       updated_at FROM edit_request WHERE id = :id FOR UPDATE"),
                   {"id": req_id}).mappings().first()
    return dict(r) if r else None


def mark_reviewed(db, req_id: int, status: str, reviewer: str, note: str | None,  # noqa: ANN001
                  unlocked: list[dict] | None = None, dates: list[str] | None = None) -> bool:
    """Đổi đề nghị ĐANG CHỜ sang approved/rejected. False = không còn chờ duyệt.

    `dates` (khi duyệt) = ngày THỰC SỰ bị ảnh hưởng lúc ghi — email/màn hình báo gỡ chốt từ đúng ngày đó.
    """
    return db.execute(text(
        "UPDATE edit_request SET status = :s, reviewed_by = :u, reviewed_at = now(), "
        "       review_note = :n, unlocked = CAST(:ul AS jsonb), updated_at = now(), "
        "       dates = COALESCE(CAST(:d AS jsonb), dates) "
        " WHERE id = :id AND status = 'pending'"),
        {"s": status, "u": reviewer, "n": note, "ul": _json(unlocked), "d": _json(dates),
         "id": req_id}).rowcount > 0


def cancel(req_id: int) -> bool:
    """Đơn vị tự huỷ đề nghị đang chờ. False = không còn chờ duyệt."""
    ensure_schema()
    with session_scope() as db:
        return db.execute(text("UPDATE edit_request SET status = 'cancelled', updated_at = now() "
                               " WHERE id = :id AND status = 'pending'"), {"id": req_id}).rowcount > 0
