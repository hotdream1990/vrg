"""Gác GHI số liệu theo đơn vị — dùng chung cho mọi endpoint nhập liệu có cột `company`.

Trước đây mỗi router tự kiểm `company in active_names()` rồi trả "Đơn vị không hợp lệ." Câu đó
không nói được vì sao, mà từ khi có SÁP NHẬP thì lý do mới là thứ người nhập cần biết: đơn vị này
đã sáp nhập vào đâu, từ ngày nào, và giờ phải nhập vào đơn vị nào.

Luật: số liệu của ngày TRƯỚC ngày sáp nhập vẫn thuộc đơn vị cũ nên vẫn sửa/bổ sung được; từ ngày
hiệu lực trở đi mới bị đẩy sang đơn vị mới (xem `services/member_unit_merge.py`).
"""

from __future__ import annotations

from fastapi import HTTPException


def assert_unit_can_enter(company: str, as_of: str | None = None, *,
                          require_known: bool = True) -> None:
    """Chặn ghi vào đơn vị không tồn tại / đang ẩn / đã sáp nhập tại NGÀY SỐ LIỆU `as_of`.

    `as_of` là ngày của SỐ LIỆU, không phải hôm nay. Không truyền = thao tác không gắn ngày cụ thể
    → coi như "từ nay trở đi" và đơn vị đã sáp nhập bị chặn. `require_known=False` cho nơi đã có
    gác riêng chặt hơn (xem `member_unit_merge.assert_can_enter`).
    """
    from app.services import member_unit_merge

    try:
        member_unit_merge.assert_can_enter(company, as_of, require_known=require_known)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
