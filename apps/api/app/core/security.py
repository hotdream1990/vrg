"""Bảo mật: hash mật khẩu (bcrypt) + JWT (pyjwt) + dependency get_current_user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
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


def assert_edit_window(username: str, as_of: str) -> None:
    """Cửa sổ sửa cho endpoint DÙNG CHUNG giữa đơn vị thành viên và chuyên viên.

    Mỗi vai trò một thông số riêng (admin cấu hình độc lập): đơn vị thành viên theo
    MEMBER_EDIT_WINDOW_DAYS, chuyên viên theo EDITOR_EDIT_WINDOW_DAYS, admin miễn. Dùng ở
    `/api/sales-contracts` — router đó phục vụ cả hai vai trò nên không thể chọn cứng một thông số.
    """
    from app.core import edit_window

    role = _active_user(username).get("role")
    if role == "admin":
        return
    window = edit_window.member_window() if role == "member" else edit_window.editor_window()
    edit_window.assert_editable(as_of, window)


def assert_not_data_locked(username: str, company: str | None, *dates,
                           safe_fields: str | None = None) -> None:
    """Hàng rào CHỐT SỐ LIỆU cho endpoint dùng chung giữa đơn vị thành viên và chuyên viên.

    Chỉ chặn tài khoản `member`: sau khi đơn vị chốt, chuyên viên/quản trị sửa hộ là đường DUY NHẤT
    để số liệu còn sửa được (đơn vị báo Ban TTKD). Xem `app/core/data_lock.py`.
    """
    from app.core import data_lock

    if not company or _active_user(username).get("role") != "member":
        return
    data_lock.assert_not_locked(company, *dates, safe_fields=safe_fields)


#: Các vai trò ĐƯỢC GÁN đơn vị thành viên (`member_units`) — cùng phạm vi dữ liệu, khác quyền ghi:
#: `member` nhập số liệu của đơn vị; `leader` (lãnh đạo đơn vị) CHỈ XEM số liệu của đơn vị mình
#: và dùng hộp thư Hỗ trợ & Thông báo (hộp thư thì ngược lại: chỉ lãnh đạo vào được).
UNIT_ROLES = {"member", "leader"}

#: Vai trò gắn đơn vị nhưng KHÔNG được ghi bất cứ thứ gì.
UNIT_VIEW_ROLES = {"leader"}

#: Method HTTP không làm thay đổi dữ liệu — lãnh đạo đơn vị chỉ đi được các method này.
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_unit_user(request: Request, username: str = Depends(get_current_user)) -> dict:
    """Dependency cho MỌI tài khoản gắn đơn vị (`member` nhập liệu · `leader` chỉ xem).

    Chặn ghi của lãnh đạo đơn vị ngay ở ĐÂY, theo method HTTP, thay vì gắn tay từng endpoint:
    router `/api/member` có hơn 20 endpoint, gắn tay là kiểu gì cũng sót một cái — và cái sót đó
    là một lỗ cho phép lãnh đạo sửa số liệu. Endpoint mới thêm sau này tự động được bảo vệ.
    """
    u = _active_user(username)
    role = u.get("role")
    if role not in UNIT_ROLES:
        raise HTTPException(403, "Chỉ dành cho tài khoản của đơn vị thành viên")
    if not (u.get("member_units") or []):
        raise HTTPException(403, "Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
    if role in UNIT_VIEW_ROLES and request.method.upper() not in _READ_METHODS:
        raise HTTPException(403, "Tài khoản lãnh đạo đơn vị chỉ được XEM số liệu — "
                                 "việc nhập/sửa do tài khoản nhập liệu của đơn vị thực hiện.")
    return u


def block_unit_roles(username: str = Depends(get_current_user)) -> str:
    """Chặn tài khoản GẮN ĐƠN VỊ khỏi các endpoint số liệu MỨC TẬP ĐOÀN (vd `/api/series`).

    Những endpoint đó trả số liệu gộp và có kiểu chia theo TỪNG ĐƠN VỊ, tức đơn vị này đọc được
    số của đơn vị kia. Chúng chỉ phục vụ Dashboard và Bản tin biến động — hai màn mà tài khoản
    đơn vị không có trong menu — nên chặn hẳn ở tầng API, đừng dựa vào việc "menu không có link".
    """
    if _active_user(username).get("role") in UNIT_ROLES:
        raise HTTPException(403, "Số liệu mức Tập đoàn — tài khoản đơn vị chỉ xem số liệu "
                                 "của đơn vị mình.")
    return username


def get_current_leader(username: str = Depends(get_current_user)) -> dict:
    """Dependency cho tài khoản LÃNH ĐẠO ĐƠN VỊ — trả user dict (có `member_units`).

    403 nếu không phải role=leader; 403 nếu chưa được gán đơn vị nào. Dùng cho phía đơn vị của
    hộp thư Hỗ trợ & Thông báo; mọi thao tác vẫn bị ép về đúng các đơn vị được gán.
    """
    u = _active_user(username)
    if u.get("role") != "leader":
        raise HTTPException(403, "Chỉ dành cho tài khoản lãnh đạo đơn vị thành viên")
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
      - tài khoản gắn đơn vị (`UNIT_ROLES`) → danh sách đơn vị ĐƯỢC GÁN (server tự ép phạm vi,
        không tin client gửi lên); riêng lãnh đạo đơn vị bị chặn ở mức Sửa — chỉ xem;
      - còn lại → `None` = mọi đơn vị, sau khi kiểm quyền `cap` ở mức `level`.
    Nhờ vậy phần Hợp đồng & Khách hàng chỉ có MỘT bộ endpoint thay vì nhân đôi /api/member/*.
    """
    def dep(username: str = Depends(get_current_user)) -> tuple[str, list[str] | None]:
        u = _active_user(username)
        if u.get("role") in UNIT_ROLES:
            # Lãnh đạo đơn vị CHỈ XEM: mọi endpoint đòi mức Sửa đều chặn ngay tại đây.
            if u.get("role") in UNIT_VIEW_ROLES and level == LEVEL_EDIT:
                raise HTTPException(403, "Tài khoản lãnh đạo đơn vị chỉ được XEM số liệu — "
                                         "việc nhập/sửa do tài khoản nhập liệu của đơn vị thực hiện.")
            units = list(u.get("member_units") or [])
            if not units:
                raise HTTPException(403, "Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
            # Nhận sáp nhập là nhận cả phần việc dở dang của đơn vị cũ: hợp đồng chưa giao hết,
            # khách hàng của những hợp đồng đó. Không mở phạm vi thì 3 hợp đồng dở dang của đơn vị
            # cũ không ai thấy để thêm đợt giao (phát hiện 27/08/2026). Ghi vẫn bị các hàng rào cũ
            # chặn: không ký hợp đồng MỚI ở đơn vị đã sáp nhập, không ghi số liệu từ ngày hiệu lực.
            from app.services import member_unit_merge

            return username, member_unit_merge.expand(units) or units
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
