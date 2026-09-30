"""Xuất Excel bảng Chỉ số điện · nước · số bành theo ngày (đầu vào = đúng phản hồi `/meters/daily`).

Mỗi chỉ số 4 cột: Đầu ngày · Cuối ngày · Tiêu thụ · Ghi chú (cờ thiếu số giải thích bằng lời, kèm
giờ lấy số thật) — file rời khỏi hệ thống vẫn tự nói được số nào là số đủ mốc 00:00. Cột suất tiêu
hao (kWh/bành, m³/bành) chỉ hiện khi nhà máy có đủ hai chỉ số tương ứng.
"""

from __future__ import annotations

import io
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_HEAD_FILL = PatternFill("solid", fgColor="D9E7D5")
_TOTAL_FILL = PatternFill("solid", fgColor="F2F2F2")
_FLAG_FILL = PatternFill("solid", fgColor="FFF4D6")      # thiếu số / đặt lại — cần lưu ý
_PROGRESS_FILL = PatternFill("solid", fgColor="E3EEF9")  # hôm nay, chưa trọn ngày — không phải lỗi
_THIN = Side(style="thin", color="9AA5A0")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

FLAG_LABELS = {
    "partial": "Thiếu mốc 00:00 — dùng số gần nhất trong ngày",
    "reset": "Số bị giảm trong ngày (đồng hồ bị đặt lại/đọc lỗi) — không tính tiêu thụ",
    "no_data": "Cả ngày không có số",
    "in_progress": "Đang trong ngày — cuối = số mới nhất",
}
_SUB = ("Đầu ngày", "Cuối ngày", "Tiêu thụ", "Ghi chú")
#: Cột suất tiêu hao → (tiêu đề, chỉ số tử số) — chỉ hiện khi nhà máy có cả chỉ số đó lẫn số bành.
_RATIOS = (("kwh_per_bale", "kWh / bành", "energy"), ("m3_per_bale", "m³ / bành", "water"))


def _ratio_cols(metrics: list[dict]) -> list[tuple[str, str]]:
    keys = {m["key"] for m in metrics}
    return [(k, label) for k, label, num in _RATIOS if num in keys and "bales" in keys]


def _fill(cell: dict) -> PatternFill | None:
    flag = cell.get("flag")
    return None if not flag else _PROGRESS_FILL if flag == "in_progress" else _FLAG_FILL


def _fmt_num(metric: str) -> str:
    return "#,##0" if metric == "bales" else "#,##0.000"


def _dmy(iso_day: str) -> str:
    return date.fromisoformat(iso_day).strftime("%d/%m/%Y")


def _hm(iso_ts: str | None) -> str:
    return datetime.fromisoformat(iso_ts).strftime("%H:%M %d/%m") if iso_ts else ""


def cell_note(cell: dict) -> str:
    """Cờ → lời giải thích; thiếu mốc thì ghi thêm giờ lấy số thật."""
    flag = cell.get("flag")
    if not flag:
        return ""
    note = FLAG_LABELS.get(flag, flag)
    if flag in ("partial", "in_progress", "reset") and cell.get("open_at"):
        note += f" (đầu {_hm(cell['open_at'])}, cuối {_hm(cell['close_at'])})"
    return note


def _put(ws, row: int, col: int, value, *, fmt: str | None = None, bold: bool = False,
         fill: PatternFill | None = None) -> None:
    c = ws.cell(row=row, column=col, value=value)
    c.border = _BORDER
    if fmt and isinstance(value, (int, float)):
        c.number_format = fmt
    if bold:
        c.font = Font(bold=True)
    if fill:
        c.fill = fill


def _header(ws, metrics: list[dict], head: int) -> int:
    """Hai dòng tiêu đề (nhóm chỉ số + cột con). Trả về số cột cuối cùng."""
    def h(r: int, c: int, v: str) -> None:
        cell = ws.cell(row=r, column=c, value=v)
        cell.font, cell.alignment = Font(bold=True), _CENTER
        cell.fill, cell.border = _HEAD_FILL, _BORDER

    h(head, 1, "Ngày")
    ws.merge_cells(start_row=head, start_column=1, end_row=head + 1, end_column=1)
    col = 2
    for m in metrics:
        h(head, col, f"{m['label']} ({m['unit']})")
        ws.merge_cells(start_row=head, start_column=col, end_row=head, end_column=col + 3)
        for i, sub in enumerate(_SUB):
            h(head + 1, col + i, sub)
        col += 4
    for _, label in _ratio_cols(metrics):
        h(head, col, label)
        ws.merge_cells(start_row=head, start_column=col, end_row=head + 1, end_column=col)
        col += 1
    return col - 1


def build_xlsx(report: dict) -> bytes:
    metrics = report["metrics"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Chỉ số theo ngày"
    ws.cell(row=1, column=1, value=f"CHỈ SỐ ĐIỆN · NƯỚC · SỐ BÀNH — {report['factory']['name']}"
            ).font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=(f"Kỳ: {_dmy(report['date_from'])} → {_dmy(report['date_to'])}"
                                    f" · Lấy số lúc {_hm(report['fetched_at'])}")).font = Font(bold=True)
    ws.cell(row=3, column=1, value="Tiêu thụ ngày = chỉ số lúc 00:00 hôm sau − chỉ số lúc 00:00 "
            "(nguồn: SCADA/Historian). Ô tô vàng = thiếu số hoặc số bị giảm, xem cột Ghi chú; "
            "ô tô xanh = hôm nay, chưa trọn ngày."
            ).font = Font(italic=True, size=9, color="666666")
    head = 5
    last_col = _header(ws, metrics, head)
    r = head + 2
    for row in report["rows"]:
        _put(ws, r, 1, date.fromisoformat(row["date"]))
        ws.cell(row=r, column=1).number_format = "dd/mm/yyyy"
        col = 2
        for m in metrics:
            cell, fmt = row[m["key"]], _fmt_num(m["key"])
            fill = _fill(cell)
            for i, key in enumerate(("open", "close", "used")):
                _put(ws, r, col + i, cell.get(key), fmt=fmt, fill=fill)
            _put(ws, r, col + 3, cell_note(cell), fill=fill)
            col += 4
        for j, (key, _) in enumerate(_ratio_cols(metrics)):
            _put(ws, r, col + j, row.get(key), fmt="#,##0.000")
        r += 1
    _footer(ws, report, r)
    ws.freeze_panes = ws.cell(row=head + 2, column=2)
    ws.column_dimensions["A"].width = 13
    for i in range(2, last_col + 1):
        is_note = i <= 1 + 4 * len(metrics) and (i - 1) % 4 == 0
        ws.column_dimensions[get_column_letter(i)].width = 34 if is_note else 14
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _footer(ws, report: dict, r: int) -> None:
    """3 dòng tổng hợp: Tổng cộng (mọi ngày có số) · Bình quân/ngày (chỉ ngày đủ số) · Chỉ số mới
    nhất (+ suất tiêu hao cả kỳ)."""
    metrics, summ = report["metrics"], report["summary"]
    lines = (("Tổng cộng", "total", 2), ("Bình quân / ngày", "avg_per_day", 2),
             ("Chỉ số mới nhất", "latest", 1))
    for i, (label, key, pos) in enumerate(lines):
        _put(ws, r + i, 1, label, bold=True, fill=_TOTAL_FILL)
        col = 2
        for m in metrics:
            s = summ[m["key"]]
            for j in range(4):
                val = s.get(key) if j == pos else None
                if j == 3 and key == "latest":
                    val = f"lúc {_hm(s.get('latest_at'))}" if s.get("latest_at") else None
                elif j == 3 and key == "total":
                    val = f"{s.get('days_with_data', 0)} ngày có số"
                elif j == 3 and key == "avg_per_day":
                    val = f"{s.get('days_complete', 0)} ngày đủ số"
                _put(ws, r + i, col + j, val, fmt=_fmt_num(m["key"]), bold=True, fill=_TOTAL_FILL)
            col += 4
        inten = report.get("intensity") or {}
        for j, (k, _) in enumerate(_ratio_cols(metrics)):
            val = inten.get(k) if key == "total" else None
            _put(ws, r + i, col + j, val, fmt="#,##0.000", bold=True, fill=_TOTAL_FILL)
