"""Xuất Excel "Phiếu báo giá mủ thị trường" — 1 phiếu/ngày, dựng theo mẫu Ban TTKD.

Bố cục: tiêu đề + tỷ giá VCB → Mục 1–4 (giá SVR theo chủng loại) → Mục 5 (đề xuất mua từ khách hàng)
→ Mục 6 (giá mủ tư nhân + giá thành SVR 3L) → Ghi chú chung → Bảng đối chiếu.

Đọc từ phiếu ĐÃ LƯU (DB), không nhận số liệu từ trình duyệt — file luôn khớp bản đang lưu. Số tự tính
(thành tiền, giá thành, chênh lệch) ghi thành GIÁ TRỊ chứ không phải công thức: công thức do openpyxl ghi
không kèm kết quả nên ô sẽ trống khi xem trước (Zalo/Quick Look/điện thoại) hoặc đọc bằng pandas.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

from openpyxl import Workbook
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from app.core.market_meta import MARKET_QUOTE_GRADES
from app.services import market_quote_excel_extra as extra
from app.services import market_quote_excel_style as st

# (khoá trong phiếu, tiêu đề mục, tiêu đề cột đơn giá). Mục 2 là USD/tấn FOB (số nhập cỡ 2.000–2.500).
_PRICE_SECTIONS = (
    ("domestic_private", "MỤC 1. GIÁ NỘI ĐỊA — HÀNG TƯ NHÂN   (VNĐ/tấn)", "ĐƠN GIÁ (ĐỒNG/TẤN)"),
    ("domestic_export", "MỤC 2. GIÁ XUẤT KHẨU — HÀNG TƯ NHÂN   (USD/tấn FOB)", "ĐƠN GIÁ (USD/TẤN)"),
    ("export_vrg", "MỤC 3. GIÁ XUẤT KHẨU — HÀNG VRG   (USD/tấn FOB)", "ĐƠN GIÁ (USD/TẤN)"),
    ("domestic_vrg", "MỤC 4. GIÁ NỘI ĐỊA — HÀNG VRG   (VNĐ/tấn)", "ĐƠN GIÁ (ĐỒNG/TẤN)"),
)


def _dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def _title_block(ws: Worksheet, q: dict[str, Any]) -> None:
    ws.row_dimensions[1].height = 20.25
    st.put(ws, "A1", "PHIẾU BÁO GIÁ MỦ THỊ TRƯỜNG", f=st.font(16, bold=True, color=st.GREEN))
    st.put(ws, "A2", f"Phiếu {_dmy(q['as_of'])}", f=st.font(9, color=st.MUTED))
    st.label_cell(ws, "A4", "Ngày phiếu")
    st.input_cell(ws, "B4", date.fromisoformat(q["as_of"]), fmt=st.FMT_DATE)
    fx = q.get("fx") or {}
    for r, (label, key) in enumerate((("Tỷ giá VCB – Mua TM", "mua_tm"), ("Tỷ giá VCB – Mua CK", "mua_ck"),
                                      ("Tỷ giá VCB – Bán", "ban")), start=5):
        st.label_cell(ws, f"A{r}", label)
        st.input_cell(ws, f"B{r}", fx.get(key), fmt=st.FMT_INT)
    st.put(ws, "C5", "VNĐ/USD – nguồn Vietcombank", f=st.font(9, color=st.MUTED))


def _price_section(ws: Worksheet, row: int, sec: dict[str, Any], title: str, price_header: str) -> int:
    """Mục 1–4: 6 chủng loại × (bao bì · đơn vị vận chuyển · tình trạng · đơn giá) + ghi chú. → dòng bắt đầu mục kế."""
    st.bar(ws, row, title, last_col="E")
    st.header(ws, row + 1, {"A": "CHỦNG LOẠI", "B": "BAO BÌ ĐÓNG GÓI", "C": "ĐƠN VỊ VẬN CHUYỂN", "D": "TÌNH TRẠNG",
                            "E": price_header})
    for i, grade in enumerate(MARKET_QUOTE_GRADES):
        r = row + 2 + i
        st.label_cell(ws, f"A{r}", grade)
        st.input_cell(ws, f"B{r}", (sec.get("packaging") or {}).get(grade) or None)
        st.input_cell(ws, f"C{r}", (sec.get("shipping") or {}).get(grade) or None)
        st.input_cell(ws, f"D{r}", (sec.get("status") or {}).get(grade) or None)
        st.input_cell(ws, f"E{r}", (sec.get("prices") or {}).get(grade), fmt=st.FMT_INT)
    note_at = row + 2 + len(MARKET_QUOTE_GRADES)
    st.note_row(ws, note_at, "Ghi chú:", sec.get("note") or "")
    return note_at + 2


def build_xlsx(quote: dict[str, Any], private_units: list[str]) -> bytes:
    """Phiếu đã lưu (dict như `market_quote_repo.get_quote`) + danh mục đơn vị tư nhân (thứ tự hiển thị) → bytes .xlsx."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Bao gia mu"
    ws.sheet_view.showGridLines = False
    for col, width in st.COL_WIDTHS.items():
        ws.column_dimensions[col].width = width
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

    _title_block(ws, quote)
    row = 9
    for key, title, price_header in _PRICE_SECTIONS:
        row = _price_section(ws, row, quote.get(key) or {}, title, price_header)
    row = extra.proposal_section(ws, row, quote.get("customer_proposal") or {})
    row = extra.private_section(ws, row, quote.get("private_prices") or {}, quote.get("private_processing_cost"),
                                private_units)
    st.note_row(ws, row, "Ghi chú / Cảnh báo:", quote.get("footer") or "", last_col=st.LAST_COL)
    extra.comparison_section(ws, row + 2, quote)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
