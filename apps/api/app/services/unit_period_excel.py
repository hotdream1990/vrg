"""Xuất Excel báo cáo theo kỳ — bám đúng cột của 2 sheet mẫu trong
"Biểu mẫu-Báo cáo tuần-năm 2026": "(2) Biểu mẫu-Thu mua" và "(1) Biểu mẫu Tiêu thụ -Tồn kho".

Mỗi đơn vị 1 dòng (kèm Khu vực), cuối bảng là dòng Tổng cộng. Số liệu do
`unit_period_report.period_report()` tính sẵn theo quy tắc cộng dồn / thời điểm / bình quân.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_HEAD_FILL = PatternFill("solid", fgColor="D9E7D5")
_TOTAL_FILL = PatternFill("solid", fgColor="F2F2F2")
_THIN = Side(style="thin", color="9AA5A0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_NUM = "#,##0.00"

# (khoá dữ liệu, tiêu đề cột, ghi chú công thức của mẫu)
_PURCHASE_COLS: list[tuple[str, str, str]] = [
    ("latex_wet", "Sản lượng thu mua mủ nước", "cộng dồn"),
    ("coagulum", "Sản lượng thu mua mủ chén", "cộng dồn"),
    ("total_purchase", "Tổng sản lượng thu mua", "= mủ nước + mủ chén"),
    ("price_latex_avg", "Giá thu mua mủ nước BQ", "bình quân gia quyền"),
    ("price_cup_avg", "Giá thu mua mủ chén BQ", "bình quân gia quyền"),
    ("plan_tonnes", "Kế hoạch thu mua", "số liệu năm"),
    ("pct_plan", "% thực hiện kế hoạch", "= thực hiện / kế hoạch"),
    ("consumption", "Sản lượng tiêu thụ mủ thu mua", "cộng dồn"),
    ("revenue_ty", "Doanh thu tiêu thụ mủ thu mua", "cộng dồn"),
    ("avg_sell_price", "Giá bán bình quân", "= doanh thu / sản lượng"),
]
_PURCHASE_UNITS = ["tấn", "tấn", "tấn", "đồng/độ TSC", "đồng/độ TSC", "tấn", "%",
                   "tấn", "tỷ đồng", "triệu đ/tấn"]

_CONSUMPTION_COLS: list[tuple[str, str, str]] = [
    ("signed_lt_tonnes", "Tổng SL đã ký HĐ dài hạn", "số liệu năm"),
    ("lt_export", "HĐ dài hạn — XK/UTXK", "cộng dồn"),
    ("lt_domestic", "HĐ dài hạn — Nội tiêu", "cộng dồn"),
    ("spot_export", "HĐ chuyến — XK/UTXK", "cộng dồn"),
    ("spot_domestic", "HĐ chuyến — Nội tiêu", "cộng dồn"),
    ("total_consumption", "Tổng tiêu thụ", "= tổng 4 cột trên"),
    ("export_total", "Tổng XK/UTXK", "= dài hạn + chuyến"),
    ("domestic_total", "Tổng Nội tiêu", "= dài hạn + chuyến"),
    ("revenue_ty", "Doanh thu cao su", "cộng dồn"),
    ("avg_sell_price", "Giá bán bình quân", "= doanh thu / tiêu thụ"),
    ("stock_finished", "Tồn kho thành phẩm", "thời điểm"),
    ("stock_not_warehoused", "Trong đó chế biến chưa nhập kho", "thời điểm"),
    ("stock_warehoused", "Trong đó đã nhập kho", "thời điểm"),
    ("stock_finished_hd", "Đã ký hợp đồng chưa giao", "thời điểm"),
    ("stock_no_hd", "Thành phẩm chưa có hợp đồng", "= tồn kho − đã có HĐ"),
]
_CONSUMPTION_UNITS = ["tấn", "tấn", "tấn", "tấn", "tấn", "tấn", "tấn", "tấn",
                      "tỷ đồng", "triệu đ/tấn", "tấn", "tấn", "tấn"]
_TAIL_COLS: list[tuple[str, str, str]] = [
    ("stock_material", "Tồn kho nguyên liệu chưa sản xuất", "thời điểm"),
    ("carry_lt_tonnes", "HĐ dài hạn năm trước chuyển sang", "số liệu năm"),
    ("carry_spot_tonnes", "HĐ chuyến năm trước chuyển sang", "số liệu năm"),
]

_TITLE = {
    "purchase": ("BÁO CÁO THU MUA", "Về công tác Thu mua và Tiêu thụ mủ nguyên liệu"),
    "consumption": ("BÁO CÁO TIÊU THỤ - TỒN KHO", "Về công tác Tiêu thụ - Tồn kho mủ cao su"),
}
# Chỉ tiêu KHÔNG được cộng ở dòng Tổng cộng (giá / tỷ lệ → tính lại hoặc bỏ trống).
_NO_SUM = {"price_latex_avg", "price_cup_avg", "pct_plan", "avg_sell_price"}


def _columns(kind: str, grades: list[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Cột dữ liệu + đơn vị tính. Biểu tiêu thụ chèn 9 chủng loại tồn kho vào giữa."""
    if kind == "purchase":
        return list(_PURCHASE_COLS), list(_PURCHASE_UNITS)
    cols = list(_CONSUMPTION_COLS)
    units = list(_CONSUMPTION_UNITS)
    for g in grades:                       # 13.1–13.8: tồn kho chưa HĐ theo chủng loại
        cols.append((f"grade::{g}", g, "thời điểm"))
        units.append("tấn")
    cols += _TAIL_COLS
    units += ["tấn", "tấn", "tấn"]
    return cols, units


def _value(row: dict, key: str) -> Any:
    if key.startswith("grade::"):
        return (row.get("stock_by_grade") or {}).get(key[7:])
    return row.get(key)


def build_period_xlsx(report: dict) -> bytes:
    """Dựng file .xlsx từ kết quả `period_report()` → bytes để trả về client."""
    kind = report["kind"]
    grades: list[str] = report.get("grades") or []
    cols, units = _columns(kind, grades)
    rows: list[dict] = report.get("rows") or []

    wb = Workbook()
    ws = wb.active
    ws.title = "Thu mua" if kind == "purchase" else "Tiêu thụ - Tồn kho"

    title, sub = _TITLE[kind]
    ncol = 2 + len(cols)
    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=sub).font = Font(italic=True)
    ws.cell(row=3, column=1,
            value=f"Kỳ báo cáo: {report['date_from']} → {report['date_to']}").font = Font(bold=True)
    for r in (1, 2, 3):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=min(ncol, 8))

    head, unit_row, formula_row = 5, 6, 7
    headers = ["Khu vực", "Đơn vị"] + [c[1] for c in cols]
    all_units = ["", ""] + units
    all_formulas = ["", ""] + [c[2] for c in cols]
    for i, (h, u, f) in enumerate(zip(headers, all_units, all_formulas), start=1):
        for r, v, bold in ((head, h, True), (unit_row, u, False), (formula_row, f, False)):
            cell = ws.cell(row=r, column=i, value=v)
            cell.font = Font(bold=bold, size=10 if r == head else 8,
                             italic=(r == formula_row), color="000000" if r != formula_row else "666666")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.fill = _HEAD_FILL
            cell.border = _BORDER

    r = formula_row + 1
    for row in rows:
        ws.cell(row=r, column=1, value=row.get("region") or "").border = _BORDER
        ws.cell(row=r, column=2, value=row.get("company")).border = _BORDER
        for i, (key, _, _) in enumerate(cols, start=3):
            c = ws.cell(row=r, column=i, value=_value(row, key))
            c.number_format = _NUM
            c.border = _BORDER
        r += 1

    # Dòng Tổng cộng: chỉ cộng chỉ tiêu dòng chảy/tồn kho; giá & % bỏ trống (không cộng được).
    ws.cell(row=r, column=2, value="Tổng cộng").font = Font(bold=True)
    ws.cell(row=r, column=1).fill = _TOTAL_FILL
    ws.cell(row=r, column=2).fill = _TOTAL_FILL
    for i, (key, _, _) in enumerate(cols, start=3):
        total = None
        if key not in _NO_SUM:
            vals = [v for v in (_value(x, key) for x in rows) if isinstance(v, (int, float))]
            total = sum(vals) if vals else None
        c = ws.cell(row=r, column=i, value=total)
        c.number_format = _NUM
        c.font = Font(bold=True)
        c.fill = _TOTAL_FILL
        c.border = _BORDER

    ws.freeze_panes = ws.cell(row=formula_row + 1, column=3)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 24
    for i in range(3, ncol + 1):
        ws.column_dimensions[get_column_letter(i)].width = 15

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
