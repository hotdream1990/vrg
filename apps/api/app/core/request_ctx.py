"""Ngữ cảnh request hiện tại (ai đang thao tác · IP) — phục vụ Nhật ký hoạt động.

Middleware ở `app/main.py` giải mã Bearer token rồi đặt actor + IP vào ContextVar; nhờ vậy
các hàm ghi dữ liệu ở tầng repo chỉ việc gọi `audit_repo.log(...)` mà KHÔNG phải đổi chữ ký
hàm và sửa toàn bộ router gọi tới.

Lưu ý kỹ thuật: ContextVar đặt trong MIDDLEWARE mới lan được tới handler (Starlette copy
context khi chạy handler sync trong threadpool). Đặt trong dependency thì KHÔNG lan ngược ra
— nên tuyệt đối không set ở dependency.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

SYSTEM_ACTOR = "system"          # máy chạy (scheduler/crawler) — không phải người dùng
PUBLIC_PREFIX = "public:"        # trang nhập giá công khai (không đăng nhập)

_actor: ContextVar[str] = ContextVar("audit_actor", default="")
_role: ContextVar[str] = ContextVar("audit_actor_role", default="")
_ip: ContextVar[str] = ContextVar("audit_ip", default="")
_on_behalf: ContextVar[str] = ContextVar("audit_on_behalf", default="")
_note: ContextVar[str] = ContextVar("audit_note", default="")
_paused: ContextVar[bool] = ContextVar("audit_paused", default=False)


def set_request(actor: str, ip: str, on_behalf: str = "") -> None:
    """Middleware gọi đầu mỗi request. actor rỗng = chưa đăng nhập/không xác định.

    `on_behalf` = admin đang đăng nhập hộ tài khoản `actor` (claim `imp_by` trong token).
    """
    _actor.set(actor or "")
    _role.set("")
    _ip.set(ip or "")
    _on_behalf.set(on_behalf or "")


def on_behalf() -> str:
    """Admin đang thao tác dưới danh nghĩa `actor()` (rỗng nếu là phiên bình thường)."""
    return _on_behalf.get()


def actor() -> str:
    """Người thao tác của request hiện tại; không có → 'system' (job tự chạy)."""
    return _actor.get() or SYSTEM_ACTOR


def client_ip() -> str:
    return _ip.get()


def cached_role() -> str:
    return _role.get()


def cache_role(role: str) -> None:
    """Nhớ vai trò đã tra trong request này (tránh truy vấn lại ở mỗi dòng nhật ký)."""
    _role.set(role or "")


@contextmanager
def use_actor(name: str) -> Iterator[None]:
    """Ép người thao tác trong 1 đoạn code (job nền, trang công khai)."""
    token = _actor.set(name)
    role_token = _role.set("")
    behalf_token = _on_behalf.set("")
    try:
        yield
    finally:
        _actor.reset(token)
        _role.reset(role_token)
        _on_behalf.reset(behalf_token)


@contextmanager
def use_note(text: str) -> Iterator[None]:
    """Gắn ghi chú mặc định cho mọi dòng nhật ký sinh ra trong đoạn code (vd 'Nhập từ file Excel')."""
    token = _note.set(text)
    try:
        yield
    finally:
        _note.reset(token)


def default_note() -> str:
    return _note.get()


@contextmanager
def paused() -> Iterator[None]:
    """Tạm tắt ghi nhật ký — dùng cho dữ liệu PHÁI SINH (mirror) để khỏi ghi trùng."""
    token = _paused.set(True)
    try:
        yield
    finally:
        _paused.reset(token)


def is_paused() -> bool:
    return _paused.get()
