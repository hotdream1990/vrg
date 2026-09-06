"""Router quản trị người dùng (app_user) — chỉ admin (gắn require_admin ở main)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import UNIT_ROLES, get_current_user
from app.schemas.auth import PasswordReset, UserCreate, UserOut, UserUpdate
from app.services import user_repo

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users():
    """Danh sách tất cả tài khoản."""
    return [UserOut(**u) for u in user_repo.list_users()]


@router.post("", response_model=UserOut)
def create_user(body: UserCreate):
    """Tạo tài khoản mới."""
    if body.role in UNIT_ROLES and not [u for u in body.member_units if (u or "").strip()]:
        raise HTTPException(400, "Tài khoản gắn đơn vị thành viên phải chọn ít nhất một đơn vị.")
    try:
        user = user_repo.create_user(body.username, body.password, body.full_name, body.role,
                                     body.permissions, body.member_units, body.email)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return UserOut(**user)


@router.put("/{username}", response_model=UserOut)
def update_user(username: str, body: UserUpdate, current: str = Depends(get_current_user)):
    """Cập nhật họ tên / vai trò / trạng thái của một tài khoản."""
    if username == current and body.is_active is False:
        raise HTTPException(400, "Không thể tự khoá tài khoản của bạn")
    try:
        user = user_repo.update_user(username, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not user:
        raise HTTPException(404, f"Không có tài khoản '{username}'")
    return UserOut(**user)


@router.post("/{username}/reset-password")
def reset_password(username: str, body: PasswordReset):
    """Đặt lại mật khẩu cho một tài khoản (không cần mật khẩu cũ)."""
    if not user_repo.set_password(username, body.new_password):
        raise HTTPException(404, f"Không có tài khoản '{username}'")
    return {"detail": "Đã đặt lại mật khẩu"}


@router.delete("/{username}")
def delete_user(username: str, current: str = Depends(get_current_user)):
    """Xoá một tài khoản."""
    if username == current:
        raise HTTPException(400, "Không thể tự xoá tài khoản của bạn")
    try:
        ok = user_repo.delete_user(username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, f"Không có tài khoản '{username}'")
    return {"detail": "Đã xoá tài khoản"}
