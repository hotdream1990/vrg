"""Đồng hồ giả + cấu hình cửa sổ tường minh cho test (không phải file test — không có tiền tố `test_`).

Từ 24/09/2026 hạn nhập tính tới GIỜ CHỐT (mặc định 11:00) của ngày D + N, nên kết quả một test đặt
cửa sổ 0 phụ thuộc giờ chạy: 9h thì hôm nay còn nhập được, 14h thì đã khoá. Test nào cần "hôm nay
còn mở" phải ghim đồng hồ, nếu không sẽ xanh buổi sáng, đỏ buổi chiều.

Test ghi số liệu "hôm qua"/"hôm nay" qua tài khoản đơn vị/chuyên viên cũng phụ thuộc N và giờ chốt
ĐANG LƯU trong DB (bản sao prod có thể là N = 0) → đặt tường minh bằng `window_config()`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.core import edit_window

VN = ZoneInfo("Asia/Ho_Chi_Minh")
MORNING = 9   # trước giờ chốt mặc định 11:00


def pin_clock(monkeypatch, hour: int = MORNING, minute: int = 0, day: date | None = None) -> datetime:
    """Ghim `edit_window.now()` (và kéo theo `today()`) vào `hour:minute` giờ VN của `day` (mặc định hôm nay)."""
    d = day or edit_window.now().date()
    fixed = datetime.combine(d, time(hour, minute), VN)
    monkeypatch.setattr(edit_window, "now", lambda: fixed)
    return fixed


_KEYS = (edit_window.MEMBER_KEY, edit_window.EDITOR_KEY, edit_window.CUTOFF_KEY)


@contextmanager
def restored_window_config() -> Iterator[None]:
    """Chụp N (đơn vị · chuyên viên) + giờ chốt đang lưu, trả lại nguyên trạng khi ra (kể cả khi lỗi)."""
    from app.services import config_repo

    before = {k: config_repo.get_value(k) for k in _KEYS}
    try:
        yield
    finally:
        config_repo.set_config({k: v or "__CLEAR__" for k, v in before.items()}, "test")


@contextmanager
def window_config(member: int = edit_window.DEFAULT_WINDOW_DAYS,
                  editor: int = edit_window.DEFAULT_WINDOW_DAYS,
                  hour: int = edit_window.DEFAULT_CUTOFF_HOUR) -> Iterator[None]:
    """Đặt TƯỜNG MINH N + giờ chốt trong app_config (không phụ thuộc DB đang cấu hình gì), trả lại khi ra.

    Mặc định N = 7: số liệu "hôm qua" còn hạn ở MỌI giờ chạy — test không nhắm cửa sổ thì dùng thế này.
    """
    from app.services import config_repo

    with restored_window_config():
        config_repo.set_config({edit_window.MEMBER_KEY: str(member), edit_window.EDITOR_KEY: str(editor),
                                edit_window.CUTOFF_KEY: str(hour)}, "test")
        yield
