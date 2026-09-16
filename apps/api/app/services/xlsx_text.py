"""Chống "Excel formula injection" khi xuất file.

Excel/LibreOffice coi ô bắt đầu bằng `=`, `+`, `-`, `@` (hoặc tab/xuống dòng) là CÔNG THỨC và chạy
nó khi người nhận mở file. Trong hệ thống có những chuỗi do người ngoài gõ vào rồi lọt xuống file
Excel của quản trị — rõ nhất là ô "Tài khoản" của một lần ĐĂNG NHẬP SAI: ai cũng gọi được
`/api/auth/login` với tên tài khoản bất kỳ mà không cần mật khẩu đúng.

Cách chặn theo chuẩn OWASP: thêm dấu nháy đơn ở đầu → Excel hiển thị đúng chữ, thôi coi là công thức.
"""

from __future__ import annotations

from typing import Any

#: Ký tự mở đầu khiến Excel hiểu ô là công thức.
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> Any:
    """Giá trị cho ô Excel — chuỗi có nguy cơ thành công thức thì thêm nháy đơn ở đầu.

    Số/ngày/None giữ nguyên kiểu (còn tính toán, sắp xếp được trong Excel).
    """
    if not isinstance(value, str) or not value:
        return value
    return f"'{value}" if value.startswith(_FORMULA_STARTS) else value
