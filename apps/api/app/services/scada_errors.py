"""Quy lỗi pymssql của SCADA về câu tiếng Việt đọc được (tách khỏi `scada_client` — phần I/O).

Câu trả ra gồm lý do đoán được (mạng? tài khoản? database? linked server? tag?) + thông điệp gốc
đã decode, KHÔNG BAO GIỜ chứa mật khẩu.
"""

from __future__ import annotations

import re

_UNREACHABLE = ("unable to connect", "server is unavailable", "connection refused",
                "no route to host", "name or service not known", "unknown host",
                "connection timed out", "timed out")
#: Dòng chung chung của DB-Lib, không nói thêm gì — bỏ cho thông điệp gốc gọn.
_NOISE = ("general sql server error: check messages from the sql server",)


class ScadaError(Exception):
    """Lỗi đọc SCADA — `str(exc)` là câu hiển thị thẳng cho người dùng."""


def _raw_message(exc: BaseException) -> tuple[int | None, str]:
    """(mã lỗi, thông điệp đã decode · bỏ dòng trùng/nhiễu).

    pymssql gói lỗi thành MỘT tuple `((mã, b"thông điệp"),)` → phải mở lớp ngoài trước.
    """
    args = exc.args[0] if len(exc.args) == 1 and isinstance(exc.args[0], tuple) else exc.args
    code: int | None = None
    parts: list[str] = []
    for arg in args:
        if isinstance(arg, int) and not isinstance(arg, bool) and code is None:
            code = arg
        elif isinstance(arg, (bytes, bytearray)):
            parts.append(bytes(arg).decode("utf-8", "replace"))
        else:
            parts.append(str(arg))
    lines: list[str] = []
    for line in "\n".join(parts).splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line and line not in lines and line.lower() not in _NOISE:
            lines.append(line)
    return code, " | ".join(lines)


def friendly_error(exc: BaseException, factory: dict, *, connected: bool,
                   server_msgs: list[str] | None = None) -> str:
    """Quy lỗi pymssql về câu tiếng Việt + thông điệp gốc (cắt ngắn; lặp mật khẩu thì bỏ chi tiết).

    ⚠ Ưu tiên CHỮ trong thông điệp hơn MÃ LỖI: pymssql giữ mã của lần lỗi TRƯỚC trong cùng tiến
    trình (đo thật 30/09/2026: "Connection refused" vẫn mang mã 18456 của lần sai mật khẩu trước).
    `server_msgs` = mọi thông điệp server gửi trong lần chạy (xem `_connect`) — đặt TRƯỚC vì exception
    chỉ giữ câu CUỐI, thường là câu chung chung "Statement(s) could not be prepared".
    """
    code, raw = _raw_message(exc)
    extra = [m for m in (server_msgs or []) if m and m not in raw]
    raw = " | ".join([*extra, raw] if raw else extra)
    password = str(factory.get("password") or "")
    low = raw.lower()
    where = f"{factory.get('host')}:{factory.get('port')}"
    unreachable = not connected and any(k in low for k in _UNREACHABLE)
    # Sai database: SQL Server gửi KÈM "Login failed" → phải xét trước nhánh sai mật khẩu.
    if "cannot open database" in low or code == 4060:
        head = f"Không mở được database «{factory.get('database_name')}» — kiểm tra tên/quyền truy cập"
    elif "login failed" in low or (not connected and code == 18456 and not unreachable):
        head = f"Sai tài khoản hoặc mật khẩu SQL Server (tài khoản «{factory.get('username')}»)"
    elif unreachable or (not connected and code == 20009):
        head = (f"Không kết nối được tới máy chủ {where} (kiểm tra mạng/VPN/tường lửa, "
                "SQL Server đã bật TCP/IP chưa)")
    elif "could not find server" in low or code == 7202:
        head = (f"Không tìm thấy linked server «{factory.get('linked_server')}» trên SQL Server "
                "(Historian thường đặt tên INSQL)")
    elif "invalid column name" in low:
        head = "Tag không tồn tại trong Historian — kiểm tra lại tên tag đã khai"
    elif "timed out" in low or code == 20003:
        head = "Truy vấn SCADA quá thời gian chờ — thử lại với kỳ ngắn hơn"
    else:
        head = "Lỗi khi đọc SQL Server của SCADA"
    # Thông điệp gốc có lặp lại mật khẩu → bỏ HẲN phần chi tiết. Không thay bằng *** vì *** cũng
    # lộ mật khẩu yếu (mật khẩu "able" biến "Unable" thành "Un***" — nhìn là đoán ra).
    if not raw or (password and password.lower() in low):
        return head
    return f"{head}. Chi tiết: {raw[:400]}"
