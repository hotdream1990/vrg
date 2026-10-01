"""Repository tài khoản đăng nhập (app_user) + seed admin từ config.

Nhật ký hoạt động của nhóm này KHÔNG BAO GIỜ chứa mật khẩu/hash — đổi mật khẩu chỉ ghi
nhận SỰ KIỆN (ai đổi, lúc nào), không ghi giá trị.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.db import ensure_schema, session_scope
from app.core.entry_types import ENTRY_TYPES, clean_entry_types
from app.core.permissions import clean_caps
from app.core.security import UNIT_ROLES, hash_password, verify_password
from app.services import audit_repo


#: Cột của mọi dict user trả ra ngoài (KHÔNG có password_hash) — một chỗ, thêm cột khỏi sót nơi nào.
_USER_COLS = "username, full_name, email, role, is_active, permissions, member_units, entry_types"
ENTRY_TYPES_REQUIRED = "Tài khoản nhập liệu đơn vị phải được giao ít nhất một loại nhập liệu"


def _norm(row: Any) -> dict[str, Any]:
    """Chuẩn hoá 1 dòng app_user → dict, đảm bảo `permissions`/`member_units`/`entry_types` là list."""
    d = dict(row)
    if "permissions" in d:
        d["permissions"] = list(d["permissions"] or [])
    if "member_units" in d:
        d["member_units"] = list(d["member_units"] or [])
    if "entry_types" in d:
        # Chỉ tài khoản nhập liệu (member) có loại; vai trò khác trả rỗng dù cột vẫn mang mặc định.
        d["entry_types"] = clean_entry_types(d["entry_types"]) if d.get("role") == "member" else []
    return d


def _entry_types_for(role: str, raw: list[str] | None, current: list[str] | None = None) -> list[str]:
    """Loại nhập liệu sẽ LƯU. Chỉ role member có (vai trò khác lưu rỗng).

    Không chỉ định (`raw` None) → giữ loại đang có; chưa có (tạo mới / vừa chuyển sang member) thì
    giao đủ 3 loại — đúng mặc định của cột, không ai tự dưng mất quyền. Chỉ định mà rỗng → lỗi.
    """
    if role != "member":
        return []
    if raw is None:
        return clean_entry_types(current) or list(ENTRY_TYPES)
    types = clean_entry_types(raw)
    if not types:
        raise ValueError(ENTRY_TYPES_REQUIRED)
    return types


def _clean_units(units: list[str] | None) -> list[str]:
    """Bỏ trống, strip, khử trùng lặp, giữ thứ tự (chuẩn hoá danh sách đơn vị của member)."""
    seen: set[str] = set()
    out: list[str] = []
    for u in units or []:
        u = (u or "").strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


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
            text(f"SELECT {_USER_COLS} FROM app_user WHERE username = :u"),
            {"u": username},
        ).mappings().first()
        return _norm(row) if row else None


def list_users() -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT {_USER_COLS} FROM app_user ORDER BY created_at"),
        ).mappings().all()
        return [_norm(r) for r in rows]


def _count_active_admins(db) -> int:  # noqa: ANN001 - session nội bộ
    return db.execute(
        text("SELECT count(*) FROM app_user WHERE role = 'admin' AND is_active = true"),
    ).scalar() or 0


def create_user(username: str, password: str, full_name: str | None, role: str,
                permissions: list[str] | None = None,
                member_units: list[str] | None = None,
                email: str | None = None,
                entry_types: list[str] | None = None) -> dict[str, Any]:
    """Tạo tài khoản mới. Raise ValueError nếu username đã tồn tại / member không còn loại nào.

    `permissions` chỉ có ý nghĩa với editor; `member_units` gắn cho các vai trò gắn đơn vị
    (`UNIT_ROLES`: đơn vị thành viên nhập liệu + lãnh đạo đơn vị); `entry_types` chỉ cho member
    (None = đủ 3 loại — xem `_entry_types_for`).
    """
    ensure_schema()
    u = username.strip()
    role = role or "admin"
    units = _clean_units(member_units) if role in UNIT_ROLES else []
    types = _entry_types_for(role, entry_types)
    with session_scope() as db:
        if db.execute(text("SELECT 1 FROM app_user WHERE username = :u"), {"u": u}).first():
            raise ValueError(f"Tài khoản '{u}' đã tồn tại")
        db.execute(
            text("INSERT INTO app_user (username, password_hash, full_name, email, role, permissions, "
                 "member_units, entry_types) VALUES (:u, :p, :f, :e, :r, CAST(:perms AS jsonb), "
                 "CAST(:units AS jsonb), CAST(:types AS jsonb))"),
            {"u": u, "p": hash_password(password), "f": full_name,
             "e": (email or "").strip() or None, "r": role,
             "perms": json.dumps(clean_caps(permissions)), "units": json.dumps(units),
             "types": json.dumps(types)},
        )
    created = get_user(u)
    audit_repo.log("user", "create", u, after=created, note=f"Vai trò: {role}")
    return created  # type: ignore[return-value]


def update_user(username: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Cập nhật full_name/role/is_active/permissions/member_units/entry_types.

    Chặn khoá/hạ quyền admin cuối cùng; member phải còn ≥1 loại nhập liệu (ValueError)."""
    allowed = {k: v for k, v in fields.items() if k in ("full_name", "email", "role", "is_active")}
    if "email" in allowed:
        allowed["email"] = (allowed["email"] or "").strip() or None
    has_perms = "permissions" in fields
    ensure_schema()
    before = get_user(username)
    with session_scope() as db:
        cur = db.execute(
            text("SELECT role, is_active, member_units, entry_types FROM app_user WHERE username = :u"),
            {"u": username},
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
        # member_units chỉ gắn cho vai trò gắn đơn vị (member/leader); role khác → xoá gắn cũ.
        final_role = allowed.get("role", cur["role"])
        if final_role in UNIT_ROLES:
            raw = fields.get("member_units", list(cur["member_units"] or []))
            member_units = _clean_units(raw)
            if not member_units:
                raise ValueError("Tài khoản gắn đơn vị thành viên phải chọn ít nhất một đơn vị.")
        else:
            member_units = []
        sets.append("member_units = CAST(:member_units AS jsonb)")
        params["member_units"] = json.dumps(member_units)
        # Loại nhập liệu: gửi kèm → thay hẳn; không gửi → giữ loại của tài khoản member đang có.
        keep = cur["entry_types"] if cur["role"] == "member" else None
        sets.append("entry_types = CAST(:entry_types AS jsonb)")
        params["entry_types"] = json.dumps(_entry_types_for(final_role, fields.get("entry_types"), keep))
        if sets:
            db.execute(text(f"UPDATE app_user SET {', '.join(sets)} WHERE username = :u"), params)
    after = get_user(username)
    audit_repo.log("user", "update", username, before=before, after=after)
    return after


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
        before = _norm(db.execute(
            text(f"SELECT {_USER_COLS} FROM app_user WHERE username = :u"),
            {"u": username}).mappings().first())
        db.execute(text("DELETE FROM app_user WHERE username = :u"), {"u": username})
        # Username = email nên có thể được cấp lại cho NGƯỜI KHÁC: dọn trình duyệt nhận push + dấu
        # "đã đọc" của chủ cũ, kẻo máy chủ cũ nhận thông báo của chủ mới.
        for table in ("push_subscription", "support_read"):
            db.execute(text(f"DELETE FROM {table} WHERE username = :u"), {"u": username})
    audit_repo.log("user", "delete", username, before=before)
    return True


def update_profile(username: str, full_name: str | None) -> dict[str, Any] | None:
    """User tự cập nhật hồ sơ (chỉ họ tên)."""
    ensure_schema()
    before = get_user(username)
    with session_scope() as db:
        res = db.execute(
            text("UPDATE app_user SET full_name = :f WHERE username = :u"),
            {"f": full_name, "u": username},
        )
        if res.rowcount == 0:
            return None
    after = get_user(username)
    audit_repo.log("user", "update", username, before=before, after=after,
                   note="Tự cập nhật hồ sơ")
    return after


def set_password(username: str, new_password: str) -> bool:
    """Admin đặt lại mật khẩu cho user (không cần mật khẩu cũ)."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(
            text("UPDATE app_user SET password_hash = :p WHERE username = :u"),
            {"p": hash_password(new_password), "u": username},
        )
        changed = res.rowcount > 0
    if changed:  # chỉ ghi SỰ KIỆN, tuyệt đối không ghi mật khẩu
        audit_repo.log("user", "update", username, note="Quản trị đặt lại mật khẩu")
    return changed


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
    audit_repo.log("user", "update", username, note="Người dùng tự đổi mật khẩu")
    return True


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    """Trả thông tin user nếu đúng mật khẩu + còn active, ngược lại None."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text(f"SELECT {_USER_COLS}, password_hash FROM app_user WHERE username = :u"),
            {"u": username},
        ).mappings().first()
    if not row or not row["is_active"] or not verify_password(password, row["password_hash"]):
        return None
    return {k: v for k, v in _norm(row).items() if k != "password_hash"}
