"""Xuất Excel cho các bảng Thống kê (thu mua · tiêu thụ · tồn kho) — cột động theo bộ lọc.

Khác `unit_period_excel` (bám cứng mẫu Biểu (1)/(2)), file này dựng bảng từ danh sách cột
truyền vào nên dùng lại được cho mọi cách nhóm (đơn vị · khu vực · chủng loại · ngày).
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

Col = tuple[str, str, str]        # (khoá dữ liệu, tiêu đề, đơn vị tính)

PURCHASE_COLS: list[Col] = [
    ("qty_latex", "Sản lượng mủ nước", "tấn"),
    ("qty_cup", "Sản lượng mủ chén", "tấn"),
    ("qty_cup_raw", "Sản lượng mủ NL chưa cán vắt", "tấn"),
    ("qty_rss_pressed", "Sản lượng mủ NL đã cán vắt", "tấn"),
    ("qty_finished", "Sản lượng thành phẩm", "tấn"),
    ("qty_total", "Tổng sản lượng (theo bộ lọc)", "tấn"),
    ("price_latex_avg", "Đơn giá BQ mủ nước", "đồng/độ"),
    ("price_cup_avg", "Đơn giá BQ mủ chén", "đồng/độ"),
    ("price_cup_raw_avg", "Đơn giá BQ mủ NL chưa cán vắt", "đồng/kg"),
    ("price_rss_pressed_avg", "Đơn giá BQ mủ NL đã cán vắt", "đồng/kg"),
    ("price_finished_avg", "Đơn giá BQ thành phẩm", "triệu đ/tấn"),
    ("days", "Số ngày có số liệu", "ngày"),
    ("no_purchase_days", "Số ngày không tổ chức thu mua", "ngày"),
]

CONSUMPTION_COLS: list[Col] = [
    ("qty", "Tổng sản lượng tiêu thụ", "tấn"),
    ("qty_long_term", "HĐ dài hạn", "tấn"),
    ("qty_spot", "HĐ chuyến", "tấn"),
    ("qty_unknown_type", "HĐ chưa khai loại", "tấn"),
    ("qty_export", "XK / UTXK", "tấn"),
    ("qty_domestic", "Tiêu thụ trong nước", "tấn"),
    ("qty_internal", "Tiêu thụ nội bộ", "tấn"),
    ("revenue_ty", "Doanh thu", "tỷ đồng"),
    ("avg_price_trieu", "Giá bán bình quân", "triệu đ/tấn"),
    ("lines", "Số dòng bán", "dòng"),
]

CONSUMPTION_DETAIL_COLS: list[Col] = [
    ("as_of", "Ngày", ""), ("company", "Đơn vị", ""), ("source_label", "Nguồn mủ", ""),
    ("code", "Số HĐ/PL", ""), ("contract_label", "Loại HĐ", ""), ("channel_label", "Hình thức", ""),
    ("grade", "Chủng loại", ""), ("qty", "Số lượng", "tấn"), ("price", "Đơn giá", ""),
    ("ccy", "Loại tiền", ""), ("revenue_vnd", "Doanh thu", "đồng"),
    ("warehouse_date", "Ngày xuất kho", ""), ("invoice_date", "Ngày hoá đơn", ""),
]

STOCK_COLS: list[Col] = [
    ("as_of", "Ngày lấy số", ""),
    ("age_days", "Số cũ so với ngày chốt", "ngày"),
    ("not_warehoused", "Tồn thành phẩm chưa nhập kho", "tấn"),
    ("warehoused", "Tồn thành phẩm đã nhập kho", "tấn"),
    ("total", "Tổng tồn kho thành phẩm", "tấn"),
    ("signed_undelivered", "Đã ký HĐ chưa giao", "tấn"),
    ("tradable", "Tồn có thể giao dịch", "tấn"),
    ("material", "Tồn kho nguyên liệu (quy khô)", "tấn"),
]

GROUP_LABELS = {"company": "Đơn vị", "region": "Khu vực", "grade": "Chủng loại", "day": "Ngày",
                "material": "Loại mủ", "contract": "Loại HĐ", "channel": "Hình thức",
                "source": "Nguồn mủ", "none": "Chi tiết"}


def _head(ws, row: int, col: int, value: Any, *, bold: bool = True, size: int = 10) -> None:
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(bold=bold, size=size)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.fill = _HEAD_FILL
    c.border = _BORDER


def build_xlsx(*, title: str, period: str, note: str, group_by: str, columns: list[Col],
               rows: list[dict], totals: dict | None, label_key: str = "label",
               period_label: str = "Kỳ báo cáo") -> bytes:
    """Dựng .xlsx: tiêu đề + kỳ + ghi chú bộ lọc, bảng dữ liệu, dòng Tổng cộng (nếu có)."""
    wb = Workbook()
    ws = wb.active
    ws.title = GROUP_LABELS.get(group_by, "Thống kê")[:31]
    detail = group_by == "none"
    # Nhóm theo đơn vị thì kèm cột Khu vực (giống bảng trên web) để lọc/pivot lại trong Excel.
    lead: list[Col] = [] if detail else [(label_key, GROUP_LABELS.get(group_by, "Nhóm"), "")]
    if group_by == "company":
        lead = [("region", "Khu vực", ""), *lead]
    cols = lead + columns

    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=f"{period_label}: {period}").font = Font(bold=True)
    ws.cell(row=3, column=1, value=note).font = Font(italic=True, size=9, color="666666")
    for r in (1, 2, 3):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=max(2, min(len(cols), 8)))

    head, unit_row = 5, 6
    for i, (_, label, unit) in enumerate(cols, start=1):
        _head(ws, head, i, label)
        _head(ws, unit_row, i, unit, bold=False, size=8)

    r = unit_row + 1
    for row in rows:
        for i, (key, *_rest) in enumerate(cols, start=1):
            c = ws.cell(row=r, column=i, value=row.get(key))
            if isinstance(row.get(key), (int, float)):
                c.number_format = _NUM
            c.border = _BORDER
        r += 1

    if totals is not None and not detail:
        # Nhãn "Tổng cộng" đặt ở cột NHÓM (sau cột Khu vực nếu có) cho khớp bảng trên web.
        label_col = len(lead)
        for i in range(1, label_col + 1):
            c = ws.cell(row=r, column=i, value="Tổng cộng" if i == label_col else None)
            c.font = Font(bold=True)
            c.fill = _TOTAL_FILL
            c.border = _BORDER
        for i, (key, *_rest) in enumerate(cols[label_col:], start=label_col + 1):
            c = ws.cell(row=r, column=i, value=totals.get(key))
            c.number_format = _NUM
            c.font = Font(bold=True)
            c.fill = _TOTAL_FILL
            c.border = _BORDER

    ws.freeze_panes = ws.cell(row=unit_row + 1, column=2)
    ws.column_dimensions["A"].width = 26
    for i in range(2, len(cols) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
