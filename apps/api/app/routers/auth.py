"""Router đăng nhập — JWT login + thông tin user hiện tại + đăng nhập hộ (impersonation)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.security import (
    UNIT_ROLES,
    create_access_token,
    create_impersonation_token,
    get_current_user,
    get_impersonator,
    require_admin,
)
from app.schemas.auth import (
    ImpersonateRequest,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    TokenResponse,
    UserOut,
)
from app.services import access_repo, unit_daily_repo, user_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: dict, **extra) -> UserOut:
    """Bọc dict user → UserOut, kèm cờ `member_has_purchase_plan`.

    Tài khoản gắn đơn vị (nhập liệu + lãnh đạo) chỉ hiện menu "Thu mua" khi có ≥1 đơn vị ĐƯỢC
    GIAO KẾ HOẠCH thu mua — suy thẳng từ số ở màn "Kế hoạch năm" (chốt 03/08/2026, xem
    `companies_with_purchase_plan`).
    """
    has_plan = False
    if user.get("role") in UNIT_ROLES:
        plan_units = unit_daily_repo.companies_with_purchase_plan()
        has_plan = any(u in plan_units for u in user.get("member_units") or [])
    return UserOut(**user, member_has_purchase_plan=has_plan, **extra)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request):
    """Đăng nhập bằng username/password → trả JWT + thông tin user.

    Ghi cả lần đăng nhập HỎNG vào Lịch sử truy cập: quản trị cần thấy dấu hiệu dò mật khẩu và
    những người gõ sai nhiều lần (thường là quên, cần hỗ trợ).
    """
    user = user_repo.authenticate(body.username, body.password)
    agent = request.headers.get("user-agent", "")
    if not user:
        # Tra hồ sơ chỉ để GHI kèm vai trò/đơn vị (quản trị thấy ngay "lãnh đạo đơn vị X gõ sai"),
        # không đổi câu trả lời cho client — vẫn là "sai tài khoản hoặc mật khẩu".
        name = body.username.strip()[:120]
        access_repo.log_login(name, user_repo.get_user(name), ok=False, user_agent=agent)
        raise HTTPException(401, "Sai tài khoản hoặc mật khẩu")
    access_repo.log_login(user["username"], user, user_agent=agent)
    return TokenResponse(access_token=create_access_token(user["username"]), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(username: str = Depends(get_current_user), imp_by: str | None = Depends(get_impersonator)):
    """Thông tin user của token hiện tại (kèm `impersonated_by` nếu đang trong phiên đăng nhập hộ)."""
    user = user_repo.get_user(username)
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Tài khoản không tồn tại hoặc đã bị khoá")
    return _user_out(user, impersonated_by=imp_by)


@router.post("/impersonate", response_model=TokenResponse)
def impersonate(
    body: ImpersonateRequest,
    admin_username: str = Depends(require_admin),
    imp_by: str | None = Depends(get_impersonator),
):
    """Admin đăng nhập hộ (mạo danh) một tài khoản khác → trả token của tài khoản đích.

    Ràng buộc an toàn: không tự mạo danh chính mình; không mạo danh tài khoản không tồn tại/đã
    khoá; token ĐANG mạo danh không được mạo danh tiếp (chặn lồng nhau).
    """
    if imp_by:
        raise HTTPException(403, "Đang trong phiên đăng nhập hộ — không thể mạo danh tiếp")
    target_username = body.username.strip()
    if target_username == admin_username:
        raise HTTPException(400, "Không thể đăng nhập hộ chính tài khoản của bạn")
    target = user_repo.get_user(target_username)
    if not target:
        raise HTTPException(404, f"Không có tài khoản '{target_username}'")
    if not target.get("is_active", True):
        raise HTTPException(400, "Tài khoản đã bị khoá — không thể đăng nhập hộ")
    logger.info("Admin '%s' bắt đầu đăng nhập hộ tài khoản '%s'", admin_username, target_username)
    token = create_impersonation_token(target["username"], admin_username)
    return TokenResponse(access_token=token, user=_user_out(target, impersonated_by=admin_username))


@router.put("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, username: str = Depends(get_current_user)):
    """User tự cập nhật hồ sơ (họ tên)."""
    user = user_repo.update_profile(username, body.full_name)
    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    return _user_out(user)


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
