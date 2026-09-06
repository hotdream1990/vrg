"""Repository hộp thư Hỗ trợ & Thông báo — luồng (`support_thread`) + tin (`support_message`).

⚠ LUẬT CÁCH LY (quan trọng nhất của module này): mỗi luồng thuộc về ĐÚNG MỘT đơn vị. Tập đoàn gửi
cho nhiều đơn vị = `open_threads()` tạo NHIỀU luồng cùng `batch_id`. Mọi truy vấn phía đơn vị đều
BẮT BUỘC truyền `companies` (danh sách đơn vị của tài khoản) và bị lọc ở SQL — không có đường nào
để đơn vị A đọc được tin hay phản hồi của đơn vị B.

Phía Tập đoàn truyền `companies=None` = xem tất cả.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

HQ, UNIT = "hq", "unit"
KIND_REQUEST, KIND_ANNOUNCE, KIND_REMINDER = "request", "announce", "reminder"
KINDS = (KIND_REQUEST, KIND_ANNOUNCE, KIND_REMINDER)

_THREAD_COLS = ("id, company, kind, subject, status, batch_id, reminder_id, created_by, "
                "created_at, last_at, last_side, hq_read_at, unit_read_at")


def _scope_sql(companies: list[str] | None, params: dict[str, Any], alias: str = "t") -> str:
    """Mệnh đề lọc theo đơn vị. `None` = Tập đoàn (mọi đơn vị); danh sách rỗng = KHÔNG thấy gì."""
    if companies is None:
        return ""
    if not companies:
        return " AND false"
    params["scope"] = list(companies)
    return f" AND {alias}.company = ANY(:scope)"


def _row(row: Any) -> dict[str, Any]:
    d = dict(row)
    if "files" in d:
        d["files"] = list(d["files"] or [])
    return d


def open_threads(companies: list[str], kind: str, subject: str, body: str,
                 files: list[dict] | None, author: str, author_name: str | None,
                 side: str, reminder_id: int | None = None) -> list[int]:
    """Mở luồng mới cho TỪNG đơn vị (kèm tin đầu tiên) → trả danh sách id luồng đã tạo.

    Gửi cho N đơn vị = N luồng độc lập cùng `batch_id` — đây là chỗ bảo đảm cách ly, đừng gộp lại
    thành một luồng nhiều người nhận để "đỡ tốn dòng".
    """
    ensure_schema()
    targets = [c for c in dict.fromkeys(companies) if (c or "").strip()]
    if not targets:
        return []
    batch = uuid.uuid4().hex if len(targets) > 1 or kind != KIND_REQUEST else None
    payload = json.dumps(files or [])
    ids: list[int] = []
    with session_scope() as db:
        for company in targets:
            tid = db.execute(
                text("INSERT INTO support_thread "
                     "(company, kind, subject, batch_id, reminder_id, created_by, last_side) "
                     "VALUES (:c, :k, :s, :b, :r, :by, :side) RETURNING id"),
                {"c": company, "k": kind, "s": subject, "b": batch, "r": reminder_id,
                 "by": author, "side": side},
            ).scalar()
            db.execute(
                text("INSERT INTO support_message (thread_id, side, author, author_name, body, files) "
                     "VALUES (:t, :side, :a, :an, :b, CAST(:f AS jsonb))"),
                {"t": tid, "side": side, "a": author, "an": author_name, "b": body, "f": payload},
            )
            ids.append(int(tid))
    return ids


def get_thread(thread_id: int, companies: list[str] | None) -> dict[str, Any] | None:
    """1 luồng trong phạm vi tài khoản (None nếu không có / ngoài phạm vi)."""
    ensure_schema()
    params: dict[str, Any] = {"id": thread_id}
    with session_scope() as db:
        row = db.execute(
            text(f"SELECT {_THREAD_COLS} FROM support_thread t "
                 f"WHERE id = :id{_scope_sql(companies, params)}"),
            params,
        ).mappings().first()
        return _row(row) if row else None


def messages(thread_id: int) -> list[dict[str, Any]]:
    """Các tin trong luồng theo thứ tự thời gian. Gọi SAU khi đã kiểm phạm vi bằng `get_thread`."""
    with session_scope() as db:
        rows = db.execute(
            text("SELECT id, thread_id, side, author, author_name, body, files, created_at "
                 "FROM support_message WHERE thread_id = :t ORDER BY id"),
            {"t": thread_id},
        ).mappings().all()
        return [_row(r) for r in rows]


def add_message(thread_id: int, side: str, author: str, author_name: str | None,
                body: str, files: list[dict] | None) -> dict[str, Any]:
    """Thêm phản hồi vào luồng + cập nhật mốc tin cuối (để hộp thư sắp xếp và báo chưa đọc)."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("INSERT INTO support_message (thread_id, side, author, author_name, body, files) "
                 "VALUES (:t, :side, :a, :an, :b, CAST(:f AS jsonb)) "
                 "RETURNING id, thread_id, side, author, author_name, body, files, created_at"),
            {"t": thread_id, "side": side, "a": author, "an": author_name, "b": body,
             "f": json.dumps(files or [])},
        ).mappings().first()
        # Bên vừa gửi coi như đã đọc tới đây; bên kia để nguyên → hiện "chưa đọc".
        # ⚠ KHÔNG đụng tới `status`: mỗi thẻ là MỘT trường hợp, khép rồi là khép hẳn — việc mới
        # thì mở thẻ mới (chốt 29/08/2026). Trước đây phản hồi tự mở lại thẻ đã đóng, thành ra
        # một thẻ gánh nhiều việc và không còn biết trường hợp nào đã xong.
        read_col = "hq_read_at" if side == HQ else "unit_read_at"
        db.execute(
            text(f"UPDATE support_thread SET last_at = now(), last_side = :side, "
                 f"{read_col} = now() WHERE id = :t"),
            {"t": thread_id, "side": side},
        )
    return _row(row)


def mark_read(thread_id: int, side: str, companies: list[str] | None) -> None:
    """Đánh dấu đã đọc cho MỘT bên (chỉ khi luồng nằm trong phạm vi tài khoản)."""
    params: dict[str, Any] = {"id": thread_id}
    col = "hq_read_at" if side == HQ else "unit_read_at"
    with session_scope() as db:
        db.execute(
            text(f"UPDATE support_thread t SET {col} = now() "
                 f"WHERE id = :id{_scope_sql(companies, params)}"),
            params,
        )


def set_status(thread_id: int, status: str, companies: list[str] | None) -> bool:
    """Đóng / mở lại luồng. False nếu luồng ngoài phạm vi tài khoản."""
    params: dict[str, Any] = {"id": thread_id, "st": status}
    with session_scope() as db:
        res = db.execute(
            text(f"UPDATE support_thread t SET status = :st "
                 f"WHERE id = :id{_scope_sql(companies, params)}"),
            params,
        )
        return res.rowcount > 0


def delete_thread(thread_id: int) -> bool:
    """Xoá hẳn 1 luồng (chỉ quản trị) — xoá kèm toàn bộ tin trong luồng."""
    with session_scope() as db:
        db.execute(text("DELETE FROM support_message WHERE thread_id = :t"), {"t": thread_id})
        res = db.execute(text("DELETE FROM support_thread WHERE id = :t"), {"t": thread_id})
        return res.rowcount > 0


def companies_of_file(name: str) -> set[str]:
    """Các đơn vị có luồng đính kèm file `name`.

    File nằm chung MỘT thư mục phẳng nên router phải hỏi câu này trước khi trả file: thiếu bước
    này, lãnh đạo đơn vị A biết tên file là tải được đính kèm trong luồng của đơn vị B.
    """
    with session_scope() as db:
        rows = db.execute(
            text("SELECT DISTINCT t.company FROM support_message m "
                 "JOIN support_thread t ON t.id = m.thread_id "
                 "WHERE m.files @> CAST(:f AS jsonb)"),
            {"f": json.dumps([{"file": name}])},
        ).all()
        return {str(r[0]) for r in rows}


def companies_of_reminder_file(name: str) -> bool:
    """File có thuộc một lịch nhắc CHƯA phát không — để Tập đoàn xem lại đính kèm đã soạn."""
    with session_scope() as db:
        return bool(db.execute(
            text("SELECT 1 FROM support_reminder WHERE files @> CAST(:f AS jsonb) LIMIT 1"),
            {"f": json.dumps([{"file": name}])},
        ).first())
