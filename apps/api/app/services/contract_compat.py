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


#: Ô MỚI ở TỪNG DÒNG chi tiết — doanh thu VNĐ theo kế toán (08/10/2026).
LINE_KEYS = ("revenue_vnd",)
#: Dòng của client cũ chỉ được nhận lại số đang lưu khi các ô tiền của dòng KHÔNG đổi — đổi số
#: lượng/giá/tỷ giá thì doanh thu kế toán cũ không còn đúng với dòng đó nữa.
_MONEY = ("grade", "qty", "price", "ccy", "fx")


def dump(body: BaseModel) -> dict[str, Any]:
    """`model_dump()` nhưng BỎ các nhóm mà client không gửi khoá nào (để `fill_missing` giữ lại);
    ô mới của dòng chi tiết mà client không gửi cũng bị bỏ khỏi đúng dòng đó."""
    unsent = {k for g in GROUPS if not set(g) & body.model_fields_set for k in g}
    out = body.model_dump(exclude=unsent or None)
    for ln, src in zip(out.get("lines") or [], getattr(body, "lines", None) or []):
        for k in LINE_KEYS:
            if k not in src.model_fields_set:
                ln.pop(k, None)
    return out


def fill_missing(row: dict, current: dict | None) -> dict:
    """Nhóm vắng mặt trong `row` → lấy số đang lưu của `current` (bản ghi mới thì giá trị rỗng).
    Dòng thiếu ô mới → lấy của dòng CÙNG VỊ TRÍ đang lưu nếu ô tiền của hai dòng trùng nhau."""
    out = dict(row)
    for group in GROUPS:
        if not any(k in row for k in group):
            out.update({k: (current or {}).get(k, v) for k, v in group.items()})
    # Bỏ ngày giao thì không còn số kế toán nào để giữ — nhét lại là client cũ dính lỗi "chỉ nhập khi
    # đã có ngày giao" về một ô nó không hề thấy.
    if isinstance(row.get("lines"), list) and row.get("delivered_at"):
        out["lines"] = [_fill_line(ln, i, (current or {}).get("lines") or [])
                        for i, ln in enumerate(row["lines"])]
    return out


def _fill_line(ln: Any, i: int, stored: list) -> Any:
    old = stored[i] if i < len(stored) and isinstance(stored[i], dict) else None
    if not isinstance(ln, dict) or old is None or not _same_money(ln, old):
        return ln
    return {**ln, **{k: old[k] for k in LINE_KEYS if k not in ln and k in old}}


def _same_money(a: dict, b: dict) -> bool:
    def key(x: dict) -> tuple:
        return tuple(str(x.get(k) or "").upper() if k in ("grade", "ccy")
                     else (float(x[k]) if x.get(k) not in (None, "") else None) for k in _MONEY)
    try:
        return key(a) == key(b)
    except (TypeError, ValueError):
        return False
