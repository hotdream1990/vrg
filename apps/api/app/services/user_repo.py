"""Repository tài khoản đăng nhập (app_user) + seed admin từ config."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.db import ensure_schema, session_scope
from app.core.permissions import clean_caps
from app.core.security import hash_password, verify_password


def _norm(row: Any) -> dict[str, Any]:
    """Chuẩn hoá 1 dòng app_user → dict, đảm bảo `permissions` luôn là list."""
    d = dict(row)
    if "permissions" in d:
        d["permissions"] = list(d["permissions"] or [])
    return d


def seed_admin() -> None:
    """Tạo tài khoản admin lần đầu nếu bảng trống (mật khẩu từ env/config)."""
    ensure_schema()
    with session_scope() as db:
        n = db.execute(text("SELECT count(*) FROM app_user")).scalar() or 0
        if n == 0:
            db.execute(
                text("INSERT INTO app_user (username, password_hash, full_name, role) "
                     "VALUES (:u, :p, :f, 'admin')"),
                {"u": settings.admin_username,
                 "p": hash_password(settings.admin_password),
                 "f": "Quản trị viên"},
            )
            if settings.admin_password == "admin":
                print("[auth] ⚠ Seed admin với mật khẩu MẶC ĐỊNH 'admin' — đổi ngay qua .env "
                      "(ADMIN_PASSWORD) khi triển khai.")


def get_user(username: str) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT username, full_name, role, is_active, permissions "
                 "FROM app_user WHERE username = :u"),
            {"u": username},
        ).mappings().first()
        return _norm(row) if row else None


def list_users() -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT username, full_name, role, is_active, permissions "
                 "FROM app_user ORDER BY created_at"),
        ).mappings().all()
        return [_norm(r) for r in rows]


def _count_active_admins(db) -> int:  # noqa: ANN001 - session nội bộ
    return db.execute(
        text("SELECT count(*) FROM app_user WHERE role = 'admin' AND is_active = true"),
    ).scalar() or 0


def create_user(username: str, password: str, full_name: str | None, role: str,
                permissions: list[str] | None = None) -> dict[str, Any]:
    """Tạo tài khoản mới. Raise ValueError nếu username đã tồn tại. `permissions` chỉ có ý nghĩa với editor."""
    ensure_schema()
    u = username.strip()
    with session_scope() as db:
        if db.execute(text("SELECT 1 FROM app_user WHERE username = :u"), {"u": u}).first():
            raise ValueError(f"Tài khoản '{u}' đã tồn tại")
        db.execute(
            text("INSERT INTO app_user (username, password_hash, full_name, role, permissions) "
                 "VALUES (:u, :p, :f, :r, CAST(:perms AS jsonb))"),
            {"u": u, "p": hash_password(password), "f": full_name, "r": role or "admin",
             "perms": json.dumps(clean_caps(permissions))},
        )
    return get_user(u)  # type: ignore[return-value]


def update_user(username: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Cập nhật full_name/role/is_active/permissions. Chặn khoá/hạ quyền admin cuối cùng (ValueError)."""
    allowed = {k: v for k, v in fields.items() if k in ("full_name", "role", "is_active")}
    has_perms = "permissions" in fields
    ensure_schema()
    with session_scope() as db:
        cur = db.execute(
            text("SELECT role, is_active FROM app_user WHERE username = :u"), {"u": username},
        ).mappings().first()
        if not cur:
            return None
        losing_admin = allowed.get("is_active") is False or (
            "role" in allowed and allowed["role"] != "admin"
        )
        if losing_admin and cur["role"] == "admin" and cur["is_active"] and _count_active_admins(db) <= 1:
            raise ValueError("Không thể khoá hoặc hạ quyền quản trị viên cuối cùng")
        sets = [f"{k} = :{k}" for k in allowed]
        params: dict[str, Any] = {**allowed, "u": username}
        if has_perms:
            sets.append("permissions = CAST(:permissions AS jsonb)")
            params["permissions"] = json.dumps(clean_caps(fields.get("permissions")))
        if sets:
            db.execute(text(f"UPDATE app_user SET {', '.join(sets)} WHERE username = :u"), params)
    return get_user(username)


def delete_user(username: str) -> bool:
    """Xoá tài khoản. Chặn xoá admin cuối cùng (ValueError). False nếu không tồn tại."""
    ensure_schema()
    with session_scope() as db:
        cur = db.execute(
            text("SELECT role, is_active FROM app_user WHERE username = :u"), {"u": username},
        ).mappings().first()
        if not cur:
            return False
        if cur["role"] == "admin" and cur["is_active"] and _count_active_admins(db) <= 1:
            raise ValueError("Không thể xoá quản trị viên cuối cùng")
        db.execute(text("DELETE FROM app_user WHERE username = :u"), {"u": username})
    return True


def update_profile(username: str, full_name: str | None) -> dict[str, Any] | None:
    """User tự cập nhật hồ sơ (chỉ họ tên)."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(
            text("UPDATE app_user SET full_name = :f WHERE username = :u"),
            {"f": full_name, "u": username},
        )
        if res.rowcount == 0:
            return None
    return get_user(username)


def set_password(username: str, new_password: str) -> bool:
    """Admin đặt lại mật khẩu cho user (không cần mật khẩu cũ)."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(
            text("UPDATE app_user SET password_hash = :p WHERE username = :u"),
            {"p": hash_password(new_password), "u": username},
        )
        return res.rowcount > 0


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """User tự đổi mật khẩu. Raise ValueError nếu mật khẩu cũ sai; False nếu không tồn tại."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT password_hash FROM app_user WHERE username = :u"), {"u": username},
        ).mappings().first()
        if not row:
            return False
        if not verify_password(old_password, row["password_hash"]):
            raise ValueError("Mật khẩu hiện tại không đúng")
        db.execute(
            text("UPDATE app_user SET password_hash = :p WHERE username = :u"),
            {"p": hash_password(new_password), "u": username},
        )
    return True


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    """Trả thông tin user nếu đúng mật khẩu + còn active, ngược lại None."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT username, password_hash, full_name, role, is_active, permissions "
                 "FROM app_user WHERE username = :u"),
            {"u": username},
        ).mappings().first()
    if not row or not row["is_active"] or not verify_password(password, row["password_hash"]):
        return None
    return {"username": row["username"], "full_name": row["full_name"], "role": row["role"],
            "permissions": list(row["permissions"] or [])}
