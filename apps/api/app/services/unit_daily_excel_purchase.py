"""Đổi DÒNG EXCEL ↔ payload biểu Thu mua (mủ nguyên liệu + thu mua thành phẩm).

Tách khỏi `unit_daily_excel_io` (nơi khai báo CỘT của 4 loại biểu) để chỗ khai cột và chỗ hiểu
nghĩa của dòng không dính vào nhau.

Mủ nguyên liệu (mủ nước · mủ chén · mủ dây) là số CỦA CẢ NGÀY: mỗi (đơn vị, ngày) một ô sản lượng
cho mỗi loại mủ, điền ở dòng đầu. **Không có chủng loại** — chủng loại chỉ có ở mủ đã chế biến,
tức phần THU MUA THÀNH PHẨM (mỗi chủng loại một dòng).
"""

from __future__ import annotations

from typing import Any

from app.services.unit_daily_fields import FINISHED_TABLE

#: Ô sản lượng của 3 loại mủ nguyên liệu — số của cả ngày, lấy ô đầu tiên có số trong các dòng.
MATERIAL_KEYS: tuple[str, ...] = ("latex_wet", "coagulum", "lace")

#: Đơn giá của CẢ NGÀY (không theo dòng) — nằm ở kho giá riêng chứ không ở payload.
PRICE_KEYS: tuple[str, ...] = ("price_latex", "price_cup", "price_lace")


def fields_from_rows(items: list[dict[str, Any]],
                     current: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Các dòng Excel của một (đơn vị, ngày) → payload biểu Thu mua, MERGE với số đã có.

    Trả kèm danh sách cảnh báo (chưa gắn tên đơn vị/ngày — người gọi tự gắn).
    """
    fields = dict(current or {})
    for key in MATERIAL_KEYS:
        value = next((r.get(key) for r in items if r.get(key) is not None), None)
        if value is not None:
            fields[key] = value

    warnings: list[str] = []
    finished, fin_warnings = _finished_rows(items, fields)
    if finished:
        fields[FINISHED_TABLE] = finished
        warnings.extend(fin_warnings)
    return fields, warnings


def _finished_rows(items: list[dict[str, Any]],
                   fields: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Dòng thu mua thành phẩm — file không có cột tỷ giá nên lấy lại tỷ giá đã nhập trên web."""
    old_fx = next((r.get("fx") for r in (fields.get(FINISHED_TABLE) or [])
                   if isinstance(r, dict) and r.get("fx")), None)
    rows = [{"grade": r["finished_grade"], "qty": r.get("finished_qty"),
             "price": r.get("finished_price"),
             "ccy": (ccy := r.get("finished_ccy") or "VND"),
             "fx": old_fx if ccy == "USD" else None}
            for r in items if r.get("finished_grade")]
    warnings: list[str] = []
    if rows and old_fx is None and any(r["ccy"] == "USD" for r in rows):
        warnings.append("có dòng thành phẩm bằng USD chưa có tỷ giá "
                        "(nhập tỷ giá ở màn Thu mua rồi lưu lại).")
    return rows, warnings
