"""Lãnh đạo Tập đoàn (role=executive) — CHỈ XEM trên toàn hệ thống.

Chặn ở MỘT dependency toàn cục (gắn vào `FastAPI(dependencies=...)`) theo method HTTP, thay vì
trông vào từng endpoint: hệ thống có hơn 100 endpoint ghi, rải rác các kiểu gác khác nhau
(`require_editor`, `require_cap_edit`, gác trong handler…). Chỉ cần một chỗ quên là lãnh đạo sửa
được số liệu; endpoint thêm sau này cũng tự được bảo vệ.

Ngoại lệ là vài thao tác "gửi đi" nhưng không ghi số liệu nghiệp vụ: hồ sơ cá nhân, đổi mật khẩu,
hỏi Trợ lý AI, bấm AI nhận định ở Bản tin biến động (bấm-tạo, không lưu), xuất PDF báo cáo tuần.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import _active_user, _bearer, decode_token

EXECUTIVE_ROLE = "executive"

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: (method, đường dẫn route) lãnh đạo Tập đoàn vẫn được gọi dù không phải method đọc.
EXECUTIVE_WRITE_ALLOW = frozenset({
    ("PUT", "/api/auth/me"),
    ("POST", "/api/auth/change-password"),
    ("POST", "/api/assistant/chat"),
    ("POST", "/api/market-movement/assessment"),
    ("POST", "/api/weekly-reports/{week_key}/generate-pdf"),
})


def block_executive_writes(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """403 nếu tài khoản Lãnh đạo Tập đoàn gọi method ghi ngoài danh sách cho phép.

    Không có token / token công khai / token sai → bỏ qua, để dependency của chính endpoint quyết
    định (401 hoặc mở). Chỉ tra DB khi là method ghi, nên không tốn gì cho các lượt đọc.
    """
    method = request.method.upper()
    if method in _READ_METHODS or not creds:
        return
    username = decode_token(creds.credentials)
    if not username:
        return
    route = request.scope.get("route")
    path = getattr(route, "path", None) or request.url.path
    if (method, path) in EXECUTIVE_WRITE_ALLOW:
        return
    if _active_user(username).get("role") == EXECUTIVE_ROLE:
        raise HTTPException(403, "Tài khoản Lãnh đạo Tập đoàn chỉ được XEM — việc nhập/sửa số liệu "
                                 "do chuyên viên thực hiện.")
