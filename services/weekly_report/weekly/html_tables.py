"""Bảng III.1 / III.2 / III.3 + "Ghi chú:" dưới bảng cho PDF báo cáo tuần.

- MỌI kỳ (1–3 tuần) bám mẫu tuần 35–36: mỗi tuần 1 cột, mỗi cặp 1 cột "+/- (T35/T34)" số có dấu in
  đậm "+35,4"/"-26,3" (0 → "0"), không cột %; giá 1 số lẻ. Nhiều cột → co chữ để vừa A4.
- Số kiểu VN: 2.740,5 (chấm nghìn, phẩy thập phân), làm tròn nửa LÊN. Giá thiếu/0 → "N/A".
"""

from __future__ import annotations

import html
from decimal import ROUND_HALF_UP, Decimal

from .models import TableRow, WeeklyReportData
from .text_format import fmt_inline

# Khung dòng khi chưa có dữ liệu (vẫn in bảng N/A như v1)
_EXCHANGE_SKELETON = [("OSE", "RSS3"), ("SHANGHAI", "RSS3"), ("SGX", "RSS3"), ("SGX", "TSR20"),
                      ("MRE", "SMR CV"), ("MRE", "SMR20"), ("MRE", "LATEX")]
_PHYS_SKELETON = [(None, "RSS3"), (None, "STR20"), (None, "SMR20"), (None, "LATEX")]


# ── Định dạng số ──
def _vn(x: float, dec: int = 1) -> str:
    """abs(x) → '2.740,5' (dec chữ số thập phân, nửa LÊN). Không kèm dấu."""
    q = Decimal(str(abs(x))).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    s = f"{q:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _is_zero(x: float, dec: int) -> bool:
    return _vn(x, dec).strip("0.,") == ""


def _price(x: float | None, dec: int = 1) -> str:
    return _vn(x, dec) if x else "N/A"  # None hoặc 0 (No Trading)


def _signed(x: float | None, dec: int = 1) -> str:
    """+/- mẫu 35–36: '+35,4' / '-26,3' / '0', in đậm."""
    if x is None:
        return ""
    if _is_zero(x, dec):
        return "<b>0</b>"
    return f"<b>{'-' if x < 0 else '+'}{_vn(x, dec)}</b>"


def _at(seq: list, i: int):
    return seq[i] if 0 <= i < len(seq) else None


# ── Khung chung ──
def _density(n_weeks: int) -> str:
    """Lớp co chữ theo số cột tuần (tối đa 4 cột tuần + 3 cột +/- vừa A4 lề 3cm/2cm)."""
    return "tw4" if n_weeks >= 4 else "tw3" if n_weeks == 3 else ""


def _rows(rows: list[TableRow], skeleton: list, n: int) -> list[TableRow]:
    return rows or [TableRow(e, g, [None] * n) for e, g in skeleton]


def _week_label(d: WeeklyReportData, i: int) -> str:
    """Xuống dòng trước '(ngày)' cho cột hẹp gọn gàng (như mẫu)."""
    w = _at(d.weeks, i)
    return html.escape(w.label).replace(" (", "<br>(", 1) if w else ""


def _pair_label(d: WeeklyReportData, i: int, prefix: str, sep: str = " ") -> str:
    return f"{prefix}{sep}(T{d.weeks[i + 1].week_no}/T{d.weeks[i].week_no})"


def _group_by_exchange(rows: list[TableRow]) -> list[list[TableRow]]:
    groups: list[list[TableRow]] = []
    for r in rows:
        if groups and groups[-1][0].exchange == r.exchange:
            groups[-1].append(r)
        else:
            groups.append([r])
    return groups


def _cells(d: WeeklyReportData, r: TableRow) -> str:
    """Các ô số của 1 dòng (sau cột Sàn/Sản phẩm)."""
    n = len(d.weeks)
    prices = "".join(f"<td class='r'>{_price(_at(r.values, i), 1)}</td>" for i in range(n))
    chg = "".join(f"<td class='r'>{_signed(_at(r.changes, i))}</td>" for i in range(n - 1))
    return prices + chg


def _head_cols(d: WeeklyReportData) -> str:
    n = len(d.weeks)
    return ("".join(f"<th>{_week_label(d, i)}</th>" for i in range(n))
            + "".join(f"<th>{_pair_label(d, i, '+/-', '<br>')}</th>" for i in range(n - 1)))


# ── Bảng III.1 — Giá sàn quốc tế ──
def exchange_table(d: WeeklyReportData) -> str:
    head = f"<thead><tr><th class='nw'>Sàn</th><th class='nw'>Sản phẩm</th>{_head_cols(d)}</tr></thead>"
    body = ""
    for grp in _group_by_exchange(_rows(d.exchange_rows, _EXCHANGE_SKELETON, len(d.weeks))):
        for j, r in enumerate(grp):
            exc = html.escape(r.exchange or "")
            lead = f"<td class='c b' rowspan='{len(grp)}'>{exc}</td>" if j == 0 else ""
            body += f"<tr>{lead}<td class='c'>{html.escape(r.grade)}</td>{_cells(d, r)}</tr>"
    return f"<table class='{_density(len(d.weeks))}'>{head}<tbody>{body}</tbody></table>"


# ── Bảng III.2 — Giá giao ngay ──
def physical_table(d: WeeklyReportData) -> str:
    head = f"<thead><tr><th class='nw'>Sản phẩm</th>{_head_cols(d)}</tr></thead>"
    body = "".join(
        f"<tr><td class='c'>{html.escape(r.grade)}</td>{_cells(d, r)}</tr>"
        for r in _rows(d.physical_rows, _PHYS_SKELETON, len(d.weeks))
    )
    return f"<table class='{_density(len(d.weeks))}'>{head}<tbody>{body}</tbody></table>"


# ── Bảng III.3 — Mủ nước (chỉ in khi có số liệu hoặc nhận định) ──
def has_latex(d: WeeklyReportData) -> bool:
    return any(b and str(b).strip() for b in d.latex_bands) or any(
        s and s.strip() for s in d.latex_notes)


def latex_table(d: WeeklyReportData) -> str:
    n = len(d.weeks)
    weeks = "".join(f"<th>Tuần {w.week_no}</th>" for w in d.weeks)
    chg_head = "".join(f"<th>{_pair_label(d, i, 'Biến động', '<br>')}</th>" for i in range(n - 1))
    bands = "".join(f"<td class='c'>{html.escape(_at(d.latex_bands, i) or 'N/A')}</td>"
                    for i in range(n))
    chg = "".join(f"<td class='c'>{html.escape(_at(d.latex_changes, i) or '')}</td>"
                  for i in range(max(n - 1, 1)))
    return (f"<table class='{_density(n)}'><thead><tr><th>Sản phẩm</th>{weeks}{chg_head}</tr>"
            f"</thead><tbody><tr><td class='c'>Mủ nước</td>{bands}{chg}</tr></tbody></table>")


# ── "Ghi chú:" dưới bảng — thiếu giá (auto) trước, ghi chú tay sau ──
def table_notes(gaps: list[str], notes: list[str]) -> str:
    lines = [s.strip() for s in [*gaps, *notes] if s and s.strip()]
    if not lines:
        return ""
    items = "".join(
        f"<p class='tn'>- {fmt_inline(s[1:].strip() if s.startswith('-') else s)}</p>"
        for s in lines
    )
    return f"<div class='tnote'><p class='tn-h'><b><i>Ghi chú:</i></b></p>{items}</div>"
