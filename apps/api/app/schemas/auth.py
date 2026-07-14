"""Schema đăng nhập / người dùng / hồ sơ."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    full_name: str | None = None
    role: str = "admin"
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list)  # quyền theo mục (editor)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Tự phục vụ (user hiện tại) ---
class ProfileUpdate(BaseModel):
    full_name: str | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


# --- Quản trị người dùng (admin) ---
class UserCreate(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    full_name: str | None = None
    role: str = "admin"
    permissions: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6)
