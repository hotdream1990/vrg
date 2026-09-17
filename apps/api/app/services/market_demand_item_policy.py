"""Luật của phiếu Nhu cầu thị trường: chuẩn hoá + kiểm tra (§3) và hàng rào thời gian (§4).

Dùng CHUNG cho router đơn vị (`/api/member/market-demand/items`), router chuyên viên
(`/api/market-demand/items`) và luồng «Đề nghị sửa» (`edit_request_ops_demand`) — một luật, một chỗ.

Hàng rào: sửa phiếu mà CHỈ đổi ô theo dõi (kết quả · ghi chú) thì miễn cửa sổ
nhập liệu. Cách nhận biết giống `sales_contract_lock`: KHÔNG liệt kê ô được sửa mà so ẢNH CHỤP các ô
NỘI DUNG cũ/mới — thêm ô mới vào `CONTENT_FIELDS` là tự động bị gác, không lọt qua theo mặc định.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException

from app.core import edit_window, security
from app.core.market_demand_meta import (
    CONTENT_FIELDS, CURRENCIES, CUSTOMER_MAX, DELIVERY_TIME_MAX, GRADES, NOTE_MAX, PLACE_MAX,
    PRICE_CAP, PRICE_CAP_MESSAGE, QTY_UNITS, RESULT_MAX,
)

DEFAULT_LIST_DAYS = 90
_NUM_FIELDS = frozenset({"qty", "price"})
_DATE_FIELDS = frozenset({"as_of"})


def _bad(msg: str) -> HTTPException:
    return HTTPException(400, msg)


def _date(value: Any, label: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError as exc:
        raise _bad(f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def _text(value: Any, label: str, max_len: int) -> str:
    out = str(value or "").strip()
    if len(out) > max_len:
        raise _bad(f"{label} tối đa {max_len} ký tự.")
    return out


def _num(value: Any, label: str) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise _bad(f"{label} phải là số.") from exc
    if not math.isfinite(out) or out < 0:
        raise _bad(f"{label} phải là số không âm.")
    return out


def _choice(value: Any, options: dict[str, str], label: str, default: str) -> str:
    out = str(value or "").strip() or default
    if out not in options:
        raise _bad(f"{label} không hợp lệ.")
    return out


def clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Payload thô → phiếu đã chuẩn hoá (ngày ISO, số float). Sai luật ⇒ 400 kèm câu tiếng Việt."""
    today = edit_window.today().isoformat()
    as_of = _date(raw.get("as_of"), "Ngày nhận")
    if not as_of:
        raise _bad("Nhập ngày nhận nhu cầu.")
    if as_of > today:
        raise _bad("Ngày nhận nhu cầu không được ở tương lai.")
    company = str(raw.get("company") or "").strip()
    if not company:
        raise _bad("Chọn đơn vị ghi nhận nhu cầu.")
    customer = _text(raw.get("customer"), "Tên khách hàng", CUSTOMER_MAX)
    if not customer:
        raise _bad("Nhập tên khách hàng.")
    grade = str(raw.get("grade") or "").strip()
    if grade not in GRADES:
        raise _bad("Chủng loại không hợp lệ — chọn trong danh mục.")
    currency = _choice(raw.get("currency"), CURRENCIES, "Loại tiền", "VND")
    price = _num(raw.get("price"), "Đơn giá")
    if price is not None and price > PRICE_CAP[currency]:
        raise _bad(PRICE_CAP_MESSAGE[currency])
    item_id = raw.get("id")
    return {
        "id": int(item_id) if item_id else None,
        "company": company, "as_of": as_of, "customer": customer, "grade": grade,
        "qty": _num(raw.get("qty"), "Số lượng"),
        "qty_unit": _choice(raw.get("qty_unit"), QTY_UNITS, "Đơn vị số lượng", "ton"),
        "price": price, "currency": currency,
        "delivery_place": _text(raw.get("delivery_place"), "Nơi giao", PLACE_MAX),
        "delivery_time": _text(raw.get("delivery_time"), "Thời gian giao", DELIVERY_TIME_MAX),
        "result": _text(raw.get("result"), "Kết quả", RESULT_MAX),
        "note": _text(raw.get("note"), "Ghi chú", NOTE_MAX),
    }


def _canon(field: str, value: Any) -> Any:
    """Một dạng duy nhất để so: 5 và 5.0 là một, "" và None là một (DB trả numeric/date)."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if field in _NUM_FIELDS:
        return float(value)
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    return text[:10] if field in _DATE_FIELDS else text


def content_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """Ảnh chụp CHỈ các ô nội dung — hai ảnh giống nhau nghĩa là lần sửa chỉ chạm ô theo dõi."""
    return {f: _canon(f, row.get(f)) for f in CONTENT_FIELDS}


def fence_dates(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    """Các ngày phải qua cửa sổ nhập liệu cho lần lưu này. Rỗng = chỉ đổi ô theo dõi (miễn).

    Thêm mới: ngày nhận mới. Sửa nội dung: CẢ ngày cũ lẫn ngày mới — không cho kéo phiếu ra/vào
    vùng đã khoá bằng cách đổi ngày nhận.
    """
    if old is None:
        return [new["as_of"]]
    if content_snapshot(old) == content_snapshot(new):
        return []
    return sorted({str(old["as_of"])[:10], str(new["as_of"])[:10]})


def assert_save_fences(username: str, old: dict[str, Any] | None, new: dict[str, Any]) -> None:
    """403 (header `X-Edit-Blocked: window`) nếu lần lưu chạm ngày ngoài cửa sổ của vai trò."""
    for as_of in fence_dates(old, new):
        security.assert_edit_window(username, as_of)


def assert_delete_fences(username: str, old: dict[str, Any]) -> None:
    security.assert_edit_window(username, str(old["as_of"])[:10])


def date_range(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """Khoảng ngày của màn danh sách — mặc định 90 ngày gần nhất tới hôm nay."""
    today = edit_window.today()
    d_from = _date(date_from, "Từ ngày") or (today - timedelta(days=DEFAULT_LIST_DAYS)).isoformat()
    d_to = _date(date_to, "Đến ngày") or today.isoformat()
    if d_to < d_from:
        raise _bad("Đến ngày phải sau hoặc bằng Từ ngày.")
    return d_from, d_to
