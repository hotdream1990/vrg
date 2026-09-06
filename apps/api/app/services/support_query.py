"""Truy vấn danh sách cho hộp thư Hỗ trợ & Thông báo — phân trang Ở SERVER.

Tách khỏi `support_repo` (ghi) để mỗi file gọn: ở đây chỉ có đọc — danh sách luồng, đếm chưa đọc,
và gom các luồng cùng một lần gửi thành một dòng "đợt gửi" cho phía Tập đoàn (gửi 30 đơn vị mà
liệt kê 30 dòng giống hệt nhau thì không ai đọc nổi).

Mọi hàm nhận `companies`: `None` = Tập đoàn (mọi đơn vị), danh sách = phạm vi của tài khoản đơn vị.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services.support_repo import HQ, _scope_sql

MAX_PAGE_SIZE = 100

#: Luồng CHƯA ĐỌC với một bên: bên kia là người nhắn cuối và mình chưa đọc tới mốc đó.
_UNREAD_HQ = "(t.last_side <> 'hq' AND (t.hq_read_at IS NULL OR t.hq_read_at < t.last_at))"
_UNREAD_UNIT = "(t.last_side <> 'unit' AND (t.unit_read_at IS NULL OR t.unit_read_at < t.last_at))"


def _unread_expr(side: str) -> str:
    return _UNREAD_HQ if side == HQ else _UNREAD_UNIT


def _filters(params: dict[str, Any], companies: list[str] | None, kinds: list[str] | None,
             status: str | None, q: str | None, company: str | None) -> str:
    """Mệnh đề WHERE dùng chung cho danh sách luồng và đợt gửi."""
    sql = _scope_sql(companies, params)
    if kinds:
        params["kinds"] = list(kinds)
        sql += " AND t.kind = ANY(:kinds)"
    if status in ("open", "closed"):
        params["status"] = status
        sql += " AND t.status = :status"
    if company:
        params["one_company"] = company
        sql += " AND t.company = :one_company"
    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        sql += " AND (lower(t.subject) LIKE :q OR lower(t.company) LIKE :q)"
    return sql


def list_threads(companies: list[str] | None, side: str, *, kinds: list[str] | None = None,
                 status: str | None = None, q: str | None = None, company: str | None = None,
                 batch_id: str | None = None, unread_only: bool = False,
                 page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Danh sách luồng (mới nhất trước) + tổng số, phân trang ở server."""
    ensure_schema()
    size = max(1, min(page_size, MAX_PAGE_SIZE))
    params: dict[str, Any] = {}
    where = _filters(params, companies, kinds, status, q, company)
    if batch_id:
        params["batch"] = batch_id
        where += " AND t.batch_id = :batch"
    if unread_only:
        where += f" AND {_unread_expr(side)}"
    with session_scope() as db:
        total = db.execute(
            text(f"SELECT count(*) FROM support_thread t WHERE true{where}"), params,
        ).scalar() or 0
        params.update({"limit": size, "offset": (max(1, page) - 1) * size})
        rows = db.execute(
            text(f"""
                SELECT t.id, t.company, t.kind, t.subject, t.status, t.batch_id, t.created_by,
                       t.created_at, t.last_at, t.last_side,
                       {_unread_expr(side)} AS unread,
                       (SELECT count(*) FROM support_message m WHERE m.thread_id = t.id) AS message_count,
                       (SELECT m.body FROM support_message m WHERE m.thread_id = t.id
                         ORDER BY m.id DESC LIMIT 1) AS last_body
                  FROM support_thread t
                 WHERE true{where}
                 ORDER BY t.last_at DESC, t.id DESC
                 LIMIT :limit OFFSET :offset"""),
            params,
        ).mappings().all()
    return {"rows": [dict(r) for r in rows], "total": int(total), "page": max(1, page),
            "page_size": size}


def list_batches(*, kinds: list[str] | None = None, status: str | None = None,
                 q: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Các ĐỢT GỬI của Tập đoàn, gom theo `batch_id` — 1 dòng/lần gửi kèm số đơn vị nhận.

    Luồng không có `batch_id` (dữ liệu cũ) tự đứng riêng một dòng nhờ `COALESCE(batch_id, id)`.
    """
    ensure_schema()
    size = max(1, min(page_size, MAX_PAGE_SIZE))
    params: dict[str, Any] = {}
    where = _filters(params, None, kinds, status, q, None)
    group = "COALESCE(t.batch_id, t.id::text)"
    with session_scope() as db:
        total = db.execute(
            text(f"SELECT count(DISTINCT {group}) FROM support_thread t WHERE true{where}"), params,
        ).scalar() or 0
        params.update({"limit": size, "offset": (max(1, page) - 1) * size})
        rows = db.execute(
            text(f"""
                SELECT {group} AS group_key,
                       min(t.batch_id) AS batch_id,
                       min(t.id) AS sample_id,
                       min(t.subject) AS subject,
                       min(t.kind) AS kind,
                       min(t.created_by) AS created_by,
                       min(t.created_at) AS created_at,
                       max(t.last_at) AS last_at,
                       count(*) AS unit_count,
                       count(*) FILTER (WHERE {_UNREAD_HQ}) AS unread_count,
                       count(*) FILTER (WHERE t.status = 'open') AS open_count
                  FROM support_thread t
                 WHERE true{where}
                 GROUP BY {group}
                 ORDER BY max(t.last_at) DESC
                 LIMIT :limit OFFSET :offset"""),
            params,
        ).mappings().all()
    return {"rows": [dict(r) for r in rows], "total": int(total), "page": max(1, page),
            "page_size": size}


def count_unread(companies: list[str] | None, side: str) -> int:
    """Số luồng chưa đọc của một bên — dùng cho huy hiệu trên menu."""
    ensure_schema()
    params: dict[str, Any] = {}
    where = _scope_sql(companies, params)
    with session_scope() as db:
        return int(db.execute(
            text(f"SELECT count(*) FROM support_thread t "
                 f"WHERE {_unread_expr(side)}{where}"),
            params,
        ).scalar() or 0)
