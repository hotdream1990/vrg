"""Bảo mật: hash mật khẩu (bcrypt) + JWT (pyjwt) + dependency get_current_user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)
_ALGO = "HS256"
_BCRYPT_MAX = 72  # bcrypt giới hạn 72 bytes


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


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


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
