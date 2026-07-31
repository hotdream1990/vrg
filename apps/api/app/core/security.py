"""Bảo mật: hash mật khẩu (bcrypt) + JWT (pyjwt) + dependency get_current_user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.permissions import LEVEL_EDIT, LEVEL_VIEW, effective_caps, has_cap

_bearer = HTTPBearer(auto_error=False)
_ALGO = "HS256"
_BCRYPT_MAX = 72  # bcrypt giới hạn 72 bytes
_IMPERSONATE_MINUTES = 60  # token đăng nhập hộ hết hạn nhanh hơn token thường


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:_BCRYPT_MAX], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:_BCRYPT_MAX], password_hash.encode())
    except Exception:  # noqa: BLE001
        return False


def create_access_token(sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": sub, "exp": exp}, settings.jwt_secret, algorithm=_ALGO)


def _decode_payload(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None


def decode_token(token: str) -> str | None:
    payload = _decode_payload(token)
    return payload.get("sub") if payload else None


def decode_bearer(header: str | None) -> tuple[str, str]:
    """Header `Authorization` → (username, admin-đăng-nhập-hộ). Rỗng nếu thiếu/sai/token công khai.

    Dùng cho middleware Nhật ký hoạt động: chỉ giải mã, KHÔNG kiểm tra quyền (việc đó là của
    dependency ở từng endpoint) và không truy vấn DB.
    """
    if not header or not header.lower().startswith("bearer "):
        return "", ""
    payload = _decode_payload(header[7:].strip())
    if not payload:
        return "", ""
    return str(payload.get("sub") or ""), str(payload.get("imp_by") or "")


def create_impersonation_token(target_username: str, admin_username: str) -> str:
    """Token đăng nhập hộ: `sub`=user đích (để get_current_user dùng bình thường) +
    `imp_by`=admin đã mạo danh (để /me báo hiệu + chặn mạo danh lồng nhau). Hạn ngắn hơn token thường."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=_IMPERSONATE_MINUTES)
    return jwt.encode(
        {"sub": target_username, "imp_by": admin_username, "exp": exp},
        settings.jwt_secret, algorithm=_ALGO,
    )


def get_impersonator(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str | None:
    """Username admin đang mạo danh nếu token hiện tại là token mạo danh (claim `imp_by`), ngược lại None."""
    if not creds:
        return None
    payload = _decode_payload(creds.credentials)
    return payload.get("imp_by") if payload else None


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Dependency bảo vệ route — trả username từ Bearer token, 401 nếu thiếu/sai/hết hạn."""
    unauth = HTTPException(401, "Chưa đăng nhập hoặc phiên đã hết hạn",
                           headers={"WWW-Authenticate": "Bearer"})
    if not creds:
        raise unauth
    sub = decode_token(creds.credentials)
    if not sub:
        raise unauth
    return sub


EDITOR_ROLES = {"admin", "editor"}  # được nhập/sửa số liệu


def _active_user(username: str) -> dict:
    """Tải user còn active từ token, 401 nếu không tồn tại/đã khoá."""
    from app.services import user_repo  # lazy: tránh import vòng với security

    user = user_repo.get_user(username)
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Tài khoản không tồn tại hoặc đã bị khoá",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(username: str = Depends(get_current_user)) -> str:
    """Dependency chỉ cho phép role=admin còn active (403 nếu không)."""
    if _active_user(username).get("role") != "admin":
        raise HTTPException(403, "Bạn không có quyền quản trị")
    return username


def require_editor(username: str = Depends(get_current_user)) -> str:
    """Dependency cho phép nhập/sửa số liệu: role admin hoặc editor (viewer bị chặn 403)."""
    if _active_user(username).get("role") not in EDITOR_ROLES:
        raise HTTPException(403, "Tài khoản chỉ có quyền xem — không được nhập/sửa số liệu")
    return username


def assert_editor_window(username: str, as_of: str) -> None:
    """Chuyên viên (editor) chỉ được ghi trong cửa sổ N ngày gần nhất; admin MIỄN (toàn quyền).

    Chỉ gọi trong handler đã gác cap → user chắc chắn là admin hoặc editor.
    """
    from app.core import edit_window

    if _active_user(username).get("role") == "admin":
        return
    edit_window.assert_editable(as_of, edit_window.editor_window())


def get_current_member(username: str = Depends(get_current_user)) -> dict:
    """Dependency cho tài khoản đơn vị thành viên — trả user dict (có `member_units`).

    403 nếu không phải role=member; 403 nếu chưa được gán đơn vị nào. Token member chỉ mở
    đúng các endpoint /api/member và chỉ với các đơn vị được gán — không đụng số liệu đơn vị
    khác hay mục nội bộ.
    """
    u = _active_user(username)
    if u.get("role") != "member":
        raise HTTPException(403, "Chỉ dành cho tài khoản đơn vị thành viên")
    if not (u.get("member_units") or []):
        raise HTTPException(403, "Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
    return u


# ── Phân quyền theo mục dữ liệu (chuyên viên nhập liệu) ──
# Hai cấp: Xem (`require_cap`) và Sửa (`require_cap_edit`) — xem app/core/permissions.py.
_NO_VIEW = HTTPException(403, "Bạn không được phân quyền với mục dữ liệu này")
_NO_EDIT = HTTPException(403, "Bạn chỉ có quyền xem mục dữ liệu này — không được nhập/sửa")


def user_caps(username: str) -> dict[str, str]:
    """Quyền THỰC của tài khoản dạng `{key: level}` (admin=tất cả mức Sửa, viewer=rỗng)."""
    u = _active_user(username)
    return effective_caps(u.get("role", ""), u.get("permissions"))


def assert_cap(username: str, cap: str, level: str = LEVEL_VIEW) -> None:
    """Ném 403 nếu tài khoản chưa đạt mức quyền yêu cầu. Dùng trong handler (khi cap phụ thuộc payload)."""
    if not has_cap(user_caps(username), cap, level):
        raise _NO_EDIT if level == LEVEL_EDIT else _NO_VIEW


def require_cap(cap: str, level: str = LEVEL_VIEW):
    """Factory dependency: cho qua nếu tài khoản đạt mức `level` với quyền `cap` (mặc định: Xem)."""
    def dep(username: str = Depends(get_current_user)) -> str:
        assert_cap(username, cap, level)
        return username
    return dep


def require_cap_edit(cap: str):
    """Factory dependency cho endpoint GHI: bắt buộc mức Sửa (chỉ-Xem sẽ bị chặn 403)."""
    return require_cap(cap, LEVEL_EDIT)


def cap_or_member_scope(cap: str, level: str = LEVEL_VIEW):
    """Factory dependency cho màn hình dùng CHUNG giữa đơn vị thành viên và chuyên viên.

    Trả `(username, companies)`:
      - role=member  → danh sách đơn vị ĐƯỢC GÁN (server tự ép phạm vi, không tin client gửi lên);
      - còn lại      → `None` = mọi đơn vị, sau khi kiểm quyền `cap` ở mức `level`.
    Nhờ vậy phần Hợp đồng & Khách hàng chỉ có MỘT bộ endpoint thay vì nhân đôi /api/member/*.
    """
    def dep(username: str = Depends(get_current_user)) -> tuple[str, list[str] | None]:
        u = _active_user(username)
        if u.get("role") == "member":
            units = list(u.get("member_units") or [])
            if not units:
                raise HTTPException(403, "Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
            return username, units
        assert_cap(username, cap, level)
        return username, None
    return dep


def require_any_cap(*caps: str, level: str = LEVEL_VIEW):
    """Factory dependency: cho qua nếu đạt mức `level` với ÍT NHẤT MỘT quyền (vd Báo giá: market_quote|raw_material)."""
    def dep(username: str = Depends(get_current_user)) -> str:
        got = user_caps(username)
        if not any(has_cap(got, c, level) for c in caps):
            raise _NO_EDIT if level == LEVEL_EDIT else _NO_VIEW
        return username
    return dep


# ── Token cho link công khai (đơn vị thành viên nhập giá mủ) ──
# Dùng claim `scope` thay cho `sub` → get_current_user (đọc `sub`) TỪ CHỐI token này,
# nên token công khai KHÔNG dùng được cho bất kỳ endpoint nội bộ nào (chỉ mở đúng phần nhập giá).
_PUBLIC_SCOPE = "public-purchase"


def create_public_token(hours: int = 8) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=hours)
    return jwt.encode({"scope": _PUBLIC_SCOPE, "exp": exp}, settings.jwt_secret, algorithm=_ALGO)


def _valid_public_token(token: str) -> bool:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO]).get("scope") == _PUBLIC_SCOPE
    except jwt.PyJWTError:
        return False


def require_public(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    """Chỉ cho qua nếu có token công khai hợp lệ (đổi từ mật khẩu ở /auth)."""
    if not creds or not _valid_public_token(creds.credentials):
        raise HTTPException(401, "Phiên nhập giá đã hết hạn — vui lòng nhập lại mật khẩu",
                            headers={"WWW-Authenticate": "Bearer"})
