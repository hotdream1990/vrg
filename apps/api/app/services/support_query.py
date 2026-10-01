"""Truy vấn danh sách cho hộp thư Hỗ trợ & Thông báo — phân trang Ở SERVER.

Tách khỏi `support_repo` (ghi) để mỗi file gọn: ở đây chỉ có đọc — danh sách luồng, đếm chưa đọc,
và gom các luồng cùng một lần gửi thành một dòng "đợt gửi" cho phía Tập đoàn (gửi 30 đơn vị mà
liệt kê 30 dòng giống hệt nhau thì không ai đọc nổi).

Mọi hàm nhận `companies`: `None` = Tập đoàn (mọi đơn vị), danh sách = phạm vi của tài khoản đơn vị
— kèm `audiences` (nhóm người nhận của người xem) và `username` (chưa đọc tính theo TỪNG NGƯỜI).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services.support_repo import HQ, _row, _scope_sql

MAX_PAGE_SIZE = 100

#: Luồng CHƯA ĐỌC với một bên: bên kia là người nhắn cuối và mình chưa đọc tới mốc đó.
#: Tập đoàn = hộp thư chung của Ban (một mốc `hq_read_at`); đơn vị = mốc của CHÍNH người xem.
_UNREAD_HQ = "(t.last_side <> 'hq' AND (t.hq_read_at IS NULL OR t.hq_read_at < t.last_at))"
_UNREAD_UNIT = ("(t.last_side <> 'unit' AND NOT EXISTS (SELECT 1 FROM support_read r "
                "WHERE r.thread_id = t.id AND r.username = :me AND r.read_at >= t.last_at))")


def _unread_expr(side: str, params: dict[str, Any], username: str | None) -> str:
    if side == HQ:
        return _UNREAD_HQ
    params["me"] = username or ""
    return _UNREAD_UNIT


def _filters(params: dict[str, Any], companies: list[str] | None, kinds: list[str] | None,
             status: str | None, q: str | None, company: str | None,
             audiences: list[str] | None = None) -> str:
    """Mệnh đề WHERE dùng chung cho danh sách luồng và đợt gửi."""
    sql = _scope_sql(companies, params, audiences=audiences)
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
                 page: int = 1, page_size: int = 20, audiences: list[str] | None = None,
                 username: str | None = None) -> dict[str, Any]:
    """Danh sách luồng (mới nhất trước) + tổng số, phân trang ở server."""
    ensure_schema()
    size = max(1, min(page_size, MAX_PAGE_SIZE))
    params: dict[str, Any] = {}
    where = _filters(params, companies, kinds, status, q, company, audiences)
    unread = _unread_expr(side, params, username)
    if batch_id:
        params["batch"] = batch_id
        where += " AND t.batch_id = :batch"
    if unread_only:
        where += f" AND {unread}"
    with session_scope() as db:
        total = db.execute(
            text(f"SELECT count(*) FROM support_thread t WHERE true{where}"), params,
        ).scalar() or 0
        params.update({"limit": size, "offset": (max(1, page) - 1) * size})
        rows = db.execute(
            text(f"""
                SELECT t.id, t.company, t.kind, t.subject, t.status, t.batch_id, t.created_by,
                       t.created_at, t.last_at, t.last_side, t.audience,
                       {unread} AS unread,
                       (SELECT count(*) FROM support_message m WHERE m.thread_id = t.id) AS message_count,
                       (SELECT m.body FROM support_message m WHERE m.thread_id = t.id
                         ORDER BY m.id DESC LIMIT 1) AS last_body
                  FROM support_thread t
                 WHERE true{where}
                 ORDER BY t.last_at DESC, t.id DESC
                 LIMIT :limit OFFSET :offset"""),
            params,
        ).mappings().all()
    return {"rows": [_row(r) for r in rows], "total": int(total), "page": max(1, page),
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
                       (array_agg(t.audience ORDER BY t.id))[1] AS audience,
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
    return {"rows": [_row(r) for r in rows], "total": int(total), "page": max(1, page),
            "page_size": size}


def count_unread(companies: list[str] | None, side: str, audiences: list[str] | None = None,
                 username: str | None = None) -> int:
    """Số luồng chưa đọc của người xem — dùng cho huy hiệu trên menu."""
    ensure_schema()
    params: dict[str, Any] = {}
    where = _scope_sql(companies, params, audiences=audiences)
    with session_scope() as db:
        return int(db.execute(
            text(f"SELECT count(*) FROM support_thread t "
                 f"WHERE {_unread_expr(side, params, username)}{where}"),
            params,
        ).scalar() or 0)


def file_visible(name: str, companies: list[str] | None, audiences: list[str] | None) -> bool:
    """File `name` có nằm trong một luồng mà tài khoản được xem không.

    File nằm chung MỘT thư mục phẳng nên router phải hỏi câu này trước khi trả file: thiếu bước
    này, lãnh đạo đơn vị A biết tên file là tải được đính kèm trong luồng của đơn vị B — và chuyên
    viên tải được đính kèm của thẻ không gửi cho nhóm mình.
    """
    params: dict[str, Any] = {"f": json.dumps([{"file": name}])}
    with session_scope() as db:
        return bool(db.execute(
            text("SELECT 1 FROM support_message m JOIN support_thread t ON t.id = m.thread_id "
                 f"WHERE m.files @> CAST(:f AS jsonb)"
                 f"{_scope_sql(companies, params, audiences=audiences)} LIMIT 1"),
            params,
        ).first())
