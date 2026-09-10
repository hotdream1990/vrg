"""Nhật ký hỏi–đáp Trợ lý AI (assistant_chat_log) — xem lại + cơ chế xoá cho DB không phình.

Bảng tạo NGAY TRONG MODULE NÀY (không phải `app/core/db.py` — file đó đang có người khác sửa
song song trong cùng đợt việc) bằng `CREATE TABLE IF NOT EXISTS` độc lập, idempotent.

⚠ KHÔNG lưu `artifacts` (bảng/biểu đồ Trợ lý trả cho người dùng) — luôn tính lại được từ đúng
tool đã gọi (số liệu gốc không đổi), lưu thêm chỉ làm log phình to vô ích (YAGNI).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from app.core.db import get_engine, session_scope

logger = logging.getLogger("vrg.assistant_history")

_ready = False

_DDL = """
CREATE TABLE IF NOT EXISTS assistant_chat_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  text NOT NULL,
    username    text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    question    text NOT NULL DEFAULT '',
    answer      text NOT NULL DEFAULT '',
    tools       jsonb NOT NULL DEFAULT '[]'::jsonb,
    sources     jsonb NOT NULL DEFAULT '[]'::jsonb,
    packs       jsonb NOT NULL DEFAULT '[]'::jsonb,
    advice      text NOT NULL DEFAULT '',
    model       text NOT NULL DEFAULT '',
    latency_ms  integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_assistant_chat_log_user
    ON assistant_chat_log (username, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_assistant_chat_log_session
    ON assistant_chat_log (session_id);
"""


def _ensure_schema() -> None:
    """Tạo bảng lần đầu dùng (idempotent, cache trong process)."""
    global _ready
    if _ready:
        return
    with get_engine().begin() as conn:
        conn.execute(text(_DDL))
    _ready = True


def _json(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False, default=str)


def log_turn(session_id: str, username: str, question: str, answer: str,
             tools: list[str], sources: list[str], packs: list[str] | None,
             advice: str, model: str, latency_ms: int) -> None:
    """Ghi 1 lượt hỏi–đáp. Lỗi ghi log KHÔNG được làm hỏng câu trả lời — nuốt exception + log warning.

    `session_id` do client tự sinh nên KHÔNG tin được: ai đó gửi trùng mã phiên của người khác là
    câu hỏi của họ lọt vào hội thoại người kia (và nếu ghi trước thì còn chiếm luôn quyền xem cả
    phiên). Vì vậy phiên đã có chủ mà người ghi khác chủ ⇒ BỎ ghi, không chèn bậy.
    """
    try:
        _ensure_schema()
        owner = session_owner(session_id)
        if owner is not None and owner != username:
            logger.warning("[assistant-history] Bỏ ghi: phiên %s thuộc về %s, không phải %s",
                           session_id, owner, username)
            return
        with session_scope() as db:
            db.execute(text("""
                INSERT INTO assistant_chat_log
                    (session_id, username, question, answer, tools, sources, packs,
                     advice, model, latency_ms)
                VALUES
                    (:session_id, :username, :question, :answer,
                     CAST(:tools AS jsonb), CAST(:sources AS jsonb), CAST(:packs AS jsonb),
                     :advice, :model, :latency_ms)
            """), {
                "session_id": session_id, "username": username,
                "question": question or "", "answer": answer or "",
                "tools": _json(tools), "sources": _json(sources), "packs": _json(packs),
                "advice": advice or "", "model": model or "", "latency_ms": int(latency_ms or 0),
            })
    except Exception as exc:  # noqa: BLE001 - ghi log hỏng KHÔNG được chặn câu trả lời của người dùng
        logger.warning("[assistant-history] Không ghi được log (session=%s): %s", session_id, exc)


def _row_out(r: Any) -> dict[str, Any]:  # noqa: ANN401 - RowMapping
    return {
        "id": int(r["id"]), "session_id": r["session_id"], "username": r["username"],
        "created_at": str(r["created_at"]), "question": r["question"], "answer": r["answer"],
        "tools": r["tools"] or [], "sources": r["sources"] or [], "packs": r["packs"] or [],
        "advice": r["advice"] or "", "model": r["model"] or "",
        "latency_ms": int(r["latency_ms"] or 0),
    }


def list_sessions(username: str | None = None, date_from: str | None = None,
                   date_to: str | None = None, q: str | None = None,
                   limit: int = 20, offset: int = 0) -> dict[str, Any]:
    """Danh sách PHIÊN (gộp theo session_id), mới nhất trước → {items, total}.

    KISS: bộ lọc áp Ở MỨC DÒNG trước khi gộp — nếu `q` chỉ khớp 1 lượt trong phiên thì mốc
    thời gian/số lượt hiển thị chỉ tính trên lượt khớp đó, không phải toàn phiên. Đủ dùng cho
    tra cứu/dọn log, không cần chính xác tuyệt đối với trường hợp lọc `q` hiếm gặp này.
    """
    _ensure_schema()
    where, params = ["1 = 1"], {}
    if username:
        where.append("username = :username")
        params["username"] = username
    if date_from:
        where.append("created_at >= CAST(:df AS date)")
        params["df"] = date_from
    if date_to:  # tới HẾT ngày date_to
        where.append("created_at < CAST(:dt AS date) + interval '1 day'")
        params["dt"] = date_to
    if q:
        where.append("question ILIKE :q")
        params["q"] = f"%{q}%"
    clause = " AND ".join(where)
    with session_scope() as db:
        total = db.execute(text(
            f"SELECT count(DISTINCT session_id) FROM assistant_chat_log WHERE {clause}"
        ), params).scalar() or 0
        rows = db.execute(text(f"""
            WITH filtered AS (
                SELECT * FROM assistant_chat_log WHERE {clause}
            ), agg AS (
                SELECT session_id, min(username) AS username, min(created_at) AS first_at,
                       max(created_at) AS last_at, count(*) AS turns
                FROM filtered GROUP BY session_id
            ), first_q AS (
                SELECT DISTINCT ON (session_id) session_id, question
                FROM filtered ORDER BY session_id, created_at ASC
            )
            SELECT agg.session_id, agg.username, agg.first_at, agg.last_at, agg.turns,
                   first_q.question AS first_question
            FROM agg JOIN first_q USING (session_id)
            ORDER BY agg.last_at DESC
            LIMIT :lim OFFSET :off
        """), {**params, "lim": limit, "off": offset}).mappings().all()
    items = [{
        "session_id": r["session_id"], "username": r["username"],
        "first_at": str(r["first_at"]), "last_at": str(r["last_at"]),
        "turns": int(r["turns"]), "title": r["first_question"],  # câu hỏi đầu tiên = tiêu đề phiên
    } for r in rows]
    return {"items": items, "total": int(total)}


def session_owner(session_id: str) -> str | None:
    """Chủ phiên = người ghi lượt ĐẦU TIÊN. None nếu phiên chưa có dòng nào.

    Bắt buộc `ORDER BY created_at`: thiếu nó thì `LIMIT 1` trả về dòng nào là do query planner
    quyết, nên "chủ phiên" đảo qua lại giữa những người cùng ghi vào một `session_id` — hàng rào
    quyền ở router dựa trên hàm này sẽ hở.
    """
    _ensure_schema()
    with session_scope() as db:
        row = db.execute(text(
            "SELECT username FROM assistant_chat_log WHERE session_id = :sid "
            "ORDER BY created_at ASC, id ASC LIMIT 1"
        ), {"sid": session_id}).first()
    return str(row[0]) if row else None


def get_session(session_id: str) -> list[dict[str, Any]]:
    """Toàn bộ lượt của 1 phiên, CŨ→MỚI."""
    _ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("""
            SELECT id, session_id, username, created_at, question, answer,
                   tools, sources, packs, advice, model, latency_ms
            FROM assistant_chat_log WHERE session_id = :sid ORDER BY created_at ASC
        """), {"sid": session_id}).mappings().all()
    return [_row_out(r) for r in rows]


def delete_session(session_id: str) -> int:
    """Xoá 1 phiên — trả số dòng đã xoá."""
    _ensure_schema()
    with session_scope() as db:
        res = db.execute(text("DELETE FROM assistant_chat_log WHERE session_id = :sid"),
                         {"sid": session_id})
    return res.rowcount or 0


def delete_before(before: str) -> int:
    """Xoá log CŨ HƠN ngày `before` (YYYY-MM-DD) — cơ chế dọn cho DB không phình. Trả số dòng đã xoá."""
    _ensure_schema()
    with session_scope() as db:
        res = db.execute(text("DELETE FROM assistant_chat_log WHERE created_at < CAST(:d AS date)"),
                         {"d": before})
    return res.rowcount or 0


def stats() -> dict[str, Any]:
    """Tổng số lượt · số phiên · dòng cũ nhất — cho UI hiện 'đang lưu N lượt từ ngày …'."""
    _ensure_schema()
    with session_scope() as db:
        row = db.execute(text(
            "SELECT count(*) AS turns, count(DISTINCT session_id) AS sessions, "
            "min(created_at) AS oldest FROM assistant_chat_log"
        )).mappings().first()
    return {
        "turns": int(row["turns"] or 0),
        "sessions": int(row["sessions"] or 0),
        "oldest": str(row["oldest"]) if row and row["oldest"] else None,
    }
