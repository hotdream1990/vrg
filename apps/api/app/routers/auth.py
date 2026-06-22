"""Router đăng nhập — JWT login + thông tin user hiện tại."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import create_access_token, get_current_user
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    TokenResponse,
    UserOut,
)
from app.services import user_repo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Đăng nhập bằng username/password → trả JWT + thông tin user."""
    user = user_repo.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Sai tài khoản hoặc mật khẩu")
    return TokenResponse(access_token=create_access_token(user["username"]), user=UserOut(**user))


@router.get("/me", response_model=UserOut)
def me(username: str = Depends(get_current_user)):
    """Thông tin user của token hiện tại."""
    user = user_repo.get_user(username)
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Tài khoản không tồn tại hoặc đã bị khoá")
    return UserOut(**user)


@router.put("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, username: str = Depends(get_current_user)):
    """User tự cập nhật hồ sơ (họ tên)."""
    user = user_repo.update_profile(username, body.full_name)
    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    return UserOut(**user)


@router.post("/change-password")
def change_password(body: PasswordChange, username: str = Depends(get_current_user)):
    """User tự đổi mật khẩu (cần mật khẩu hiện tại)."""
    try:
        ok = user_repo.change_password(username, body.old_password, body.new_password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    return {"detail": "Đã đổi mật khẩu"}
