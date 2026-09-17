"""Cửa sổ nhập liệu: chỉ được nhập/sửa số liệu trong N ngày gần nhất; cũ hơn = chỉ xem.

Hai thông số ĐỘC LẬP (admin cấu hình ở app_config, đổi riêng từng cái):
- MEMBER_EDIT_WINDOW_DAYS → tài khoản đơn vị thành viên: Thu mua · Tồn kho · Giá mủ · Nhu cầu
  thị trường (`/api/member/*`) và NGÀY GIAO của hợp đồng/đợt giao (`/api/sales-contracts`, kể cả
  lần giao ghi kèm khi bấm Hoàn thành)
- EDITOR_EDIT_WINDOW_DAYS → chuyên viên nhập liệu (Giá mủ nguyên liệu · Physical · Tồn kho · Báo giá)
Mặc định 7 ngày cho cả hai. N = số ngày LÙI được phép tính từ hôm nay: 0 = chỉ hôm nay, 1 = hôm
nay và hôm qua. Admin KHÔNG bị giới hạn (xem `security.assert_editor_window`).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_WINDOW_DAYS = 7
MEMBER_KEY = "MEMBER_EDIT_WINDOW_DAYS"
EDITOR_KEY = "EDITOR_EDIT_WINDOW_DAYS"

#: Bảng nhắc việc của đơn vị rà bao nhiêu ngày gần nhất (TÍNH CẢ HÔM NAY) — độc lập với cửa sổ
#: sửa ở trên: rà xa hơn để đơn vị biết mình còn nợ, kể cả ngày đã khoá (nhờ Ban TTKD nhập hộ).
ALERT_KEY = "MEMBER_ALERT_DAYS"
DEFAULT_ALERT_DAYS = 14

#: Header đánh dấu 403 do HÀNG RÀO THỜI GIAN (web đọc để mời đơn vị gửi «Đề nghị sửa»).
#: `detail` giữ nguyên câu cũ — nhiều màn và test đang đọc chuỗi đó.
BLOCK_HEADER = "X-Edit-Blocked"


def today() -> date:
    return datetime.now(_TZ).date()


def _parse(raw: str | None, default: int = DEFAULT_WINDOW_DAYS) -> int:
    """Chuỗi cấu hình → số ngày (≥0). Rỗng/không hợp lệ/số âm → mặc định."""
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return n if n >= 0 else default


def window_days(key: str) -> int:
    from app.services import config_repo

    return _parse(config_repo.get_value(key))


def member_window() -> int:
    return window_days(MEMBER_KEY)


def editor_window() -> int:
    return window_days(EDITOR_KEY)


def alert_days() -> int:
    """Số ngày bảng nhắc việc rà lại. **0 = TẮT cảnh báo** (số âm coi như chưa cấu hình)."""
    from app.services import config_repo

    return _parse(config_repo.get_value(ALERT_KEY), DEFAULT_ALERT_DAYS)


def window_phrase(window: int) -> str:
    """N ngày lùi → cụm từ người dùng đọc không nhầm: 0 → "hôm nay", 7 → "hôm nay và 7 ngày trước".

    Không viết "trong N ngày gần nhất": đặt 0 thì câu thành "trong 0 ngày" vô nghĩa, còn đặt 1 thì
    người đọc hiểu là chỉ hôm nay trong khi thực tế được sửa cả hôm qua.
    """
    return "hôm nay" if window <= 0 else f"hôm nay và {window} ngày trước"


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
            f"Ngày này đã chuyển sang chế độ chỉ xem — chỉ được nhập/sửa {window_phrase(window)}.",
            headers={BLOCK_HEADER: "window"},
        )
