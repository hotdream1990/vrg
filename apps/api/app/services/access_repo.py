"""Lịch sử truy cập — ghi vết ĐĂNG NHẬP và LƯỢT VÀO TRANG + tra cứu.

Nguyên tắc (giống Nhật ký hoạt động ở `audit_repo`):
  - Append-only: mỗi sự kiện 1 dòng, không sửa không ghi đè.
  - Ghi vết KHÔNG được chặn nghiệp vụ: mọi lỗi ở đây chỉ log warning rồi bỏ qua.
  - Chỉ ghi "vào trang nào", KHÔNG ghi bộ lọc/nội dung đang xem (vừa nặng vừa soi quá mức).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.core import request_ctx
from app.core.access_meta import EVENTS, normalize_path, page_label
from app.core.db import ensure_schema, session_scope
from app.core.security import UNIT_ROLES

logger = logging.getLogger("vrg.access")

#: Cùng người + cùng trang trong bấy nhiêu giây → không ghi thêm dòng (React render lại, bấm F5).
DEDUP_SECONDS = 30

#: Giữ lịch sử bấy nhiêu ngày (hơn 1 năm để còn đối chiếu cùng kỳ), cũ hơn thì dọn.
RETENTION_DAYS = 400

_COLUMNS = "username, role, on_behalf, event, path, label, company, ip, user_agent"
_VALUES = ":username, :role, :on_behalf, :event, :path, :label, :company, :ip, :ua"

_INSERT = text(f"INSERT INTO access_log ({_COLUMNS}) VALUES ({_VALUES})")

#: Bản ghi lượt xem trang: chèn TRONG CÙNG MỘT LỆNH với phép kiểm trùng, thay vì "hỏi trước, ghi
#: sau" — hai request gần như đồng thời (mở 2 tab, React bắn lặp) sẽ không cùng lọt qua bước hỏi.
_INSERT_IF_NEW = text(f"""
    INSERT INTO access_log ({_COLUMNS})
    SELECT {_VALUES}
    WHERE NOT EXISTS (
        SELECT 1 FROM access_log
        WHERE username = :username AND path = :path AND event = 'page'
          AND at > now() - interval '{DEDUP_SECONDS} seconds'
    )
""")


def company_of(user: dict[str, Any] | None) -> str | None:
    """Đơn vị được gán (tài khoản đơn vị/lãnh đạo có thể gán nhiều đơn vị)."""
    # Chỉ vai trò gắn đơn vị mới có "đơn vị" để ghi (dùng chung danh sách với phân quyền).
    if not user or user.get("role") not in UNIT_ROLES:
        return None
    units = [u for u in (user.get("member_units") or []) if u]
    return ", ".join(units) or None


def _write(event: str, username: str, *, role: str = "", company: str | None = None,
           path: str = "", label: str = "", user_agent: str = "",
           dedup: bool = False) -> None:
    """Ghi 1 dòng lịch sử truy cập. Nuốt mọi lỗi (không bao giờ làm hỏng request của người dùng)."""
    try:
        ensure_schema()
        with session_scope() as db:
            db.execute(_INSERT_IF_NEW if dedup else _INSERT, {
                "username": username, "role": role or None,
                "on_behalf": request_ctx.on_behalf() or None,
                "event": event, "path": path, "label": label, "company": company,
                "ip": request_ctx.client_ip() or None, "ua": (user_agent or "")[:300] or None,
            })
    except Exception as exc:  # noqa: BLE001 - ghi vết hỏng KHÔNG được chặn đăng nhập/điều hướng
        logger.warning("[access] Không ghi được lịch sử truy cập (%s/%s): %s", event, username, exc)


def log_login(username: str, user: dict[str, Any] | None = None, *,
              ok: bool = True, user_agent: str = "") -> None:
    """Đăng nhập thành công (`ok=True`) hoặc sai mật khẩu/không có tài khoản (`ok=False`)."""
    _write("login" if ok else "login_failed", username,
           role=str((user or {}).get("role") or ""), company=company_of(user),
           path="/login", label=page_label("/login"), user_agent=user_agent)


def log_page(user: dict[str, Any], raw_path: str, user_agent: str = "") -> None:
    """Một lượt vào trang (web bắn khi đổi route)."""
    path = normalize_path(raw_path)
    _write("page", str(user.get("username") or ""), role=str(user.get("role") or ""),
           company=company_of(user), path=path, label=page_label(path),
           user_agent=user_agent, dedup=True)


def build_filters(date_from: str | None, date_to: str | None, username: str | None,
             role: str | None, event: str | None, company: str | None,
             q: str | None) -> tuple[str, dict[str, Any]]:
    """Mệnh đề WHERE dùng chung cho tra cứu chi tiết và bảng tổng hợp (`access_stats`)."""
    where, params = ["1 = 1"], {}
    if date_from:
        where.append("at >= CAST(:df AS date)")
        params["df"] = date_from
    if date_to:  # tới HẾT ngày date_to
        where.append("at < CAST(:dt AS date) + interval '1 day'")
        params["dt"] = date_to
    if username:
        where.append("username = :u")
        params["u"] = username
    if role:
        where.append("role = :r")
        params["r"] = role
    if event:
        where.append("event = :e")
        params["e"] = event
    if company:
        where.append("company ILIKE :c")
        params["c"] = f"%{company}%"
    if q:
        where.append("(username ILIKE :q OR label ILIKE :q OR path ILIKE :q OR ip ILIKE :q)")
        params["q"] = f"%{q}%"
    return " AND ".join(where), params


def search(date_from: str | None = None, date_to: str | None = None,
           username: str | None = None, role: str | None = None, event: str | None = None,
           company: str | None = None, q: str | None = None,
           limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Tra cứu chi tiết (mới nhất trước) → {items, total}."""
    ensure_schema()
    clause, params = build_filters(date_from, date_to, username, role, event, company, q)
    with session_scope() as db:
        total = db.execute(text(f"SELECT count(*) FROM access_log WHERE {clause}"),
                           params).scalar() or 0
        rows = db.execute(text(f"""
            SELECT id, at, username, role, on_behalf, event, path, label, company, ip, user_agent
            FROM access_log WHERE {clause} ORDER BY at DESC, id DESC LIMIT :lim OFFSET :off
        """), {**params, "lim": limit, "off": offset}).mappings().all()
    return {"items": [_out(r) for r in rows], "total": int(total)}


def _out(r) -> dict[str, Any]:  # noqa: ANN001 - RowMapping
    return {
        "id": int(r["id"]),
        "at": str(r["at"]),
        "username": r["username"],
        "role": r["role"] or "",
        "on_behalf": r["on_behalf"] or "",
        "event": r["event"],
        "event_label": EVENTS.get(r["event"], r["event"]),
        "path": r["path"] or "",
        "label": r["label"] or r["path"] or "",
        "company": r["company"] or "",
        "ip": r["ip"] or "",
        "user_agent": r["user_agent"] or "",
    }


def known_users() -> list[str]:
    """Danh sách đổ vào ô lọc "Tài khoản".

    Liệt kê MỌI tài khoản còn dùng được, kể cả người chưa truy cập lần nào — nếu chỉ liệt kê người
    đã có vết thì không chọn được đúng người cần kiểm tra, mà "chưa từng vào" mới là điều cần biết.
    Thêm cả tài khoản đã bị xoá nhưng từng ĐĂNG NHẬP THÀNH CÔNG (lịch sử của họ vẫn tra được).
    Cố ý KHÔNG lấy tên gõ ở các lần đăng nhập hỏng — ai cũng gõ được chuỗi bất kỳ vào ô đăng nhập.
    """
    from app.services import user_repo  # lazy: tránh nhập vòng khi user_repo ghi nhật ký

    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT DISTINCT username FROM access_log WHERE event = 'login'"
        )).scalars().all()
    accounts = {u["username"] for u in user_repo.list_users() if u.get("is_active", True)}
    return sorted(accounts | set(rows))


def purge_old(days: int = RETENTION_DAYS) -> int:
    """Dọn lịch sử quá hạn lưu (gọi lúc khởi động API) → số dòng đã xoá."""
    try:
        ensure_schema()
        with session_scope() as db:
            res = db.execute(text("DELETE FROM access_log WHERE at < now() - CAST(:d AS interval)"),
                             {"d": f"{int(days)} days"})
        return res.rowcount or 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("[access] Không dọn được lịch sử cũ: %s", exc)
        return 0
