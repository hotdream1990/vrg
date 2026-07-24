"""Nhật ký hoạt động (audit log) — ghi vết MỌI thay đổi số liệu + tra cứu.

Nguyên tắc:
  - Mỗi lần ghi/xoá = 1 DÒNG MỚI (không ghi đè) → truy được ai · lúc nào · sửa gì · từ đâu sang đâu.
  - Gắn ở tầng REPO (choke point) nên mọi lối vào đều được ghi: màn chuyên viên, màn đơn vị
    thành viên (/api/member), nhập từ file Excel, link công khai, job tự chạy.
  - Ghi nhật ký KHÔNG được làm hỏng nghiệp vụ: mọi lỗi ở đây chỉ log warning rồi bỏ qua.
  - Không lưu mật khẩu/secret — nơi gọi phải che trước khi truyền vào (xem `user_repo`, `config_repo`).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from app.core import request_ctx
from app.core.audit_meta import ACTIONS, ENTITIES
from app.core.db import ensure_schema, session_scope

logger = logging.getLogger("vrg.audit")

#: Gộp các lần lưu liên tiếp của CÙNG người trên CÙNG bản ghi trong bấy nhiêu phút.
#: Dùng cho màn tự động lưu (báo giá, bản tin) — tránh mỗi lần gõ phím sinh 1 dòng nhật ký.
COALESCE_MINUTES = 10

_INSERT = text("""
    INSERT INTO audit_log
        (actor, actor_role, on_behalf, entity, action, entity_key, as_of, company,
         data_before, data_after, ip, note)
    VALUES
        (:actor, :role, :behalf, :entity, :action, :key, CAST(:as_of AS date), :company,
         CAST(:before AS jsonb), CAST(:after AS jsonb), :ip, :note)
""")


def _json(value: Any) -> str | None:
    """dict/list → chuỗi JSON cho cột jsonb. `default=str` để date/Decimal không làm vỡ."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _role_of(db, username: str) -> str:  # noqa: ANN001 - session nội bộ
    """Vai trò của người thao tác (nhớ trong request để không truy vấn lặp mỗi dòng)."""
    cached = request_ctx.cached_role()
    if cached:
        return cached
    if not username or username == request_ctx.SYSTEM_ACTOR \
            or username.startswith(request_ctx.PUBLIC_PREFIX):
        return ""
    row = db.execute(text("SELECT role FROM app_user WHERE username = :u"),
                     {"u": username}).first()
    role = str(row[0]) if row else ""
    request_ctx.cache_role(role)
    return role


def _merged(db, params: dict[str, Any]) -> bool:  # noqa: ANN001 - session nội bộ
    """Gộp vào dòng vừa ghi (cùng người · cùng bản ghi · trong COALESCE_MINUTES) — True nếu đã gộp.

    Giữ nguyên `data_before` của lần đầu nên diff vẫn là "trước khi bắt đầu sửa → hiện tại".
    """
    res = db.execute(text(f"""
        UPDATE audit_log SET data_after = CAST(:after AS jsonb), at = now(), note = :note
        WHERE id = (
            SELECT id FROM audit_log
            WHERE entity = :entity AND entity_key = :key AND actor = :actor AND action = :action
              AND at > now() - interval '{COALESCE_MINUTES} minutes'
            ORDER BY at DESC LIMIT 1
        )
    """), {k: params[k] for k in ("after", "note", "entity", "key", "actor", "action")})
    return res.rowcount > 0


def log(entity: str, action: str, key: str = "", *,
        before: Any = None, after: Any = None,
        as_of: str | None = None, company: str | None = None,
        note: str | None = None, actor: str | None = None,
        coalesce: bool = False) -> None:
    """Ghi 1 dòng nhật ký. Không bao giờ ném lỗi ra ngoài (nghiệp vụ luôn được ưu tiên).

    `coalesce=True` cho màn TỰ ĐỘNG LƯU: gộp các lần lưu liên tiếp của cùng người vào 1 dòng.
    """
    if request_ctx.is_paused():
        return
    if action == "update" and before == after:
        return  # bấm lưu nhưng không đổi gì → không ghi cho đỡ nhiễu
    try:
        ensure_schema()
        who = actor or request_ctx.actor()
        with session_scope() as db:
            params = {
                "actor": who, "role": _role_of(db, who), "behalf": request_ctx.on_behalf() or None,
                "entity": entity, "action": action, "key": key or "",
                "as_of": as_of, "company": company,
                "before": _json(before), "after": _json(after),
                "ip": request_ctx.client_ip() or None,
                "note": note or request_ctx.default_note() or None,
            }
            if coalesce and action == "update" and _merged(db, params):
                return
            db.execute(_INSERT, params)
    except Exception as exc:  # noqa: BLE001 - nhật ký hỏng KHÔNG được chặn việc nhập liệu
        logger.warning("[audit] Không ghi được nhật ký (%s/%s): %s", entity, action, exc)


def search(date_from: str | None = None, date_to: str | None = None,
           actor: str | None = None, entity: str | None = None, action: str | None = None,
           company: str | None = None, q: str | None = None,
           limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Tra cứu nhật ký (mới nhất trước) → {items, total}. Mọi bộ lọc đều tuỳ chọn."""
    ensure_schema()
    where, params = ["1 = 1"], {}
    if date_from:
        where.append("at >= CAST(:df AS date)")
        params["df"] = date_from
    if date_to:  # tới HẾT ngày date_to
        where.append("at < CAST(:dt AS date) + interval '1 day'")
        params["dt"] = date_to
    if actor:
        where.append("actor = :actor")
        params["actor"] = actor
    if entity:
        where.append("entity = :entity")
        params["entity"] = entity
    if action:
        where.append("action = :action")
        params["action"] = action
    if company:
        where.append("company = :company")
        params["company"] = company
    if q:
        where.append("(entity_key ILIKE :q OR company ILIKE :q OR note ILIKE :q "
                     "OR actor ILIKE :q OR data_before::text ILIKE :q OR data_after::text ILIKE :q)")
        params["q"] = f"%{q}%"
    clause = " AND ".join(where)
    with session_scope() as db:
        total = db.execute(text(f"SELECT count(*) FROM audit_log WHERE {clause}"), params).scalar() or 0
        rows = db.execute(text(f"""
            SELECT id, at, actor, actor_role, on_behalf, entity, action, entity_key,
                   as_of, company, data_before, data_after, ip, note
            FROM audit_log WHERE {clause} ORDER BY at DESC, id DESC LIMIT :lim OFFSET :off
        """), {**params, "lim": limit, "off": offset}).mappings().all()
    return {"items": [_out(r) for r in rows], "total": int(total)}


def _out(r) -> dict[str, Any]:  # noqa: ANN001 - RowMapping
    return {
        "id": int(r["id"]),
        "at": str(r["at"]),
        "actor": r["actor"],
        "actor_role": r["actor_role"] or "",
        "on_behalf": r["on_behalf"] or "",
        "entity": r["entity"],
        "entity_label": ENTITIES.get(r["entity"], r["entity"]),
        "action": r["action"],
        "action_label": ACTIONS.get(r["action"], r["action"]),
        "entity_key": r["entity_key"] or "",
        "as_of": str(r["as_of"]) if r["as_of"] else None,
        "company": r["company"] or "",
        "before": r["data_before"],
        "after": r["data_after"],
        "ip": r["ip"] or "",
        "note": r["note"] or "",
    }


def known_actors() -> list[str]:
    """Danh sách người từng thao tác (đổ vào ô lọc). Giới hạn 200 cho nhẹ."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT actor, max(at) AS last_at FROM audit_log GROUP BY actor "
            "ORDER BY last_at DESC LIMIT 200"
        )).mappings().all()
    return [r["actor"] for r in rows]
