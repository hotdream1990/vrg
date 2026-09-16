"""Bảng tổng hợp Lịch sử truy cập: MỖI TÀI KHOẢN dùng hệ thống ra sao.

Trả lời đúng câu hỏi của admin — "lãnh đạo đơn vị có vào hệ thống không, vào những trang nào":
đăng nhập gần nhất · số lần đăng nhập · số lượt xem trang · số ngày có hoạt động · trang hay vào nhất.
Tài khoản CHƯA truy cập lần nào vẫn có một dòng (mọi số bằng 0) — "ai được cấp tài khoản mà không
dùng" chính là câu hỏi đáng giá nhất ở đây, im lặng bỏ họ ra khỏi bảng là giấu mất câu trả lời.

⚠ Bảng này BỎ QUA những lượt do quản trị "đăng nhập hộ" (`on_behalf`). Tính cả vào thì con số nói
người đó đang dùng hệ thống, trong khi thực chất là quản trị đang thao tác thay — đúng thứ làm sai
lệch câu hỏi cần trả lời. Tab "Chi tiết" vẫn hiện đủ, có ghi rõ ai đăng nhập hộ ai.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import user_repo
from app.services.access_repo import build_filters, company_of

#: Lượt "đăng nhập hộ" không tính vào thống kê sử dụng của chủ tài khoản (xem docstring).
_OWN_ACTIVITY = "on_behalf IS NULL"


def summary(date_from: str | None = None, date_to: str | None = None,
            username: str | None = None, role: str | None = None,
            company: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    """Mỗi tài khoản 1 dòng, sắp theo hoạt động gần nhất. Bộ lọc `event` cố ý KHÔNG áp ở đây
    (đang gộp cả đăng nhập lẫn lượt xem để ra bức tranh sử dụng)."""
    ensure_schema()
    clause, params = build_filters(date_from, date_to, username, role, None, company, q)
    with session_scope() as db:
        rows = db.execute(text(f"""
            SELECT username,
                   max(role) FILTER (WHERE role <> '') AS role,
                   max(company) AS company,
                   max(at) AS last_seen,
                   max(at) FILTER (WHERE event = 'login') AS last_login,
                   count(*) FILTER (WHERE event = 'login') AS logins,
                   count(*) FILTER (WHERE event = 'login_failed') AS failed_logins,
                   count(*) FILTER (WHERE event = 'page') AS page_views,
                   count(DISTINCT date_trunc('day', at)) AS active_days,
                   count(DISTINCT path) FILTER (WHERE event = 'page') AS distinct_pages
            FROM access_log WHERE {clause} AND {_OWN_ACTIVITY}
            GROUP BY username ORDER BY max(at) DESC
        """), params).mappings().all()
        tops = db.execute(text(f"""
            SELECT DISTINCT ON (username) username, label, path, count(*) AS views
            FROM access_log WHERE {clause} AND {_OWN_ACTIVITY} AND event = 'page'
            GROUP BY username, label, path
            ORDER BY username, count(*) DESC, label
        """), params).mappings().all()
    top_by_user = {t["username"]: t for t in tops}
    items = [_out(r, top_by_user.get(r["username"])) for r in rows]
    seen = {r["username"] for r in items}
    idle = [_never_seen(u) for u in _roster(username, role, company, q) if u["username"] not in seen]
    return items + sorted(idle, key=lambda r: r["username"])


def _roster(username: str | None, role: str | None,
            company: str | None, q: str | None) -> list[dict[str, Any]]:
    """Tài khoản còn dùng được, lọc theo đúng các ô đang chọn (bỏ ô ngày — chưa vào thì không có ngày).

    Tài khoản đã khoá cố ý không liệt kê: đã khoá thì "chưa truy cập" là chuyện đương nhiên.
    """
    needle = (q or "").lower()
    out = []
    for u in user_repo.list_users():
        units = u.get("member_units") or []
        if not u.get("is_active", True):
            continue
        if username and u["username"] != username:
            continue
        if role and u.get("role") != role:
            continue
        if company and company not in units:
            continue
        if needle and needle not in u["username"].lower() \
                and not any(needle in unit.lower() for unit in units):
            continue
        out.append(u)
    return out


def _never_seen(user: dict[str, Any]) -> dict[str, Any]:
    """Dòng cho tài khoản chưa hề truy cập — mọi số bằng 0, hai mốc thời gian để trống."""
    return {
        "username": user["username"], "role": user.get("role") or "",
        "company": company_of(user) or "", "last_seen": None, "last_login": None,
        "logins": 0, "failed_logins": 0, "page_views": 0, "active_days": 0,
        "distinct_pages": 0, "top_page": "", "top_page_views": 0,
    }


def _out(r, top) -> dict[str, Any]:  # noqa: ANN001 - RowMapping
    return {
        "username": r["username"],
        "role": r["role"] or "",
        "company": r["company"] or "",
        "last_seen": str(r["last_seen"]) if r["last_seen"] else None,
        "last_login": str(r["last_login"]) if r["last_login"] else None,
        "logins": int(r["logins"] or 0),
        "failed_logins": int(r["failed_logins"] or 0),
        "page_views": int(r["page_views"] or 0),
        "active_days": int(r["active_days"] or 0),
        "distinct_pages": int(r["distinct_pages"] or 0),
        "top_page": (top["label"] or top["path"]) if top else "",
        "top_page_views": int(top["views"]) if top else 0,
    }


def top_pages(date_from: str | None = None, date_to: str | None = None,
              username: str | None = None, role: str | None = None,
              company: str | None = None, q: str | None = None,
              limit: int = 30) -> list[dict[str, Any]]:
    """Xếp hạng trang được xem nhiều nhất (theo đúng bộ lọc đang xem)."""
    ensure_schema()
    clause, params = build_filters(date_from, date_to, username, role, None, company, q)
    with session_scope() as db:
        rows = db.execute(text(f"""
            SELECT path, max(label) AS label, count(*) AS views,
                   count(DISTINCT username) AS users
            FROM access_log WHERE {clause} AND {_OWN_ACTIVITY} AND event = 'page'
            GROUP BY path ORDER BY count(*) DESC, path LIMIT :lim
        """), {**params, "lim": limit}).mappings().all()
    return [{"path": r["path"], "label": r["label"] or r["path"],
             "views": int(r["views"]), "users": int(r["users"])} for r in rows]
