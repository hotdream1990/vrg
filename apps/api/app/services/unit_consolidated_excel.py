"""Dựng file Excel "TỔNG HỢP BÁO CÁO SẢN XUẤT - TỒN KHO - TIÊU THỤ" gửi Tập đoàn.

Số liệu lấy nguyên từ `unit_period_report.period_report("consumption", 01/01 → ngày chốt)` — cùng
nguồn với màn Báo cáo theo kỳ nên hai chỗ không thể lệch. Khuôn biểu (cột, nhóm chủng loại, tiêu
đề) nằm ở `unit_consolidated_layout`.

Dòng đơn vị đi theo khu vực; ĐƠN VỊ ĐÃ SÁP NHẬP vẫn có dòng riêng (để trống + ghi chú) đúng như
file mẫu Ban TTKD đang dùng — số liệu của họ đã gộp vào đơn vị nhận. Dòng khu vực và dòng TẬP ĐOÀN
là CÔNG THỨC `SUM`, không phải số chết: sửa một ô là tổng chạy theo.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from app.services import member_unit_repo, unit_period_report
from app.services.unit_consolidated_layout import (
    _GROUP_FILL, _GRADE_COLS, _SUM_COLS, _TOTAL_FILL, _VALUE_COLS, _WIDTHS, NOTES, REGION_ORDER,
    _OTHER_REGION, _ROMAN, grade_cells, header, row_formulas, write,
)

_FIRST_ROW = 6          # dòng TẬP ĐOÀN (ngay dưới 5 dòng tiêu đề)


def _dmy(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else ""


def _unit_note(u: dict[str, Any]) -> str:
    """Ghi chú của dòng đơn vị — hiện chỉ dùng cho đơn vị đã sáp nhập (số liệu gộp vào nơi khác)."""
    if not u.get("merged_into"):
        return ""
    since = _dmy(str(u["merged_at"])) if u.get("merged_at") else ""
    return f"Đã hợp nhất số liệu vào {u['merged_into']}" + (f" từ {since}" if since else "")


def _units_by_region(units: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Khu vực → danh sách đơn vị, đúng thứ tự biểu. Đơn vị chưa gán khu vực dồn vào khối cuối."""
    groups: dict[str, list[dict[str, Any]]] = {r: [] for r in REGION_ORDER}
    for u in units:
        groups.setdefault(u.get("region") or _OTHER_REGION, []).append(u)
    ordered = [(r, groups[r]) for r in REGION_ORDER if groups.get(r)]
    ordered += [(r, us) for r, us in groups.items() if r not in REGION_ORDER and us]
    return ordered


def _write_unit(ws, r: int, no: int, seq: int, u: dict[str, Any], data: dict[str, Any] | None) -> None:
    write(ws, r, "A", no)
    write(ws, r, "B", seq)
    write(ws, r, "C", u["name"])
    for col, key in _VALUE_COLS.items():
        write(ws, r, col, (data or {}).get(key))
    for col, value in zip(_GRADE_COLS, grade_cells(data or {}), strict=True):
        write(ws, r, col, value)
    for col, formula in row_formulas(r).items():
        write(ws, r, col, formula)
    note = _unit_note(u)
    if note:
        write(ws, r, "AG", note)


def _write_total(ws, r: int, source_rows: list[int], fill) -> None:
    """Dòng tổng (khu vực hoặc Tập đoàn): cộng đúng các dòng con, cột suy ra vẫn là công thức."""
    for col in _SUM_COLS:
        formula = "=" + "+".join(f"{col}{i}" for i in source_rows) if source_rows else None
        write(ws, r, col, formula, bold=True, fill=fill)
    for col, formula in row_formulas(r).items():
        write(ws, r, col, formula, bold=True, fill=fill)
    for col in ("D", "E", "F", "AG"):
        write(ws, r, col, None, bold=True, fill=fill)


def _write_notes(ws, r: int) -> int:
    """Khối ghi chú cuối bảng (giữ nguyên tinh thần của mẫu, bổ sung cách tính cột chủng loại)."""
    write(ws, r + 1, "B", "Ghi chú", bold=True, fmt="General")
    for i, text in enumerate(NOTES, start=2):
        write(ws, r + i, "B", "*", fmt="General")
        ws.merge_cells(start_row=r + i, start_column=3, end_row=r + i, end_column=24)
        write(ws, r + i, "C", text, fmt="General")
    return r + len(NOTES) + 1


def build(as_of: str, report: dict[str, Any] | None = None) -> bytes:
    """`as_of` = ngày chốt số liệu (thứ Năm hàng tuần). Trả bytes .xlsx."""
    year = int(as_of[:4])
    report = report or unit_period_report.period_report(
        "consumption", f"{year}-01-01", as_of)
    data = {r["company"]: r for r in report.get("rows") or []}
    units = member_unit_repo.list_units(include_inactive=True)

    wb = Workbook()
    ws = wb.active
    ws.title = f"TT&TK ({as_of[8:10]}.{as_of[5:7]})"
    header(ws, as_of, year)

    row = _FIRST_ROW + 1            # dòng 6 dành cho TẬP ĐOÀN, viết sau khi biết các dòng khu vực
    region_rows: list[int] = []
    seq = 0
    for i, (region, members) in enumerate(_units_by_region(units)):
        region_row, first = row, row + 1
        region_rows.append(region_row)
        row += 1
        for no, u in enumerate(members, start=1):
            seq += 1
            _write_unit(ws, row, no, seq, u, data.get(u["name"]))
            row += 1
        _write_total(ws, region_row, list(range(first, row)), _GROUP_FILL)
        write(ws, region_row, "B", _ROMAN[i] if i < len(_ROMAN) else str(i + 1),
              bold=True, fill=_GROUP_FILL)
        write(ws, region_row, "C", region, bold=True, fill=_GROUP_FILL, fmt="General")
        write(ws, region_row, "A", None, bold=True, fill=_GROUP_FILL)

    _write_total(ws, _FIRST_ROW, region_rows, _TOTAL_FILL)
    ws.merge_cells(f"A{_FIRST_ROW}:C{_FIRST_ROW}")
    write(ws, _FIRST_ROW, "A", "TẬP ĐOÀN", bold=True, fill=_TOTAL_FILL, fmt="General")
    _write_notes(ws, row)

    for col, width in _WIDTHS.items():
        ws.column_dimensions[col].width = width
    for col in _GRADE_COLS:
        ws.column_dimensions[col].width = 10
    ws.freeze_panes = f"D{_FIRST_ROW}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def file_name(as_of: str) -> str:
    """Tên file tải về — bám cách đặt tên của Ban TTKD (tuần + ngày chốt)."""
    return f"tong-hop-bao-cao-tieu-thu-ton-kho-{as_of}.xlsx"


__all__ = ["build", "file_name", "get_column_letter"]
