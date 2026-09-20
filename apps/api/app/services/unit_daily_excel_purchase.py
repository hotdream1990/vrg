"""Đổi qua lại giữa DÒNG EXCEL và payload biểu Thu mua (mủ nguyên liệu + thu mua thành phẩm).

Tách khỏi `unit_daily_excel_io` (nơi khai báo CỘT của 4 loại biểu) để chỗ khai cột và chỗ hiểu
nghĩa của dòng không dính vào nhau.

Mủ nguyên liệu có HAI cách khai trên cùng một mẫu file:
  - dòng CÓ "Chủng loại mủ nguyên liệu" → một dòng của bảng chủng loại (`latex_grades` /
    `cup_grades` / `lace_grades`); ô tổng khi đó là số SUY RA = tổng các dòng;
  - dòng KHÔNG có chủng loại            → ô tổng như trước (`latex_wet` / `coagulum` / `lace`).

File mẫu CŨ không có cột chủng loại ⇒ mọi dòng đều là dòng tổng ⇒ nhập y hệt trước đây. Ngày chưa
tách chủng loại khi XUẤT cũng chỉ ra một dòng tổng — không bịa chủng loại cho số cũ.

Số lượng của mỗi chủng loại nằm ĐÚNG cột số lượng của loại mủ đó (mủ nước / mủ chén / mủ dây), nên
một chủng loại mua cả mủ nước lẫn mủ chén chỉ tốn MỘT dòng. Đơn giá KHÔNG đi theo dòng: vẫn một
giá cho cả loại mủ trong ngày (xem `unit_daily_fields.MATERIAL_GRADE_TABLES`).
"""

from __future__ import annotations

from typing import Any

from app.services.unit_daily_fields import FINISHED_TABLE, MATERIAL_GRADE_TABLES

#: Khoá cột "Chủng loại mủ nguyên liệu" trong file Excel (khai báo cột ở `unit_daily_excel_io`).
GRADE_COL = "material_grade"

#: Tên loại mủ trong câu cảnh báo gửi người nhập.
_LABELS = {"latex": "mủ nước", "cup": "mủ chén", "lace": "mủ dây"}

#: Đơn giá của CẢ NGÀY (không theo dòng) — nằm ở kho giá riêng chứ không ở payload, nên khi xuất
#: phải do người gọi truyền vào.
PRICE_KEYS: tuple[str, ...] = ("price_latex", "price_cup", "price_lace")


def export_rows(fields: dict[str, Any] | None,
                prices: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Số liệu đã lưu của một (đơn vị, ngày) → các dòng Excel (chưa gắn cột Đơn vị / Ngày).

    `prices` = {`price_latex`|`price_cup`|`price_lace`: số} lấy từ kho giá mủ nguyên liệu; để
    trống thì file xuất ra không có đơn giá (payload không giữ đơn giá VNĐ).
    """
    fields = fields or {}
    graded: dict[str, dict[str, Any]] = {}      # chủng loại → 1 dòng, dùng chung cho 3 loại mủ
    totals: dict[str, Any] = {}
    for table, total_key in MATERIAL_GRADE_TABLES.values():
        lines = [ln for ln in (fields.get(table) or [])
                 if isinstance(ln, dict) and ln.get("grade")]
        if lines:
            for ln in lines:
                grade = str(ln["grade"])
                graded.setdefault(grade, {GRADE_COL: grade})[total_key] = ln.get("qty")
        elif fields.get(total_key) is not None:
            totals[total_key] = fields[total_key]   # ngày chưa tách chủng loại → 1 dòng tổng
    rows: list[dict[str, Any]] = list(graded.values())
    if totals:
        rows.append(totals)

    finished = [ln for ln in (fields.get(FINISHED_TABLE) or [])
                if isinstance(ln, dict) and ln.get("grade")]
    for i, ln in enumerate(finished):
        if i >= len(rows):
            rows.append({})
        rows[i].update({"finished_grade": ln["grade"], "finished_qty": ln.get("qty"),
                        "finished_price": ln.get("price"), "finished_ccy": ln.get("ccy") or "VND"})

    px = {k: v for k, v in (prices or {}).items() if k in PRICE_KEYS and v is not None}
    if px:
        if not rows:
            rows.append({})
        rows[0].update(px)                          # đơn giá là số của cả ngày → ghi ở dòng đầu
    return rows


def fields_from_rows(items: list[dict[str, Any]],
                     current: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Các dòng Excel của một (đơn vị, ngày) → payload biểu Thu mua, MERGE với số đã có.

    Trả kèm danh sách cảnh báo (chưa gắn tên đơn vị/ngày — người gọi tự gắn).
    Dòng trùng chủng loại và ô tổng suy ra do `unit_daily_fields.clean_fields` lo khi lưu.
    """
    fields = dict(current or {})
    warnings: list[str] = []
    graded = [r for r in items if r.get(GRADE_COL)]
    plain = [r for r in items if not r.get(GRADE_COL)]
    for mat, (table, total_key) in MATERIAL_GRADE_TABLES.items():
        lines = [{"grade": r[GRADE_COL], "qty": r[total_key]}
                 for r in graded if r.get(total_key) is not None]
        total = next((r[total_key] for r in plain if r.get(total_key) is not None), None)
        if lines:
            fields[table] = lines
            fields.pop(total_key, None)             # ô tổng là số SUY RA, để clean_fields tính
            if total is not None:
                warnings.append(
                    f"{_LABELS[mat]}: file vừa có dòng chủng loại vừa có ô tổng — lấy tổng các "
                    f"dòng chủng loại, bỏ qua ô tổng.")
        elif total is not None:
            # Khai bằng ô tổng ⇒ bỏ bảng chủng loại cũ của ngày đó, tránh tổng lệch tổng các dòng.
            fields[total_key] = total
            fields.pop(table, None)

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
