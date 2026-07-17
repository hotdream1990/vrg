"""Cửa sổ nhập liệu: chỉ được nhập/sửa số liệu trong N ngày gần nhất; cũ hơn = chỉ xem.

Hai thông số ĐỘC LẬP (admin cấu hình ở app_config, đổi riêng từng cái):
- MEMBER_EDIT_WINDOW_DAYS → tài khoản đơn vị thành viên (trang Giá mủ đơn vị)
- EDITOR_EDIT_WINDOW_DAYS → chuyên viên nhập liệu (Giá mủ nguyên liệu · Physical · Tồn kho · Báo giá)
Mặc định 7 ngày cho cả hai. Admin KHÔNG bị giới hạn (xem `security.assert_editor_window`).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_WINDOW_DAYS = 7
MEMBER_KEY = "MEMBER_EDIT_WINDOW_DAYS"
EDITOR_KEY = "EDITOR_EDIT_WINDOW_DAYS"


def today() -> date:
    return datetime.now(_TZ).date()


def _parse(raw: str | None) -> int:
    """Chuỗi cấu hình → số ngày (≥0). Rỗng/không hợp lệ → mặc định."""
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_WINDOW_DAYS
    return n if n >= 0 else DEFAULT_WINDOW_DAYS


def window_days(key: str) -> int:
    from app.services import config_repo

    return _parse(config_repo.get_value(key))


def member_window() -> int:
    return window_days(MEMBER_KEY)


def editor_window() -> int:
    return window_days(EDITOR_KEY)


def assert_editable(as_of: str | date, window: int) -> None:
    """403/400 nếu ngày ngoài cửa sổ cho phép (server ép — hàng rào thật, không chỉ ẩn UI).

    `as_of` nhận cả chuỗi 'YYYY-MM-DD' lẫn `date` (một số schema parse sẵn thành date).
    """
    if isinstance(as_of, date):
        d = as_of
    else:
        try:
            d = date.fromisoformat(str(as_of))
        except ValueError as exc:
            raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    t = today()
    if d > t:
        raise HTTPException(400, "Không nhập số liệu cho ngày trong tương lai.")
    if (t - d).days > window:
        raise HTTPException(
            403,
            f"Ngày này đã chuyển sang chế độ chỉ xem — chỉ được nhập/sửa trong {window} ngày gần nhất.",
        )


def assert_week_editable(week_key: str | date, window: int) -> None:
    """Cửa sổ sửa cho DỮ LIỆU TUẦN: được sửa tuần hiện tại + `window` ngày sau khi tuần kết thúc.

    `week_key` = ngày Thứ 2 (ISO) của tuần. Tuần tương lai bị chặn; tuần đã qua chỉ sửa được trong
    `window` ngày kể từ Chủ nhật của tuần đó (mặc định 7 = còn sửa hết tuần kế tiếp).
    """
    if isinstance(week_key, date):
        mon = week_key
    else:
        try:
            mon = date.fromisoformat(str(week_key))
        except ValueError as exc:
            raise HTTPException(400, "Tuần không hợp lệ (Thứ 2 ISO 'YYYY-MM-DD').") from exc
    t = today()
    t_mon = t - timedelta(days=t.weekday())
    if mon > t_mon:
        raise HTTPException(400, "Không nhập số liệu cho tuần trong tương lai.")
    sun = mon + timedelta(days=6)
    if (t - sun).days > window:
        raise HTTPException(
            403,
            f"Tuần này đã chuyển sang chế độ chỉ xem — chỉ được nhập/sửa tuần hiện tại và {window} ngày sau đó.",
        )
