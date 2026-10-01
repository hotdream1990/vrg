"""Schema đăng nhập / người dùng / hồ sơ."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    full_name: str | None = None
    email: str | None = None  # địa chỉ nhận thông báo (Hỗ trợ & Thông báo)
    role: str = "admin"
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list)  # quyền theo mục (editor)
    member_units: list[str] = Field(default_factory=list)  # đơn vị gắn với tài khoản (member/leader)
    # Loại nhập liệu của tài khoản member (purchase · stock · contract); vai trò khác luôn rỗng.
    entry_types: list[str] = Field(default_factory=list)
    # role=member: có ≥1 đơn vị được giao kế hoạch thu mua → mới hiện menu "Báo cáo thu mua".
    member_has_purchase_plan: bool = False
    impersonated_by: str | None = None  # username admin đang đăng nhập hộ (None = phiên bình thường)


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
    email: str | None = None
    role: str = "admin"
    permissions: list[str] = Field(default_factory=list)
    member_units: list[str] = Field(default_factory=list)  # bắt buộc ≥1 khi role=member/leader
    entry_types: list[str] | None = None  # role=member: None = đủ 3 loại; gửi thì phải ≥1 loại


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None
    member_units: list[str] | None = None
    entry_types: list[str] | None = None  # None/không gửi = giữ loại đang có


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6)


class ImpersonateRequest(BaseModel):
    username: str  # tài khoản đích muốn đăng nhập hộ
