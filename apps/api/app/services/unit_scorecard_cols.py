"""Bộ CỘT của màn "Chỉ số đơn vị" — mỗi tab một danh sách chỉ số (dữ liệu thuần, không tính toán).

Mỗi cột khai `src` (bảng thống kê nguồn) + `field` (tên trường trong bảng đó) nên một tab gom được
nhiều nguồn mà không sợ trùng tên trường: tab Tổng quan vừa lấy `qty` của Tiêu thụ vừa lấy
`qty_total` của Thu mua. Tính toán nằm ở `unit_scorecard.py`, ở đây chỉ mô tả.

`compare=True` = chỉ số CỘNG DỒN theo kỳ nên so được với kỳ khác. Giá bình quân, %, ảnh chụp tồn
kho và các số thời điểm đều để False — so hai con số bình quân của hai kỳ khác rổ sản lượng là
khập khiễng, và tồn kho vốn không có "kỳ" để so.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import PURCHASE_PRICE_UNIT

Col = dict[str, Any]

LATEX_PRICE_UNIT = PURCHASE_PRICE_UNIT["purchase"]
CUP_PRICE_UNIT = PURCHASE_PRICE_UNIT["purchase_cup"]
LACE_PRICE_UNIT = PURCHASE_PRICE_UNIT["purchase_lace"]


def _c(key: str, label: str, unit: str, src: str, field: str, *, note: str = "",
       compare: bool = False) -> Col:
    return {"key": key, "label": label, "unit": unit, "src": src, "field": field,
            "note": note, "compare": compare}


#: Tổng quan — mỗi nhóm số liệu lấy vài chỉ số cốt lõi, đủ nhìn ra đơn vị nào đang lệch.
OVERVIEW: list[Col] = [
    _c("pur_material", "Thu mua mủ nguyên liệu", "tấn", "purchase", "qty_material",
       note="cộng dồn", compare=True),
    _c("pur_plan_pct", "% thực hiện KH thu mua", "%", "purchase", "pct_plan",
       note="Σ thực hiện ÷ Σ kế hoạch"),
    _c("pur_price_latex", "Giá mủ nước BQ", LATEX_PRICE_UNIT, "purchase", "price_latex_avg",
       note="BQ gia quyền"),
    _c("con_qty", "Tiêu thụ", "tấn", "consumption", "qty", note="cộng dồn", compare=True),
    _c("con_revenue", "Doanh thu", "tỷ đồng", "consumption", "revenue_ty",
       note="cộng dồn", compare=True),
    _c("con_price", "Giá bán BQ", "triệu đ/tấn", "consumption", "avg_price_trieu",
       note="BQ gia quyền"),
    _c("stk_total", "Tồn kho thành phẩm", "tấn", "stock", "total", note="thời điểm"),
    _c("stk_signed", "Đã ký HĐ chưa giao", "tấn quy khô", "stock", "signed_undelivered",
       note="nằm trong tồn kho"),
    _c("sta_rate", "Tỷ lệ nộp báo cáo", "%", "status", "rate",
       note="Σ ngày đã nộp ÷ Σ ngày phải nộp"),
]

PURCHASE: list[Col] = [
    _c("qty_latex", "SL mủ nước", "tấn", "purchase", "qty_latex", note="cộng dồn", compare=True),
    _c("qty_cup", "SL mủ chén", "tấn", "purchase", "qty_cup", note="cộng dồn", compare=True),
    _c("qty_lace", "SL mủ dây", "tấn", "purchase", "qty_lace", note="cộng dồn", compare=True),
    _c("qty_finished", "SL thành phẩm", "tấn", "purchase", "qty_finished",
       note="cộng dồn", compare=True),
    _c("qty_material", "TỔNG mủ nguyên liệu", "tấn", "purchase", "qty_material",
       note="nước + chén + dây", compare=True),
    _c("qty_total", "Tổng SL thu mua", "tấn", "purchase", "qty_total",
       note="gồm cả thành phẩm", compare=True),
    _c("plan_tonnes", "Kế hoạch năm", "tấn", "purchase", "plan_tonnes", note="chỉ tiêu năm"),
    _c("pct_plan", "% thực hiện KH", "%", "purchase", "pct_plan", note="Σ TH ÷ Σ KH"),
    _c("price_latex_avg", "Giá mủ nước BQ", LATEX_PRICE_UNIT, "purchase", "price_latex_avg",
       note="BQ gia quyền"),
    _c("price_cup_avg", "Giá mủ chén BQ", CUP_PRICE_UNIT, "purchase", "price_cup_avg",
       note="BQ gia quyền"),
    _c("price_lace_avg", "Giá mủ dây BQ", LACE_PRICE_UNIT, "purchase", "price_lace_avg",
       note="BQ gia quyền"),
    _c("price_finished_avg", "Giá thành phẩm BQ", "triệu đ/tấn", "purchase",
       "price_finished_avg", note="BQ gia quyền"),
    _c("days", "Số ngày có số liệu", "ngày", "purchase", "days"),
    _c("no_purchase_days", "Ngày không tổ chức mua", "ngày", "purchase", "no_purchase_days"),
]

CONSUMPTION: list[Col] = [
    _c("qty", "Tổng tiêu thụ", "tấn", "consumption", "qty", note="cộng dồn", compare=True),
    _c("qty_long_term", "HĐ dài hạn", "tấn", "consumption", "qty_long_term", compare=True),
    _c("qty_spot", "HĐ chuyến", "tấn", "consumption", "qty_spot", compare=True),
    _c("qty_principle", "HĐ nguyên tắc", "tấn", "consumption", "qty_principle", compare=True),
    _c("qty_unknown_type", "HĐ chưa khai loại", "tấn", "consumption", "qty_unknown_type"),
    _c("qty_export", "Xuất khẩu / UTXK", "tấn", "consumption", "qty_export", compare=True),
    _c("qty_domestic", "Trong nước", "tấn", "consumption", "qty_domestic", compare=True),
    _c("qty_internal", "Tiêu thụ nội bộ", "tấn", "consumption", "qty_internal", compare=True),
    _c("revenue_ty", "Doanh thu", "tỷ đồng", "consumption", "revenue_ty",
       note="cộng dồn", compare=True),
    _c("avg_price_trieu", "Giá bán BQ", "triệu đ/tấn", "consumption", "avg_price_trieu",
       note="BQ gia quyền"),
    _c("plan_sales_spot_tonnes", "KH tiêu thụ HĐ chuyến", "tấn", "consumption",
       "plan_sales_spot_tonnes", note="chỉ tiêu năm"),
    _c("pct_plan_sales_spot", "% thực hiện KH chuyến", "%", "consumption",
       "pct_plan_sales_spot", note="Σ TH ÷ Σ KH"),
    _c("lines", "Số lần giao", "lần", "consumption", "lines", compare=True),
    _c("days", "Số ngày có tiêu thụ", "ngày", "consumption", "days"),
]

#: Tồn kho đi TRỤC RIÊNG (ảnh chụp tại ngày chốt) nên không cột nào so kỳ được.
STOCK: list[Col] = [
    _c("not_warehoused", "Tồn TP chưa nhập kho", "tấn", "stock", "not_warehoused"),
    _c("warehoused", "Tồn TP đã nhập kho", "tấn", "stock", "warehoused"),
    _c("total", "TỔNG tồn thành phẩm", "tấn", "stock", "total"),
    _c("signed_undelivered", "Đã ký HĐ chưa giao", "tấn quy khô", "stock", "signed_undelivered",
       note="nằm trong tồn kho"),
    _c("tradable", "Tồn có thể giao dịch", "tấn", "stock", "tradable",
       note="tổng − đã ký; âm = thiếu hàng"),
    _c("material", "Tồn kho nguyên liệu", "tấn quy khô", "stock", "material"),
    _c("as_of", "Ngày lấy số", "", "stock", "as_of", note="mỗi đơn vị một ngày"),
]

COMPLIANCE: list[Col] = [
    _c("expected", "Số ngày phải nộp", "ngày", "status", "expected"),
    _c("filled", "Đã nộp", "ngày", "status", "filled"),
    _c("no_purchase", "Không tổ chức thu mua", "ngày", "status", "no_purchase"),
    _c("missing", "Còn thiếu", "ngày", "status", "missing"),
    _c("rate", "Tỷ lệ nộp", "%", "status", "rate", note="Σ đã nộp ÷ Σ phải nộp"),
    _c("last_day", "Ngày nộp gần nhất", "", "status", "last_day"),
]

TABS: dict[str, dict[str, Any]] = {
    "overview": {"label": "Tổng quan", "cols": OVERVIEW, "axis": "period"},
    "purchase": {"label": "Thu mua", "cols": PURCHASE, "axis": "period"},
    "consumption": {"label": "Tiêu thụ", "cols": CONSUMPTION, "axis": "period"},
    "stock": {"label": "Tồn kho", "cols": STOCK, "axis": "as_of"},
    "compliance": {"label": "Tuân thủ nhập liệu", "cols": COMPLIANCE, "axis": "period"},
}

#: Tab nào lọc được theo CHỦNG LOẠI. Mủ nước/chén/dây và kế hoạch năm khai theo tổng, không gắn
#: chủng loại — bật ô lọc ở đó chỉ làm người dùng tưởng số bị thiếu.
GRADE_TABS = frozenset({"consumption", "stock"})
#: Tab Thu mua lọc được chủng loại nhưng CHỈ tác động phần thành phẩm (xem `purchase_report`).
GRADE_PARTIAL_TABS = frozenset({"purchase"})


def sources(tab: str) -> list[str]:
    """Các bảng thống kê cần gọi cho một tab (không trùng, giữ thứ tự khai báo cột)."""
    out: list[str] = []
    for c in TABS[tab]["cols"]:
        if c["src"] not in out:
            out.append(c["src"])
    return out
