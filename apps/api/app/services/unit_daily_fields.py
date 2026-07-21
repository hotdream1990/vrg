"""Danh mục ô số liệu hợp lệ cho báo cáo tiêu thụ–tồn kho theo ngày (2 biểu mẫu).

Chỉ liệt kê các ô NHẬP TAY (đầu vào). Các ô suy ra (tổng tiêu thụ, % kế hoạch, giá BQ lũy kế…)
được tính ở frontend nên KHÔNG lưu. Bộ key này PHẢI khớp `apps/web/src/lib/unit-daily-fields.ts`.
Server dùng bộ này để lọc payload (chỉ nhận key hợp lệ) — chống ghi rác/khoá ngoài ý muốn.
"""

from __future__ import annotations

# Biểu mẫu Thu mua ("Chỉ tiêu Biểu (2)-ngày") — số THỜI ĐIỂM theo ngày (KHÔNG lũy kế, KHÔNG %KH).
# Đơn giá VND đồng bộ kho "Giá mủ nguyên liệu" (không ở đây). Tiền lưu BASE = đồng (VND). Giá BQ = cột suy ra.
# Đơn vị nước ngoài (Lào/Campuchia): thêm đơn giá theo nội tệ + 2 tỷ giá (nội tệ→VND cho đơn giá,
# USD→VND cho doanh thu); doanh thu quy về VND (đồng) là cột chính.
PURCHASE_FIELDS: frozenset[str] = frozenset({
    "latex_wet",         # sản lượng thu mua mủ nước trong ngày (tấn)
    "coagulum",          # sản lượng thu mua mủ chén trong ngày (tấn)
    # Thu mua THÀNH PHẨM (mua lại mủ đã chế biến) — nhập được cả đơn giá VNĐ lẫn ngoại tệ.
    "finished_qty",           # sản lượng thu mua thành phẩm (tấn)
    "price_finished_vnd",     # đơn giá thành phẩm theo VNĐ (triệu đ/tấn)
    "price_finished_fx",      # đơn giá thành phẩm theo ngoại tệ (USD/tấn)
    "fx_finished",            # tỷ giá ngoại tệ→VND cho đơn giá thành phẩm
    # ── Chỉ đơn vị nước ngoài ──
    "price_latex_local",  # đơn giá mủ nước theo nội tệ (vd LAK/độ TSC)
    "price_cup_local",    # đơn giá mủ chén theo nội tệ
    "fx_purchase",        # tỷ giá nội tệ→VND (quy đơn giá nội tệ ra VND)
})

# Ô CHỮ của biểu Thu mua: mủ chén tính theo độ TSC hay độ DRC (đổi nhãn đơn giá + đơn vị lưu kho giá).
PURCHASE_TEXT: dict[str, frozenset[str]] = {"cup_basis": frozenset({"tsc", "drc"})}

# Cờ đánh dấu ngày KHÔNG tổ chức thu mua. Phân biệt rõ 2 tình huống khác nhau về nghiệp vụ:
#   - có công bố giá, có tổ chức mua, nhưng KHÔNG mua được → nhập sản lượng 0 kèm ĐÚNG giá đã công bố
#   - hôm đó KHÔNG tổ chức thu mua                        → bật cờ này, không có giá nào cả
PURCHASE_FLAGS: frozenset[str] = frozenset({"no_purchase"})

# Biểu mẫu Tiêu thụ – Tồn kho — TIÊU THỤ = BẢNG NHIỀU DÒNG (`sales`); tổng doanh thu (VND, base=đồng) ở `revenue`.
# TỒN KHO (chỉ tiêu THỜI ĐIỂM, đơn vị TẤN) chia 4 khối theo yêu cầu nghiệp vụ:
#   1 `stock_not_warehoused`     Tồn kho thành phẩm chế biến CHƯA nhập kho (chủng loại · tấn)
#   2 `stock_warehoused`         Tồn kho thành phẩm ĐÃ nhập kho          (chủng loại · tấn)
#   3 `stock_signed_undelivered` Số lượng ĐÃ KÝ HĐ CHƯA GIAO (chủng loại · tấn · đơn giá · lịch giao
#                                · file HĐ scan đóng dấu)
#   4 `stock_material`           Tồn kho nguyên liệu CHƯA SẢN XUẤT — chỉ đơn vị KHÔNG có nhà máy
# Quy về mẫu tuần: mục 11 (tồn thành phẩm) = khối 1 + khối 2 · mục 12 (đã có HĐ) = khối 3 ·
# mục 13 = 11 − 12 · mục 14 = khối 4.
CONSUMPTION_FIELDS: frozenset[str] = frozenset({
    "revenue",            # tổng doanh thu tiêu thụ (BASE = đồng) — tính từ dòng bán
    "fx_revenue",         # tỷ giá USD→VND (khi giá bán / đơn giá tồn kho nhập bằng USD)
    "stock_material",     # tồn kho nguyên liệu chưa sản xuất, quy khô (tấn) — mọi đơn vị
    # ── Tiêu thụ mủ THU MUA và mủ THÀNH PHẨM (trước ở biểu Thu mua, chuyển sang đây) ──
    "purchased_sold_qty",       # SL tiêu thụ mủ thu mua (tấn)
    "purchased_sold_raw",       # số user gõ (tỷ đồng khi VND · USD khi USD) — giữ để mở lại form
    "purchased_sold_revenue",   # doanh thu tương ứng — BASE = đồng
    "purchased_sold_fx",        # tỷ giá USD→VND (khi doanh thu nhập bằng USD)
    "finished_sold_qty",        # SL tiêu thụ mủ thành phẩm (tấn)
    "finished_sold_raw",        # số user gõ — giữ để mở lại form
    "finished_sold_revenue",    # doanh thu tương ứng — BASE = đồng
    "finished_sold_fx",         # tỷ giá USD→VND
})

# Loại tiền người dùng CHỌN khi nhập giá bán (tiêu thụ) và đơn giá tồn kho đã có HĐ.
_CCY = frozenset({"VND", "USD"})
CONSUMPTION_TEXT: dict[str, frozenset[str]] = {
    "sales_ccy": _CCY, "stock_ccy": _CCY,
    "purchased_sold_ccy": _CCY, "finished_sold_ccy": _CCY,
}

_SALE_CONTRACTS = {"long_term", "spot"}   # loại HĐ: Dài hạn | Chuyến
_SALE_CHANNELS = {"export", "domestic"}   # hình thức: XK/UTXK | Nội tiêu

ALLOWED: dict[str, frozenset[str]] = {"purchase": PURCHASE_FIELDS}


def _to_float(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _clean_sales(sales) -> list[dict]:
    """Lọc/chuẩn hoá các dòng tiêu thụ.

    Mỗi dòng: loại HĐ · hình thức · loại mủ · số lượng · giá bán · NGÀY XUẤT HOÁ ĐƠN ·
    file bộ Hợp đồng đã upload (tên lưu uuid + tên gốc hiển thị).
    """
    out: list[dict] = []
    for ln in sales if isinstance(sales, list) else []:
        if not isinstance(ln, dict):
            continue
        out.append({
            "contract": ln.get("contract") if ln.get("contract") in _SALE_CONTRACTS else "long_term",
            "channel": ln.get("channel") if ln.get("channel") in _SALE_CHANNELS else "export",
            "grade": str(ln.get("grade") or "")[:60],
            "qty": _to_float(ln.get("qty")),
            "price": _to_float(ln.get("price")),
            # Loại tiền + tỷ giá theo TỪNG DÒNG: một ngày có thể vừa bán USD vừa bán VNĐ.
            "ccy": ln.get("ccy") if ln.get("ccy") in _CCY else "VND",
            "fx": _to_float(ln.get("fx")),
            "invoice_date": str(ln.get("invoice_date") or "")[:10] or None,
            "file": str(ln.get("file") or "")[:120] or None,
            "filename": str(ln.get("filename") or "")[:200] or None,
        })
    return out


def _clean_stock_qty(rows) -> list[dict]:
    """Khối tồn kho chỉ có SỐ LƯỢNG: chủng loại · số lượng (TẤN) — dùng cho khối 1 và khối 2."""
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        out.append({
            "grade": str(r.get("grade") or "")[:60],
            "qty": _to_float(r.get("qty")),
        })
    return out


def _clean_stock_signed(rows) -> list[dict]:
    """Khối 3 — đã ký hợp đồng: chủng loại · TẤN · đơn giá · lịch giao · file HĐ scan (tên file lưu)."""
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        out.append({
            "grade": str(r.get("grade") or "")[:60],
            "qty": _to_float(r.get("qty")),
            "price": _to_float(r.get("price")),
            "ccy": r.get("ccy") if r.get("ccy") in _CCY else "VND",
            "fx": _to_float(r.get("fx")),
            "delivery_date": str(r.get("delivery_date") or "")[:10] or None,
            "file": str(r.get("file") or "")[:120] or None,       # tên file lưu server
            "filename": str(r.get("filename") or "")[:200] or None,  # tên gốc hiển thị
        })
    return out


def _pick_text(fields: dict, spec: dict[str, frozenset[str]], out: dict) -> None:
    """Nhận các ô CHỮ có tập giá trị đóng (loại tiền, cách tính độ) — sai giá trị thì bỏ qua."""
    for k, choices in spec.items():
        v = fields.get(k)
        if isinstance(v, str) and v in choices:
            out[k] = v


def clean_fields(kind: str, fields: dict) -> dict:
    """Chuẩn hoá payload theo `kind` (chống ghi rác). Thu mua: ô phẳng. Tiêu thụ: dòng bán + tồn kho (mảng)."""
    fields = fields or {}
    if kind == "consumption":
        out: dict = {}
        if "sales" in fields:
            out["sales"] = _clean_sales(fields.get("sales"))
        for key in ("stock_not_warehoused", "stock_warehoused"):
            if key in fields:
                out[key] = _clean_stock_qty(fields.get(key))
        if "stock_signed_undelivered" in fields:
            out["stock_signed_undelivered"] = _clean_stock_signed(fields.get("stock_signed_undelivered"))
        for k in CONSUMPTION_FIELDS:
            fv = _to_float(fields.get(k))
            if fv is not None:
                out[k] = fv
        _pick_text(fields, CONSUMPTION_TEXT, out)
        return out
    allow = ALLOWED.get(kind, frozenset())
    out = {}
    for k, v in fields.items():
        if k not in allow:
            continue
        fv = _to_float(v)
        if fv is not None:
            out[k] = fv
    if kind == "purchase":
        _pick_text(fields, PURCHASE_TEXT, out)
        for k in PURCHASE_FLAGS:
            if fields.get(k) is True:
                out[k] = True
    return out
