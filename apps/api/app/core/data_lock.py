"""Hàng rào CHỐT SỐ LIỆU: ngày đã chốt thì ĐƠN VỊ không tự sửa được nữa.

Khác [cửa sổ nhập liệu](edit_window.py) ở chỗ: cửa sổ trượt theo hôm nay và giống nhau cho mọi đơn
vị, còn mốc chốt là **một ngày cố định của riêng từng đơn vị**, do chính đơn vị xác nhận (hoặc quản
trị khoá hộ). Hai hàng rào chạy độc lập và **cái nào chặn tới ngày mới hơn thì cái đó quyết định**
— đúng yêu cầu 25/08/2026: *"ngày nào mới hơn thì sẽ bị chặn tới thời điểm đó"*.

Ai bị chặn: **chỉ tài khoản đơn vị thành viên**. Chuyên viên và quản trị vẫn sửa được — sau khi
chốt, đó là đường sửa duy nhất (đơn vị báo Ban TTKD sửa hộ).

KẾ HOẠCH NĂM chốt CÙNG ĐỢT (03/10/2026): xác nhận chốt số liệu đến hết ngày X là xác nhận luôn chỉ
tiêu kế hoạch của năm X — từ đó kế hoạch năm ≤ năm của mốc chốt thì đơn vị không tự sửa, phải gửi
«Đề nghị sửa» (`assert_plan_not_locked`). Kế hoạch năm mới mở cho tới khi đơn vị chốt đợt đầu năm đó.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException

from app.core.edit_window import BLOCK_HEADER

#: Câu báo lỗi dùng CHUNG cho mọi endpoint — đơn vị phải biết ngay phải làm gì tiếp theo.
#: Câu trung tính: hàng rào này chỉ chặn đơn vị, nhưng câu có thể hiện ở màn dùng chung.
_MSG = ("Số liệu đến hết ngày {lock} đã được chốt — đơn vị không tự sửa được nữa. "
        "Cần điều chỉnh số liệu ngày này, đơn vị gửi «Đề nghị sửa» để Ban duyệt.")

#: Phần đuôi CHỈ dành cho hợp đồng/đợt giao: ở đó các ô không ảnh hưởng số liệu vẫn sửa được
#: (chốt 29/08/2026) — nói rõ để đơn vị khỏi tưởng bản ghi đã đóng băng hoàn toàn.
_MSG_SAFE_TAIL = (" Riêng các nội dung KHÔNG ảnh hưởng số liệu thì vẫn sửa được bình thường: {ok}.")


def locked_until(company: str) -> date | None:
    """Mốc chốt của đơn vị (None = chưa chốt lần nào)."""
    from app.services import data_lock_repo

    return data_lock_repo.locked_until(company)


def _as_date(as_of: str | date) -> date:
    if isinstance(as_of, date):
        return as_of
    try:
        return date.fromisoformat(str(as_of)[:10])
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc


_PLAN_MSG = ("Kế hoạch năm {year} đã được chốt cùng số liệu (đơn vị đã xác nhận chốt đến hết ngày "
             "{lock}) — đơn vị không tự sửa được nữa. Cần điều chỉnh chỉ tiêu, đơn vị gửi «Đề nghị sửa» "
             "để Ban duyệt.")


def plan_locked(lock: date | None, year: int) -> bool:
    """Kế hoạch năm `year` đã chốt chưa, với mốc chốt `lock` của đơn vị (luật duy nhất — mọi nơi gọi đây)."""
    return bool(lock and lock.year >= int(year))


def assert_plan_not_locked(company: str, year: int) -> None:
    """403 (header chặn = lock) nếu kế hoạch năm `year` của đơn vị đã chốt cùng đợt chốt số liệu."""
    lock = locked_until(company)
    if plan_locked(lock, year):
        raise HTTPException(403, _PLAN_MSG.format(year=year, lock=lock.strftime("%d/%m/%Y")),
                            headers={BLOCK_HEADER: "lock"})


def is_locked(company: str, as_of: str | date | None) -> bool:
    if not as_of:
        return False
    lock = locked_until(company)
    return bool(lock and _as_date(as_of) <= lock)


def assert_not_locked(company: str, *dates: str | date | None,
                      safe_fields: str | None = None) -> None:
    """403 nếu BẤT KỲ ngày nào trong `dates` đã nằm trong vùng chốt của đơn vị.

    Nhận nhiều ngày để chặn cả hai đầu của thao tác dời ngày / đổi ngày giao: kéo số liệu RA khỏi
    vùng đã chốt cũng là làm đổi số đã chốt.

    `safe_fields` — danh sách ô vẫn sửa được của màn đang gọi (hợp đồng/đợt giao). Có thì ghép vào
    câu báo lỗi: người dùng biết ngay mình bỏ ô nào ra là lưu được, khỏi đoán.
    """
    days = [_as_date(d) for d in dates if d]
    if not days:
        return
    lock = locked_until(company)
    if lock and min(days) <= lock:
        msg = _MSG.format(lock=lock.strftime("%d/%m/%Y"))
        if safe_fields:
            msg += _MSG_SAFE_TAIL.format(ok=safe_fields)
        raise HTTPException(403, msg, headers={BLOCK_HEADER: "lock"})
