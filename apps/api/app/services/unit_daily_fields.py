"""Danh mục ô số liệu hợp lệ cho báo cáo tiêu thụ–tồn kho theo ngày (2 biểu mẫu).

Chỉ liệt kê các ô NHẬP TAY (đầu vào). Các ô suy ra (tổng tiêu thụ, % kế hoạch, giá BQ lũy kế…)
được tính ở frontend nên KHÔNG lưu. Bộ key này PHẢI khớp `apps/web/src/lib/unit-daily-fields.ts`.
Server dùng bộ này để lọc payload (chỉ nhận key hợp lệ) — chống ghi rác/khoá ngoài ý muốn.
"""

from __future__ import annotations

# Loại tiền người dùng CHỌN khi nhập đơn giá (thu mua thành phẩm · giá bán tiêu thụ · tồn kho đã HĐ).
_CCY = frozenset({"VND", "USD"})

# Biểu mẫu Thu mua ("Chỉ tiêu Biểu (2)-ngày") — số THỜI ĐIỂM theo ngày (KHÔNG lũy kế, KHÔNG %KH).
# Đơn giá VND đồng bộ kho "Giá mủ nguyên liệu" (không ở đây). Tiền lưu BASE = đồng (VND). Giá BQ = cột suy ra.
# Đơn vị nước ngoài (Lào/Campuchia): thêm đơn giá theo nội tệ + 2 tỷ giá (nội tệ→VND cho đơn giá,
# USD→VND cho doanh thu); doanh thu quy về VND (đồng) là cột chính.
PURCHASE_FIELDS: frozenset[str] = frozenset({
    "latex_wet",         # sản lượng thu mua mủ nước trong ngày (tấn)
    "coagulum",          # sản lượng thu mua mủ chén trong ngày (tấn)
    # ── Chỉ đơn vị nước ngoài ──
    "price_latex_local",  # đơn giá mủ nước theo nội tệ (vd LAK/độ TSC)
    "price_cup_local",    # đơn giá mủ chén theo nội tệ
    "fx_purchase",        # tỷ giá nội tệ→VND (quy đơn giá nội tệ ra VND)
})

# Thu mua THÀNH PHẨM (mua lại mủ đã chế biến) — BẢNG NHIỀU DÒNG như tiêu thụ/tồn kho, vì một ngày
# mua nhiều CHỦNG LOẠI với đơn giá khác nhau. Mỗi dòng: chủng loại · tấn · đơn giá · loại tiền · tỷ giá.
FINISHED_TABLE = "finished"

# Ô CHỮ của biểu Thu mua: mủ chén tính theo độ TSC hay độ DRC (đổi nhãn đơn giá + đơn vị lưu kho giá).
PURCHASE_TEXT: dict[str, frozenset[str]] = {"cup_basis": frozenset({"tsc", "drc"})}

# Cờ đánh dấu ngày KHÔNG tổ chức thu mua. Phân biệt rõ 2 tình huống khác nhau về nghiệp vụ:
#   - có công bố giá, có tổ chức mua, nhưng KHÔNG mua được → nhập sản lượng 0 kèm ĐÚNG giá đã công bố
#   - hôm đó KHÔNG tổ chức thu mua                        → bật cờ này, không có giá nào cả
PURCHASE_FLAGS: frozenset[str] = frozenset({"no_purchase"})

# Biểu mẫu Tiêu thụ – Tồn kho — TIÊU THỤ = 2 BẢNG NHIỀU DÒNG nhập tách riêng: `sales` (mủ THU MUA)
# và `sales_own` (mủ KHAI THÁC); tổng doanh thu của CẢ HAI (VND, base=đồng) gộp chung ở `revenue`.
# TỒN KHO (chỉ tiêu THỜI ĐIỂM, đơn vị TẤN) chia 4 khối theo yêu cầu nghiệp vụ:
#   1 `stock_not_warehoused`     Tồn kho thành phẩm chế biến CHƯA nhập kho (chủng loại · tấn)
#   2 `stock_warehoused`         Tồn kho thành phẩm ĐÃ nhập kho          (chủng loại · tấn)
#   3 `stock_signed_undelivered` Số lượng ĐÃ KÝ HĐ CHƯA GIAO — KHÔNG lưu ở đây nữa: mỗi hợp đồng là
#                                1 bản ghi có vòng đời riêng ở bảng `unit_stock_contract` (nhập 1 lần,
#                                tự nằm ở khối này tới hết ngày trước ngày giao). Khi ĐỌC báo cáo
#                                ngày, khối này được tính và gắn vào (unit_daily_repo._attach_contracts).
#   4 `stock_material`           Tồn kho nguyên liệu CHƯA SẢN XUẤT — chỉ đơn vị KHÔNG có nhà máy
# Tồn kho thành phẩm = khối 1 + khối 2. Khối 3 là CAM KẾT giao hàng, chỉ để GHI NHẬN đã ký bao nhiêu
# mà chưa giao — KHÔNG cộng vào và KHÔNG trừ khỏi tồn kho. Khối 4 báo riêng.
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

CONSUMPTION_TEXT: dict[str, frozenset[str]] = {
    "sales_ccy": _CCY, "stock_ccy": _CCY,
    "purchased_sold_ccy": _CCY, "finished_sold_ccy": _CCY,
}

_SALE_CONTRACTS = {"long_term", "spot"}   # loại HĐ: Dài hạn | Chuyến
_SALE_CHANNELS = {"export", "domestic"}   # hình thức: XK/UTXK | Nội tiêu

# 2 bảng tiêu thụ nhập TÁCH RIÊNG (để lưu trữ riêng), tổng vẫn cộng chung:
#   `sales`     — tiêu thụ mủ THU MUA
#   `sales_own` — tiêu thụ mủ KHAI THÁC
SALE_TABLES: tuple[str, ...] = ("sales", "sales_own")
# 3 file đính kèm mỗi dòng bán: (khoá file lưu server, khoá tên gốc hiển thị).
SALE_DOC_SLOTS: tuple[tuple[str, str], ...] = (
    ("file", "filename"),            # bộ Hợp đồng
    ("wh_file", "wh_filename"),      # phiếu xuất kho
    ("inv_file", "inv_filename"),    # hoá đơn
)

ALLOWED: dict[str, frozenset[str]] = {"purchase": PURCHASE_FIELDS}


def _to_float(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _code(v) -> str | None:
    """Mã Hợp đồng / Phụ lục người dùng gõ tay — chuỗi ngắn, rỗng thì lưu None."""
    return str(v or "").strip()[:60] or None


def _clean_sales(sales) -> list[dict]:
    """Lọc/chuẩn hoá các dòng tiêu thụ (dùng chung `sales` = mủ thu mua và `sales_own` = mủ khai thác).

    Mỗi dòng: MÃ HĐ/PL · loại HĐ · hình thức · loại mủ · số lượng · giá bán · NGÀY XUẤT KHO ·
    NGÀY XUẤT HOÁ ĐƠN · 3 file đính kèm (bộ Hợp đồng · phiếu xuất kho · hoá đơn),
    mỗi file lưu tên uuid trên server + tên gốc để hiển thị.
    """
    out: list[dict] = []
    for ln in sales if isinstance(sales, list) else []:
        if not isinstance(ln, dict):
            continue
        row = {
            "code": _code(ln.get("code")),   # mã Hợp đồng / Phụ lục của dòng bán
            "contract": ln.get("contract") if ln.get("contract") in _SALE_CONTRACTS else "long_term",
            "channel": ln.get("channel") if ln.get("channel") in _SALE_CHANNELS else "export",
            "grade": str(ln.get("grade") or "")[:60],
            "qty": _to_float(ln.get("qty")),
            "price": _to_float(ln.get("price")),
            # Loại tiền + tỷ giá theo TỪNG DÒNG: một ngày có thể vừa bán USD vừa bán VNĐ.
            "ccy": ln.get("ccy") if ln.get("ccy") in _CCY else "VND",
            "fx": _to_float(ln.get("fx")),
            "warehouse_date": str(ln.get("warehouse_date") or "")[:10] or None,
            "invoice_date": str(ln.get("invoice_date") or "")[:10] or None,
        }
        for fk, nk in SALE_DOC_SLOTS:
            row[fk] = str(ln.get(fk) or "")[:120] or None
            row[nk] = str(ln.get(nk) or "")[:200] or None
        out.append(row)
    return out


def _clean_finished(rows) -> list[dict]:
    """Thu mua thành phẩm — mỗi dòng 1 CHỦNG LOẠI: chủng loại · TẤN · đơn giá · loại tiền · tỷ giá.

    Đơn giá theo loại tiền của DÒNG (VND → triệu đ/tấn · USD → USD/tấn), y hệt dòng bán tiêu thụ:
    một ngày có thể mua chủng loại này bằng VNĐ, chủng loại kia bằng USD.
    """
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


def _pick_text(fields: dict, spec: dict[str, frozenset[str]], out: dict) -> None:
    """Nhận các ô CHỮ có tập giá trị đóng (loại tiền, cách tính độ) — sai giá trị thì bỏ qua."""
    for k, choices in spec.items():
        v = fields.get(k)
        if isinstance(v, str) and v in choices:
            out[k] = v


def clean_fields(kind: str, fields: dict) -> dict:
    """Chuẩn hoá payload theo `kind` (chống ghi rác).

    Thu mua: ô phẳng + bảng `finished` (thu mua thành phẩm theo chủng loại).
    Tiêu thụ: dòng bán + tồn kho (mảng).
    """
    fields = fields or {}
    if kind == "consumption":
        out: dict = {}
        for key in SALE_TABLES:
            if key in fields:
                out[key] = _clean_sales(fields.get(key))
        for key in ("stock_not_warehoused", "stock_warehoused"):
            if key in fields:
                out[key] = _clean_stock_qty(fields.get(key))
        # Khối 3 (đã ký HĐ) KHÔNG lưu trong payload ngày — client có gửi kèm cũng bỏ qua.
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
        if FINISHED_TABLE in fields:
            out[FINISHED_TABLE] = _clean_finished(fields.get(FINISHED_TABLE))
        _pick_text(fields, PURCHASE_TEXT, out)
        for k in PURCHASE_FLAGS:
            if fields.get(k) is True:
                out[k] = True
    return out
