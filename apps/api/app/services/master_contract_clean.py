"""Chuẩn hoá + KIỂM TRA NGHIỆP VỤ một HỢP ĐỒNG MẸ (HĐNT/HĐDH) trước khi ghi.

Hợp đồng mẹ là HỒ SƠ GỐC ký với khách hàng — nó KHÔNG vào báo cáo sản lượng nào (tiêu thụ và
"đã ký HĐ chưa giao" vẫn tính trên `sales_contract`). Vì vậy ràng buộc ở đây nới hơn hợp đồng bán:
số lượng được để trống, vì HĐ nguyên tắc thường chỉ chốt chủng loại. Ngược lại, những gì làm hồ
sơ vô nghĩa thì BẮT BUỘC: số hợp đồng, loại hợp đồng, khách hàng và ít nhất một chủng loại.

ĐƠN GIÁ / LOẠI TIỀN / TỶ GIÁ không thuộc hồ sơ mẹ (chốt 25/08/2026) — giá là số của từng chuyến,
khai ở phụ lục; hồ sơ mẹ chỉ giữ CÔNG THỨC GIÁ.

CÔNG THỨC GIÁ chỉ thuộc về HĐ DÀI HẠN — HĐ nguyên tắc không có phần này (chốt 22/08/2026).

Giá trị sai vẫn BÁO LỖI chứ không lặng lẽ quy về mặc định — cùng nguyên tắc với
`sales_contract_clean`.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core.market_meta import DRY_REQUIRED_GRADES, MASTER_CONTRACT_TYPES, UNIT_GRADES
from app.services import contract_certs, contract_docs, customer_repo

_GRADES = frozenset(UNIT_GRADES)


def _num(v) -> float | None:
    """Số hợp lệ hoặc None — loại NaN/Infinity (`nan <= 0` là False nên lọt mọi kiểm tra)."""
    try:
        f = None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
    return None if f is not None and not math.isfinite(f) else f


def _int_id(v, label: str) -> int | None:
    """Khoá số dương hoặc None. `str(-1).isdigit()` là False nên số âm từng lặng lẽ thành None."""
    s = str(v if v is not None else "").strip()
    if not s:
        return None
    if not s.isdigit() or int(s) <= 0:
        raise ValueError(f"{label} không hợp lệ.")
    return int(s)


def _as_date(v, label: str) -> date | None:
    s = str(v or "").strip()[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def clean_lines(lines) -> list[dict[str, Any]]:
    """Dòng cam kết của hợp đồng mẹ: chủng loại BẮT BUỘC, số lượng + quy khô tuỳ chọn.

    KHÔNG có đơn giá / loại tiền / tỷ giá (chốt 25/08/2026) — hồ sơ mẹ cam kết chủng loại và sản
    lượng, còn giá là số của từng chuyến (khai ở phụ lục) hoặc đi theo công thức giá của hồ sơ.
    Bản ghi cũ có 3 ô này thì lần lưu sau bỏ luôn, không báo lỗi: người dùng không còn ô nào để sửa.

    QUY KHÔ khai giống dòng hợp đồng bán: latex và 2 loại mủ nguyên liệu bán theo mủ nước nên
    số lượng cam kết phải đi kèm phần quy khô; chủng loại thành phẩm không có ô này.
    """
    out: list[dict[str, Any]] = []
    for i, ln in enumerate(lines if isinstance(lines, list) else [], start=1):
        if not isinstance(ln, dict):
            continue
        grade = str(ln.get("grade") or "").strip()[:80]
        qty, qty_dry = _num(ln.get("qty")), _num(ln.get("qty_dry"))
        if not grade and qty is None and qty_dry is None:
            continue  # dòng trống người dùng bấm thêm rồi bỏ dở
        if not grade:
            raise ValueError(f"Dòng {i}: thiếu chủng loại.")
        if grade not in _GRADES:
            raise ValueError(f"Dòng {i}: chủng loại “{grade}” không có trong danh mục.")
        if qty is not None and qty <= 0:
            raise ValueError(f"Dòng {i} ({grade}): số lượng phải lớn hơn 0 (để trống nếu chưa "
                             "cam kết sản lượng).")
        if grade not in DRY_REQUIRED_GRADES and qty_dry is not None:
            raise ValueError(f"Dòng {i} ({grade}): chủng loại này không có quy khô — số lượng bán "
                             "đã là khối lượng khô. Chỉ latex và mủ nguyên liệu mới khai quy khô.")
        # Quy khô ĐI KÈM số lượng, không ép khi chưa cam kết sản lượng: hồ sơ mẹ được phép chỉ
        # chốt chủng loại (khác hợp đồng bán — ở đó số lượng luôn bắt buộc nên quy khô cũng vậy).
        if grade in DRY_REQUIRED_GRADES and qty is not None and (qty_dry is None or qty_dry <= 0):
            raise ValueError(f"Dòng {i} ({grade}): đã cam kết số lượng thì phải nhập quy khô.")
        if qty_dry is not None and qty_dry <= 0:
            raise ValueError(f"Dòng {i} ({grade}): quy khô phải lớn hơn 0.")
        if qty is not None and qty_dry is not None and qty_dry > qty + 1e-9:
            raise ValueError(f"Dòng {i} ({grade}): quy khô ({qty_dry:g} tấn) không thể lớn hơn "
                             f"số lượng ({qty:g} tấn).")
        out.append({"grade": grade, "qty": qty, "qty_dry": qty_dry})
    if not out:
        raise ValueError("Hợp đồng mẹ phải có ít nhất một chủng loại.")
    seen = [ln["grade"] for ln in out]
    dup = {g for g in seen if seen.count(g) > 1}
    if dup:
        raise ValueError(f"Chủng loại bị lặp: {', '.join(sorted(dup))} — mỗi chủng loại một dòng.")
    return out


def clean(row: dict, company: str) -> dict[str, Any]:
    """Chuẩn hoá + kiểm tra 1 hợp đồng mẹ trước khi ghi (raise ValueError nếu sai)."""
    code = str(row.get("code") or "").strip()[:80]
    if not code:
        raise ValueError("Thiếu số hợp đồng.")
    master_type = str(row.get("master_type") or "").strip()
    if master_type not in MASTER_CONTRACT_TYPES:
        raise ValueError("Thiếu loại hợp đồng mẹ (HĐ nguyên tắc / HĐ dài hạn).")
    customer_id = _int_id(row.get("customer_id"), "Khách hàng")
    if customer_id is None:
        raise ValueError("Hợp đồng mẹ phải gán một khách hàng của đơn vị.")
    owner = customer_repo.owner_of(customer_id)
    if owner is None:
        raise ValueError("Khách hàng không còn tồn tại.")
    if owner != company:
        raise ValueError("Khách hàng thuộc danh mục của đơn vị khác.")
    sign = _as_date(row.get("sign_date"), "Ngày ký")
    expiry = _as_date(row.get("expiry_date"), "Thời hạn hợp đồng")
    if sign and expiry and expiry < sign:
        raise ValueError("Thời hạn hợp đồng phải sau ngày ký.")
    return {
        "id": _int_id(row.get("id"), "Mã hợp đồng mẹ"),
        "company": company,
        "code": code,
        "master_type": master_type,
        "customer_id": customer_id,
        "sign_date": sign.isoformat() if sign else None,
        "expiry_date": expiry.isoformat() if expiry else None,
        "lines": clean_lines(row.get("lines")),
        # CÔNG THỨC GIÁ chỉ có ở HĐ DÀI HẠN. HĐ nguyên tắc không có phần này: form ẩn ô đi nhưng
        # bản ghi cũ (hoặc client cũ) vẫn gửi chữ lên — nhận vào là màn chi tiết hiện một công
        # thức mà người dùng không còn ô nào để sửa/xoá. Bỏ ở đây, không báo lỗi (đổi loại hợp
        # đồng là thao tác hợp lệ, không phải nhập sai).
        "price_formula": (str(row.get("price_formula") or "").strip()[:2000] or None
                          if master_type == "long_term" else None),
        "files": contract_docs.normalize(row.get("files"), None, None),
        "note": str(row.get("note") or "").strip()[:500] or None,
        # Hàng có chứng chỉ + premium — xem `services/contract_certs.py`.
        **contract_certs.clean(row),
    }
