"""CHỈ THỊ GIAO HÀNG của một lần giao — thời gian giao · địa điểm giao · scan chỉ thị.

Yêu cầu VRG 07/10/2026: *"Hợp đồng đã bán chờ giao e thêm phần chỉ thị giao hàng (thời gian giao,
địa điểm, kèm scan chứng từ) bên cạnh nội dung cọc"*.

Chỉ thị giao hàng do khách phát cho TỪNG chuyến hàng ⇒ nằm ở bản ghi là MỘT LẦN GIAO (hợp đồng giao
1 lần, hoặc từng đợt giao) — cùng chỗ với hoá đơn/thanh toán. Hợp đồng giao nhiều lần không mang
(mỗi đợt một chỉ thị). Thời gian giao là ngày KẾ HOẠCH nên được phép ở tương lai.

Số ghi nhận, không vào báo cáo nào ⇒ KHÔNG nằm trong `sales_contract_lock.STAT_FIELDS`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services import contract_docs

EMPTY: dict[str, Any] = {"instruction_date": None, "instruction_place": None,
                         "instruction_docs": []}
FIELDS: tuple[str, ...] = tuple(EMPTY)

_PLACE_MAX = 200


def clean(row: dict, *, is_batch: bool) -> dict[str, Any]:
    """{instruction_date, instruction_place, instruction_docs} đã chuẩn hoá cho một bản ghi."""
    if not is_batch:
        return dict(EMPTY)
    s = str(row.get("instruction_date") or "").strip()[:10]
    try:
        when = date.fromisoformat(s).isoformat() if s else None
    except ValueError as exc:
        raise ValueError("Thời gian giao theo chỉ thị không hợp lệ (YYYY-MM-DD).") from exc
    place = str(row.get("instruction_place") or "").strip()[:_PLACE_MAX] or None
    return {"instruction_date": when, "instruction_place": place,
            "instruction_docs": contract_docs.normalize(row.get("instruction_docs"), None, None)}
