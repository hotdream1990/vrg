"""Giữ các NHÓM Ô MỚI của hợp đồng khi thân gửi lên chưa biết tới chúng.

Hai nguồn thân thiếu khoá: web bản cũ còn trong bộ nhớ đệm trình duyệt, và «đề nghị sửa» gửi TRƯỚC
khi có ô mới mà Ban duyệt sau đó. `ContractIn.model_dump()` điền mặc định (None / []) cho khoá vắng
mặt ⇒ lưu/duyệt xong là xoá trắng dữ liệu người khác vừa bổ sung. Vì vậy: nhóm nào người gửi không
gửi khoá nào thì giữ nguyên số đang lưu; gửi dù một khoá của nhóm = người gửi biết nhóm đó.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.services import contract_deposit, contract_instruction

#: Nhóm ô bổ sung 07/10/2026 — tiền đặt cọc · chỉ thị giao hàng.
GROUPS: tuple[dict[str, Any], ...] = (contract_deposit.EMPTY, contract_instruction.EMPTY)


def dump(body: BaseModel) -> dict[str, Any]:
    """`model_dump()` nhưng BỎ các nhóm mà client không gửi khoá nào (để `fill_missing` giữ lại)."""
    unsent = {k for g in GROUPS if not set(g) & body.model_fields_set for k in g}
    return body.model_dump(exclude=unsent or None)


def fill_missing(row: dict, current: dict | None) -> dict:
    """Nhóm vắng mặt trong `row` → lấy số đang lưu của `current` (bản ghi mới thì giá trị rỗng)."""
    out = dict(row)
    for group in GROUPS:
        if not any(k in row for k in group):
            out.update({k: (current or {}).get(k, v) for k, v in group.items()})
    return out
