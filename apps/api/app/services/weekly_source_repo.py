"""Danh mục nguồn tham khảo của Báo cáo tuần (bảng `weekly_source`) — CRUD + seed mặc định.

Bảng rỗng → tự seed `weekly_source_defaults.DEFAULT_SOURCES` ở lượt đọc đầu. Mọi thao tác ghi
đều ghi Nhật ký hoạt động (nhóm `bulletin_weekly`).
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo
from app.services.weekly_source_defaults import CATEGORIES, DEFAULT_SOURCES, MODES, SECTIONS

_ENTITY = "bulletin_weekly"
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9=.^@\-]{1,20}$")  # mã kiểu Yahoo (CL=F) hoặc CNBC (@LCO.1)
_FIELDS = ("category", "name", "role", "url", "sections", "guide", "mode", "feed_symbol",
           "enabled", "sort_order")
_COLS = "id, category, name, role, url, sections, guide, mode, feed_symbol, enabled, sort_order, " \
        "updated_by, updated_at"


ALLOWED_NEWS_HOSTS = {"vietnambiz.vn", "www.vietnambiz.vn"}


def is_vietnambiz_url(url: str) -> bool:
    """URL http(s) thuộc vietnambiz.vn (kể cả www.)."""
    from urllib.parse import urlparse

    try:
        u = urlparse(url or "")
    except ValueError:
        return False
    return u.scheme in ("http", "https") and (u.hostname or "").lower() in ALLOWED_NEWS_HOSTS


def clean_source(data: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hoá + kiểm 1 nguồn (hàm thuần). ValueError với thông báo tiếng Việt nếu sai."""
    category = str(data.get("category") or "").strip()
    if category not in CATEGORIES:
        raise ValueError(f"Nhóm nguồn không hợp lệ: “{category}”.")
    mode = str(data.get("mode") or "").strip()
    if mode not in MODES:
        raise ValueError(f"Cách dùng nguồn không hợp lệ: “{mode}”.")
    name = re.sub(r"\s+", " ", str(data.get("name") or "")).strip()
    if not name:
        raise ValueError("Nhập tên nguồn.")
    if len(name) > 200:
        raise ValueError("Tên nguồn tối đa 200 ký tự.")
    url = str(data.get("url") or "").strip()
    if url and not re.match(r"^https?://\S+$", url, flags=re.I):
        raise ValueError("Đường dẫn phải bắt đầu bằng http:// hoặc https://.")
    if mode == "vietnambiz" and not is_vietnambiz_url(url):
        # Server tự mở link này → chỉ cho đúng tên miền vietnambiz (chặn SSRF vào mạng nội bộ).
        raise ValueError("Nguồn tự đọc bài vietnambiz chỉ nhận đường dẫn https://vietnambiz.vn/….")
    raw_sections = data.get("sections") or []
    if not isinstance(raw_sections, list):
        raise ValueError("Danh sách mục báo cáo không hợp lệ.")
    bad = [s for s in raw_sections if s not in SECTIONS]
    if bad:
        raise ValueError(f"Mục báo cáo không hợp lệ: {', '.join(map(str, bad))}.")
    sections = [s for s in SECTIONS if s in raw_sections]  # bỏ trùng, giữ thứ tự báo cáo
    symbol = str(data.get("feed_symbol") or "").strip() or None
    if mode == "market_feed" and not symbol:
        raise ValueError("Nguồn tự lấy số liệu thị trường phải có mã (vd DX-Y.NYB, CL=F).")
    if symbol and not _SYMBOL_RE.match(symbol):
        raise ValueError("Mã số liệu chỉ gồm chữ, số và . = ^ @ - (tối đa 20 ký tự).")
    try:
        sort_order = int(data.get("sort_order") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Thứ tự hiển thị phải là số nguyên.") from exc
    return {
        "category": category, "name": name, "role": str(data.get("role") or "").strip()[:500],
        "url": url, "sections": sections, "guide": str(data.get("guide") or "").strip()[:8000],
        "mode": mode, "feed_symbol": symbol, "enabled": bool(data.get("enabled", True)),
        "sort_order": sort_order,
    }


def _out(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["sections"] = list(d.get("sections") or [])
    d["updated_at"] = d["updated_at"].isoformat() if d.get("updated_at") else None
    return d


def _params(src: dict[str, Any], username: str | None) -> dict[str, Any]:
    return {**src, "sections": json.dumps(src["sections"]), "updated_by": username}


def _insert_defaults(db: Any, username: str | None) -> None:
    for i, raw in enumerate(DEFAULT_SOURCES):
        src = clean_source({**raw, "sort_order": (i + 1) * 10})
        db.execute(text("""
            INSERT INTO weekly_source (category, name, role, url, sections, guide, mode, feed_symbol,
                                       enabled, sort_order, updated_by)
            VALUES (:category, :name, :role, :url, CAST(:sections AS jsonb), :guide, :mode,
                    :feed_symbol, :enabled, :sort_order, :updated_by)
        """), _params(src, username))


def _seed_if_empty() -> None:
    with session_scope() as db:
        if db.execute(text("SELECT 1 FROM weekly_source LIMIT 1")).first():
            return
        # Khoá bảng rồi kiểm lại: 2 lượt đọc đầu cùng lúc không seed trùng.
        db.execute(text("LOCK TABLE weekly_source IN EXCLUSIVE MODE"))
        if not db.execute(text("SELECT 1 FROM weekly_source LIMIT 1")).first():
            _insert_defaults(db, "system")


def list_sources(enabled_only: bool = False) -> list[dict[str, Any]]:
    """Mọi nguồn theo thứ tự hiển thị (seed mặc định nếu bảng rỗng)."""
    ensure_schema()
    _seed_if_empty()
    where = "WHERE enabled" if enabled_only else ""
    with session_scope() as db:
        rows = db.execute(text(f"SELECT {_COLS} FROM weekly_source {where} "
                               "ORDER BY sort_order, id")).mappings().all()
    return [_out(r) for r in rows]


def sources_for_section(key: str) -> list[dict[str, Any]]:
    """Nguồn ĐANG BẬT dùng cho 1 mục báo cáo (vd 'IV.3')."""
    return [s for s in list_sources(enabled_only=True) if key in s["sections"]]


def get_source(source_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(f"SELECT {_COLS} FROM weekly_source WHERE id = :i"),
                       {"i": source_id}).mappings().first()
    return _out(r) if r else None


MAX_ENABLED_FEEDS = 10  # mỗi mã gọi nguồn ngoài (CNBC/Yahoo) khi mở màn — trần chặn cấu hình làm chậm/treo trang


def _check_feed_limit(src: dict[str, Any], exclude_id: int | None = None) -> None:
    """Không cho bật quá MAX_ENABLED_FEEDS nguồn tự lấy số liệu thị trường."""
    if not (src["enabled"] and src["mode"] == "market_feed"):
        return
    with session_scope() as db:
        n = db.execute(text("SELECT count(*) FROM weekly_source WHERE enabled AND mode = 'market_feed' "
                            "AND (CAST(:x AS int) IS NULL OR id <> :x)"), {"x": exclude_id}).scalar() or 0
    if n >= MAX_ENABLED_FEEDS:
        raise ValueError(f"Chỉ bật tối đa {MAX_ENABLED_FEEDS} nguồn tự lấy số liệu thị trường — tắt bớt nguồn cũ.")


def create_source(data: dict[str, Any], username: str | None) -> dict[str, Any]:
    src = clean_source(data)
    _check_feed_limit(src)
    ensure_schema()
    with session_scope() as db:
        if not data.get("sort_order"):  # không nhập thứ tự → xếp cuối danh sách
            src["sort_order"] = int(db.execute(text(
                "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM weekly_source")).scalar() or 10)
        r = db.execute(text(f"""
            INSERT INTO weekly_source (category, name, role, url, sections, guide, mode, feed_symbol,
                                       enabled, sort_order, updated_by)
            VALUES (:category, :name, :role, :url, CAST(:sections AS jsonb), :guide, :mode,
                    :feed_symbol, :enabled, :sort_order, :updated_by)
            RETURNING {_COLS}
        """), _params(src, username)).mappings().first()
    created = _out(r)
    audit_repo.log(_ENTITY, "create", f"source:{created['id']}", after=created,
                   note=f"Thêm nguồn tham khảo: {created['name']}")
    return created


def update_source(source_id: int, data: dict[str, Any], username: str | None) -> dict[str, Any] | None:
    """Sửa 1 nguồn — `data` có thể chỉ chứa vài trường (ghép với bản hiện có rồi kiểm lại)."""
    before = get_source(source_id)
    if not before:
        return None
    # null chỉ có nghĩa "xoá" với mã số liệu; trường khác gửi null coi như không đổi
    changes = {k: v for k, v in data.items() if k in _FIELDS and (v is not None or k == "feed_symbol")}
    merged = {k: before[k] for k in _FIELDS} | changes
    src = clean_source(merged)
    _check_feed_limit(src, source_id)
    with session_scope() as db:
        r = db.execute(text(f"""
            UPDATE weekly_source SET category = :category, name = :name, role = :role, url = :url,
                   sections = CAST(:sections AS jsonb), guide = :guide, mode = :mode,
                   feed_symbol = :feed_symbol, enabled = :enabled, sort_order = :sort_order,
                   updated_by = :updated_by, updated_at = now()
             WHERE id = :id RETURNING {_COLS}
        """), {**_params(src, username), "id": source_id}).mappings().first()
    if not r:
        return None
    after = _out(r)
    audit_repo.log(_ENTITY, "update", f"source:{source_id}",
                   before={k: before[k] for k in _FIELDS}, after={k: after[k] for k in _FIELDS},
                   note=f"Sửa nguồn tham khảo: {after['name']}")
    return after


def delete_source(source_id: int) -> bool:
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(f"DELETE FROM weekly_source WHERE id = :i RETURNING {_COLS}"),
                       {"i": source_id}).mappings().first()
    if not r:
        return False
    before = _out(r)
    audit_repo.log(_ENTITY, "delete", f"source:{source_id}", before=before,
                   note=f"Xoá nguồn tham khảo: {before['name']}")
    return True


def reset_defaults(username: str | None) -> list[dict[str, Any]]:
    """Xoá toàn bộ danh mục rồi nạp lại bộ mặc định."""
    ensure_schema()
    with session_scope() as db:
        count = db.execute(text("SELECT count(*) FROM weekly_source")).scalar() or 0
        db.execute(text("DELETE FROM weekly_source"))
        _insert_defaults(db, username)
    audit_repo.log(_ENTITY, "update", "sources:reset", after={"count": len(DEFAULT_SOURCES)},
                   note=f"Khôi phục nguồn tham khảo mặc định (thay {count} nguồn cũ)")
    return list_sources()
