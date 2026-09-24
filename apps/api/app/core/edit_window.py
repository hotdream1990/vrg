"""Cửa sổ nhập liệu: số liệu ngày D chỉ được nhập/sửa đến GIỜ CHỐT của ngày D + N; sau đó = chỉ xem.

Hai thông số ĐỘC LẬP (admin cấu hình ở app_config, đổi riêng từng cái):
- MEMBER_EDIT_WINDOW_DAYS → tài khoản đơn vị thành viên: Thu mua · Tiêu thụ – Tồn kho · Giá mủ ·
  Nhu cầu thị trường (`/api/member/*`) và NGÀY GIAO của hợp đồng/đợt giao (`/api/sales-contracts`,
  kể cả lần giao ghi kèm khi bấm Hoàn thành)
- EDITOR_EDIT_WINDOW_DAYS → chuyên viên nhập liệu (Giá mủ nguyên liệu · Physical · Tồn kho · Báo giá)
Mặc định 7 ngày cho cả hai. Admin KHÔNG bị giới hạn (xem `security.assert_editor_window`).

LUẬT GIỜ CHỐT (chủ dự án chốt 24/09/2026, thay cho 2 ô "cộng thêm ngày" riêng của biểu Thu mua và
biểu Tồn kho): MỌI mục tính chung một mốc — **hạn = `EDIT_CUTOFF_HOUR` giờ (mặc định 11:00) của ngày
D + N**. Đặt 0 ⇒ số liệu hôm nay nhập đến 11:00 hôm nay; đặt 1 ⇒ nhập đến 11:00 hôm sau. Hệ quả: qua
giờ chốt mà N = 0 thì cả ngày hôm nay cũng đã khoá (`editable_from` > hôm nay).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_WINDOW_DAYS = 7
MEMBER_KEY = "MEMBER_EDIT_WINDOW_DAYS"
EDITOR_KEY = "EDITOR_EDIT_WINDOW_DAYS"

#: Giờ chốt (0–23, giờ Việt Nam) — hạn nhập của ngày D là giờ này của ngày D + N. Cùng mốc này
#: được job gửi cảnh báo tự động và job chụp số liệu tuần dùng lại, nên chỉ khai MỘT chỗ.
CUTOFF_KEY = "EDIT_CUTOFF_HOUR"
DEFAULT_CUTOFF_HOUR = 11

#: Bảng nhắc việc của đơn vị rà bao nhiêu ngày gần nhất (TÍNH CẢ HÔM NAY) — độc lập với cửa sổ
#: sửa ở trên: rà xa hơn để đơn vị biết mình còn nợ, kể cả ngày đã khoá (nhờ Ban TTKD nhập hộ).
ALERT_KEY = "MEMBER_ALERT_DAYS"
DEFAULT_ALERT_DAYS = 14

#: Trần của mọi ô "số ngày" (N, số ngày rà cảnh báo): admin gõ số rất lớn để hiểu là "không giới
#: hạn" thì `timedelta` tràn (OverflowError → 500 ở MỌI đường ghi). 3650 ≈ 10 năm, thừa cho mọi nhu cầu.
MAX_DAYS = 3650

#: Header đánh dấu 403 do HÀNG RÀO THỜI GIAN (web đọc để mời đơn vị gửi «Đề nghị sửa»).
#: `detail` giữ nguyên phần đầu câu cũ — nhiều màn và test đang đọc chuỗi đó.
BLOCK_HEADER = "X-Edit-Blocked"


def now() -> datetime:
    return datetime.now(_TZ)


def today() -> date:
    return now().date()


def _parse(raw: str | None, default: int = DEFAULT_WINDOW_DAYS) -> int:
    """Chuỗi cấu hình → số ngày (0…MAX_DAYS). Rỗng/không hợp lệ/số âm → mặc định; quá trần → trần."""
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return min(n, MAX_DAYS) if n >= 0 else default


def window_days(key: str) -> int:
    from app.services import config_repo

    return _parse(config_repo.get_value(key))


def member_window() -> int:
    return window_days(MEMBER_KEY)


def editor_window() -> int:
    return window_days(EDITOR_KEY)


def cutoff_hour() -> int:
    """Giờ chốt 0–23; rỗng/không hợp lệ/ngoài khoảng → 11."""
    from app.services import config_repo

    h = _parse(config_repo.get_value(CUTOFF_KEY), DEFAULT_CUTOFF_HOUR)
    return h if h <= 23 else DEFAULT_CUTOFF_HOUR


def deadline(as_of: date, window: int, hour: int | None = None) -> datetime:
    """Hạn chót nhập/sửa số liệu ngày `as_of`: `hour` giờ (mặc định giờ chốt) của ngày as_of + window."""
    h = cutoff_hour() if hour is None else hour
    return datetime.combine(as_of + timedelta(days=window), time(h), _TZ)


def _vn(ref: datetime | None) -> datetime:
    """Mốc thời gian → giờ Việt Nam, LUÔN kèm múi giờ (so được với `deadline`/`next_change_at`).

    `ref` không kèm múi giờ coi như ĐÃ là giờ VN (job/test) → gắn múi giờ VN, không đổi giờ.
    """
    if ref is None:
        return now()
    return ref.astimezone(_TZ) if ref.tzinfo is not None else ref.replace(tzinfo=_TZ)


def editable_from(window: int, ref: datetime | None = None) -> date:
    """Ngày số liệu CŨ NHẤT còn nhập/sửa được tại thời điểm `ref` (mặc định: bây giờ).

    Chưa tới giờ chốt: hôm nay lùi N ngày. Đã qua giờ chốt: ngày đó vừa hết hạn ⇒ lùi N − 1.
    Có thể LỚN HƠN hôm nay (N = 0 và đã qua giờ chốt) = hôm nay cũng không nhập được nữa.
    """
    n = _vn(ref)
    start = n.date() - timedelta(days=window)
    return start if n.time() < time(cutoff_hour()) else start + timedelta(days=1)


def next_change_at(ref: datetime | None = None) -> datetime:
    """Mốc kế tiếp cửa sổ trượt (= giờ chốt kế tiếp): trang để mở qua mốc này phải tải lại cửa sổ."""
    n = _vn(ref)
    at = datetime.combine(n.date(), time(cutoff_hour()), _TZ)
    return at if n < at else at + timedelta(days=1)


def is_editable(as_of: date, window: int, ref: datetime | None = None) -> bool:
    n = _vn(ref)
    return editable_from(window, n) <= as_of <= n.date()


def alert_days() -> int:
    """Số ngày bảng nhắc việc rà lại. **0 = TẮT cảnh báo** (số âm coi như chưa cấu hình)."""
    from app.services import config_repo

    return _parse(config_repo.get_value(ALERT_KEY), DEFAULT_ALERT_DAYS)


def window_phrase(window: int) -> str:
    """N ngày → câu người dùng đọc không nhầm: "đến 11:00 ngày hôm sau", "đến 11:00, 7 ngày sau ngày số liệu"…

    Nói thẳng GIỜ CHỐT thay vì "hôm nay và N ngày trước": từ 24/09/2026 hạn tính tới giờ, nếu chỉ
    nói ngày thì đơn vị tưởng còn cả buổi chiều để nhập. KHÔNG viết "ngày thứ N": tiếng Việt đọc
    "ngày thứ 7" thành thứ Bảy.
    """
    hh = f"{cutoff_hour():02d}:00"
    if window <= 0:
        return f"đến {hh} cùng ngày"
    if window == 1:
        return f"đến {hh} ngày hôm sau"
    return f"đến {hh}, {window} ngày sau ngày số liệu"


def blocked_message(window: int) -> str:
    """Câu báo khi ngày đã quá hạn — dùng chung cho 403 và màn cần báo trước (link công khai)."""
    return (f"Ngày này đã chuyển sang chế độ chỉ xem — số liệu mỗi ngày chỉ được nhập/sửa "
            f"{window_phrase(window)}.")


def assert_editable(as_of: str | date, window: int) -> None:
    """403/400 nếu ngày đã quá hạn nhập (server ép — hàng rào thật, không chỉ ẩn UI).

    `as_of` nhận cả chuỗi 'YYYY-MM-DD' lẫn `date` (một số schema parse sẵn thành date).
    """
    if isinstance(as_of, date):
        d = as_of
    else:
        try:
            d = date.fromisoformat(str(as_of))
        except ValueError as exc:
            raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    n = now()
    if d > n.date():
        raise HTTPException(400, "Không nhập số liệu cho ngày trong tương lai.")
    if d < editable_from(window, n):
        raise HTTPException(403, blocked_message(window), headers={BLOCK_HEADER: "window"})
