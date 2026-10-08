"""TIỀN ĐẶT CỌC của hợp đồng bán — NHIỀU ĐỢT CỌC, mỗi đợt: số tiền · loại tiền · ngày cọc · chứng từ.

Yêu cầu VRG 07/10/2026: *"Hợp đồng đã bán chờ giao (đã có scan Hợp đồng, giờ yêu cầu bổ sung thêm
scan chứng từ cọc, Thanh toán) … mục ghi nhận số tiền đã cọc, thời gian đã cọc"*; chủ dự án bổ sung
cùng ngày: một hợp đồng **cọc nhiều đợt** (không phải một ô cọc cho mỗi hợp đồng).

Lưu ở cột jsonb `sales_contract.deposits` = `[{amount, ccy, date, docs}]`, theo thứ tự người nhập.
Khoản cọc thuộc về HỢP ĐỒNG, không thuộc từng lần giao ⇒ đợt giao luôn rỗng. Đơn vị tính theo đúng
quy ước giá trên dòng hợp đồng: VNĐ nhập **triệu đồng**, ngoại tệ nhập **nguyên tệ** — để so được
TỔNG cọc với giá trị hợp đồng mà không phải quy đổi.

⚠ Tiền cọc là số GHI NHẬN, không vào doanh thu hay báo cáo tiêu thụ nào — nên KHÔNG nằm trong
`sales_contract_lock.STAT_FIELDS` (sửa được cả sau khi chốt số liệu, như chứng từ thanh toán).
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core.market_meta import SALE_CURRENCIES
from app.services import contract_docs
from app.services import sales_contract_calc as calc

#: Nhóm ô của một bản ghi không có cọc (đợt giao, hoặc hợp đồng chưa cọc).
EMPTY: dict[str, Any] = {"deposits": []}

#: Trần số đợt cọc của một hợp đồng — chặn thân gửi bất thường, thực tế vài đợt.
MAX_DEPOSITS = 50

#: Nhãn đơn vị tính hiện trong thông báo lỗi — VNĐ là TRIỆU đồng (cùng quy ước đơn giá).
_UNIT = {"VND": "triệu đồng"}


def _fmt(v: float) -> str:
    return f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _amount(raw: Any, at: str) -> float | None:
    try:
        v = None if raw in (None, "") else float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{at}: số tiền cọc phải là số.") from exc
    if v is not None and not math.isfinite(v):
        raise ValueError(f"{at}: số tiền cọc phải là số.")
    if v is not None and v < 0:
        raise ValueError(f"{at}: số tiền cọc không được âm.")
    # 0 = không có tiền ở đợt này — cùng quy ước premium 0 = không có premium.
    return v or None


def _deposit_date(raw: Any, at: str) -> str | None:
    from app.core import edit_window

    s = str(raw or "").strip()[:10]
    if not s:
        return None
    try:
        d = date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"{at}: ngày cọc không hợp lệ (YYYY-MM-DD).") from exc
    # Ghi nhận khoản ĐÃ cọc — ngày tương lai là gõ nhầm năm/tháng (giờ Việt Nam, như cửa sổ sửa).
    if d > edit_window.today():
        raise ValueError(f"{at}: ngày cọc không được sau hôm nay.")
    return d.isoformat()


def _item(raw: Any, at: str) -> dict[str, Any] | None:
    """Một đợt cọc đã chuẩn hoá; đợt TRỐNG HẲN (không tiền, không ngày, không file) → None (bỏ)."""
    if not isinstance(raw, dict):
        raise ValueError(f"{at}: dữ liệu không hợp lệ.")
    amount = _amount(raw.get("amount"), at)
    paid = _deposit_date(raw.get("date"), at)
    docs = contract_docs.normalize(raw.get("docs"), None, None)
    if amount is None and paid is None and not docs:
        return None
    ccy = None
    if amount is not None:
        # Form luôn gửi loại tiền mặc định — không có số tiền thì loại tiền vô nghĩa, bỏ đi.
        ccy = str(raw.get("ccy") or "VND").strip().upper()
        if ccy not in SALE_CURRENCIES:
            raise ValueError(f"{at}: loại tiền cọc phải là một trong {', '.join(SALE_CURRENCIES)}.")
    return {"amount": amount, "ccy": ccy, "date": paid, "docs": docs}


def normalize(raw: Any) -> list[dict[str, Any]]:
    """Đọc từ DB → danh sách đợt cọc gọn (không kiểm tra lại — dữ liệu đã qua `clean`)."""
    return [{"amount": x.get("amount"), "ccy": x.get("ccy"), "date": x.get("date"),
             "docs": contract_docs.normalize(x.get("docs"), None, None)}
            for x in (raw if isinstance(raw, list) else []) if isinstance(x, dict)]


def contract_value(lines: list[dict], ccy: str) -> float | None:
    """Giá trị hợp đồng theo ĐÚNG loại tiền cọc (VNĐ: triệu đồng · ngoại tệ: nguyên tệ).

    None khi không so được: có dòng khác loại tiền (cọc VNĐ cho hợp đồng USD) hoặc dòng chưa có
    giá — thiếu dữ kiện thì không chặn, không đoán.
    """
    total = 0.0
    for ln in lines or []:
        qty, price = ln.get("qty"), ln.get("price")
        # Giá 0 = chưa chốt giá (phụ lục theo công thức) — coi như thiếu, không phải hợp đồng 0 đồng.
        if (ln.get("ccy") or "VND") != ccy or qty is None or not price:
            return None
        total += calc.line_amount(ln) or 0.0   # ngoại tệ: từng dòng làm tròn 2 số lẻ như hoá đơn
    return total if lines else None


def clean(row: dict, lines: list[dict], *, is_child: bool) -> dict[str, Any]:
    """{deposits: [...]} đã chuẩn hoá; TỔNG cọc từng loại tiền không được vượt giá trị hợp đồng."""
    if is_child:
        return {"deposits": []}
    raw = row.get("deposits") or []
    if not isinstance(raw, list):
        raise ValueError("Danh sách đợt cọc không hợp lệ.")
    if len(raw) > MAX_DEPOSITS:
        raise ValueError(f"Tối đa {MAX_DEPOSITS} đợt cọc cho một hợp đồng.")
    items = [it for i, r in enumerate(raw, 1) if (it := _item(r, f"Đợt cọc {i}"))]
    totals: dict[str, float] = {}
    for it in items:
        if it["amount"] is not None:
            totals[it["ccy"]] = totals.get(it["ccy"], 0.0) + it["amount"]
    for ccy, total in totals.items():
        value = contract_value(lines, ccy)
        if value is not None and total > value + 1e-6:
            unit = _UNIT.get(ccy, ccy)
            raise ValueError(
                f"Tổng tiền cọc {_fmt(total)} {unit} lớn hơn giá trị hợp đồng {_fmt(value)} {unit} — "
                "kiểm lại đơn vị tính (VNĐ nhập theo TRIỆU đồng).")
    return {"deposits": items}
