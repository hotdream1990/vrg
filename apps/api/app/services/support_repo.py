"""Repository hộp thư Hỗ trợ & Thông báo — luồng (`support_thread`) + tin (`support_message`).

⚠ LUẬT CÁCH LY (quan trọng nhất của module này): mỗi luồng thuộc về ĐÚNG MỘT đơn vị. Tập đoàn gửi
cho nhiều đơn vị = `open_threads()` tạo NHIỀU luồng cùng `batch_id`. Mọi truy vấn phía đơn vị đều
BẮT BUỘC truyền `companies` (danh sách đơn vị của tài khoản) và bị lọc ở SQL — không có đường nào
để đơn vị A đọc được tin hay phản hồi của đơn vị B.

Phía Tập đoàn truyền `companies=None` = xem tất cả.

NGƯỜI NHẬN trong đơn vị (chốt 01/10/2026): mỗi luồng có `audience` = lãnh đạo (`leader`) và/hoặc
chuyên viên theo loại nhập liệu (`purchase` · `stock` · `contract`). Phía đơn vị lọc thêm theo nhóm
của người xem (`audiences`) — lãnh đạo KHÔNG thấy thẻ không gửi cho lãnh đạo (phân luồng chặt).
"Đã đọc" phía đơn vị tính theo TỪNG NGƯỜI (`support_read`); phía Tập đoàn vẫn là hộp thư chung
(`hq_read_at`).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.entry_types import DEFAULT_AUDIENCE, clean_audience

HQ, UNIT = "hq", "unit"
KIND_REQUEST, KIND_ANNOUNCE, KIND_REMINDER = "request", "announce", "reminder"
#: Cảnh báo số liệu hệ thống tự gửi sau giờ chốt nhập liệu (`anomaly_notify`) — nội dung riêng
#: từng đơn vị, mọi luồng của cùng một ngày chung `batch_id` = `alert-YYYY-MM-DD`.
KIND_ALERT = "alert"
KINDS = (KIND_REQUEST, KIND_ANNOUNCE, KIND_REMINDER, KIND_ALERT)

_THREAD_COLS = ("id, company, kind, subject, status, batch_id, reminder_id, created_by, "
                "created_at, last_at, last_side, hq_read_at, unit_read_at, audience")


def _scope_sql(companies: list[str] | None, params: dict[str, Any], alias: str = "t",
               audiences: list[str] | None = None) -> str:
    """Mệnh đề lọc phía đơn vị: đúng đơn vị được gán VÀ thẻ có gửi cho nhóm của người xem.

    `companies=None` = Tập đoàn (mọi đơn vị, mọi nhóm). Phía đơn vị mà thiếu đơn vị hoặc thiếu
    nhóm người nhận = KHÔNG thấy gì (quên truyền `audiences` thì chặn hết chứ không lộ).
    """
    if companies is None:
        return ""
    if not companies or not audiences:
        return " AND false"
    params["scope"] = list(companies)
    params["aud"] = list(audiences)
    return (f" AND {alias}.company = ANY(:scope)"
            f" AND EXISTS (SELECT 1 FROM jsonb_array_elements_text({alias}.audience) AS a(v)"
            f" WHERE a.v = ANY(:aud))")


def audience_of(raw: Any) -> list[str]:
    """Nhóm người nhận đã chuẩn hoá (thứ tự chuẩn); rỗng/thiếu = chỉ lãnh đạo như dữ liệu cũ."""
    return clean_audience(raw) or list(DEFAULT_AUDIENCE)


def _row(row: Any) -> dict[str, Any]:
    d = dict(row)
    if "files" in d:
        d["files"] = list(d["files"] or [])
    if "audience" in d:
        d["audience"] = audience_of(d["audience"])
    return d


def _touch_read(db: Any, thread_id: int, username: str) -> None:
    """Ghi mốc "đã đọc tới bây giờ" của MỘT người phía đơn vị."""
    db.execute(
        text("INSERT INTO support_read (thread_id, username, read_at) VALUES (:t, :u, now()) "
             "ON CONFLICT (thread_id, username) DO UPDATE SET read_at = EXCLUDED.read_at"),
        {"t": thread_id, "u": username},
    )


def open_threads(companies: list[str], kind: str, subject: str, body: str,
                 files: list[dict] | None, author: str, author_name: str | None,
                 side: str, reminder_id: int | None = None,
                 audience: list[str] | None = None) -> list[int]:
    """Mở luồng mới cho TỪNG đơn vị (kèm tin đầu tiên) → trả danh sách id luồng đã tạo.

    Gửi cho N đơn vị = N luồng độc lập cùng `batch_id` — đây là chỗ bảo đảm cách ly, đừng gộp lại
    thành một luồng nhiều người nhận để "đỡ tốn dòng". Mọi luồng của một lần gửi chung `audience`.
    """
    ensure_schema()
    targets = [c for c in dict.fromkeys(companies) if (c or "").strip()]
    if not targets:
        return []
    batch = uuid.uuid4().hex if len(targets) > 1 or kind != KIND_REQUEST else None
    with session_scope() as db:
        return [insert_thread(db, company, kind, subject, body, files, author, author_name, side,
                              batch, reminder_id, audience) for company in targets]


def insert_thread(db: Any, company: str, kind: str, subject: str, body: str,
                  files: list[dict] | None, author: str, author_name: str | None, side: str,
                  batch_id: str | None, reminder_id: int | None = None,
                  audience: list[str] | None = None) -> int:
    """Ghi MỘT luồng của MỘT đơn vị + tin đầu tiên, trong session của người gọi → id luồng.

    Tách riêng để nơi gửi nội dung KHÁC NHAU cho từng đơn vị (cảnh báo tự động) vẫn đi đúng một
    đường ghi, trong cùng giao dịch với bước chống gửi trùng của nó.
    """
    tid = db.execute(
        text("INSERT INTO support_thread "
             "(company, kind, subject, batch_id, reminder_id, created_by, last_side, audience) "
             "VALUES (:c, :k, :s, :b, :r, :by, :side, CAST(:aud AS jsonb)) RETURNING id"),
        {"c": company, "k": kind, "s": subject, "b": batch_id, "r": reminder_id,
         "by": author, "side": side, "aud": json.dumps(audience_of(audience))},
    ).scalar()
    db.execute(
        text("INSERT INTO support_message (thread_id, side, author, author_name, body, files) "
             "VALUES (:t, :side, :a, :an, :b, CAST(:f AS jsonb))"),
        {"t": tid, "side": side, "a": author, "an": author_name, "b": body,
         "f": json.dumps(files or [])},
    )
    if side == UNIT:
        _touch_read(db, int(tid), author)
    return int(tid)


def get_thread(thread_id: int, companies: list[str] | None,
               audiences: list[str] | None = None) -> dict[str, Any] | None:
    """1 luồng trong phạm vi tài khoản (None nếu không có / ngoài phạm vi đơn vị hoặc nhóm nhận)."""
    ensure_schema()
    params: dict[str, Any] = {"id": thread_id}
    with session_scope() as db:
        row = db.execute(
            text(f"SELECT {_THREAD_COLS} FROM support_thread t "
                 f"WHERE id = :id{_scope_sql(companies, params, audiences=audiences)}"),
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
        if side == UNIT:
            _touch_read(db, thread_id, author)
    return _row(row)


def mark_read(thread_id: int, side: str, companies: list[str] | None,
              audiences: list[str] | None = None, username: str | None = None) -> None:
    """Đánh dấu đã đọc (chỉ khi luồng nằm trong phạm vi tài khoản).

    Tập đoàn: mốc chung của Ban (`hq_read_at`). Đơn vị: mốc RIÊNG của người đang xem
    (`support_read`) — lãnh đạo mở thẻ không làm tắt "chưa đọc" của chuyên viên; vẫn ghi
    `unit_read_at` để Tập đoàn biết đơn vị đã mở thẻ.
    """
    params: dict[str, Any] = {"id": thread_id}
    col = "hq_read_at" if side == HQ else "unit_read_at"
    with session_scope() as db:
        hit = db.execute(
            text(f"UPDATE support_thread t SET {col} = now() "
                 f"WHERE id = :id{_scope_sql(companies, params, audiences=audiences)} RETURNING id"),
            params,
        ).first()
        if hit and side == UNIT and username:
            _touch_read(db, thread_id, username)


def set_status(thread_id: int, status: str, companies: list[str] | None,
               audiences: list[str] | None = None) -> bool:
    """Đóng / mở lại luồng. False nếu luồng ngoài phạm vi tài khoản."""
    params: dict[str, Any] = {"id": thread_id, "st": status}
    with session_scope() as db:
        res = db.execute(
            text(f"UPDATE support_thread t SET status = :st "
                 f"WHERE id = :id{_scope_sql(companies, params, audiences=audiences)}"),
            params,
        )
        return res.rowcount > 0


def delete_thread(thread_id: int) -> bool:
    """Xoá hẳn 1 luồng (chỉ quản trị) — xoá kèm toàn bộ tin + mốc đã đọc của luồng."""
    with session_scope() as db:
        db.execute(text("DELETE FROM support_message WHERE thread_id = :t"), {"t": thread_id})
        db.execute(text("DELETE FROM support_read WHERE thread_id = :t"), {"t": thread_id})
        res = db.execute(text("DELETE FROM support_thread WHERE id = :t"), {"t": thread_id})
        return res.rowcount > 0


def companies_of_reminder_file(name: str) -> bool:
    """File có thuộc một lịch nhắc CHƯA phát không — để Tập đoàn xem lại đính kèm đã soạn."""
    with session_scope() as db:
        return bool(db.execute(
            text("SELECT 1 FROM support_reminder WHERE files @> CAST(:f AS jsonb) LIMIT 1"),
            {"f": json.dumps([{"file": name}])},
        ).first())
