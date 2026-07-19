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
    "consumption",       # sản lượng tiêu thụ mủ thu mua trong ngày (tấn)
    "revenue",           # doanh thu tiêu thụ — LƯU BASE = đồng (VND); nước ngoài = revenue_usd × fx_revenue
    # ── Chỉ đơn vị nước ngoài ──
    "price_latex_local",  # đơn giá mủ nước theo nội tệ (vd LAK/độ TSC)
    "price_cup_local",    # đơn giá mủ chén theo nội tệ
    "fx_purchase",        # tỷ giá nội tệ→VND (quy đơn giá nội tệ ra VND)
    "revenue_usd",        # doanh thu theo USD
    "fx_revenue",         # tỷ giá USD→VND (quy doanh thu USD ra VND)
})

# Biểu mẫu Tiêu thụ – Tồn kho — TIÊU THỤ = BẢNG NHIỀU DÒNG (`sales`); tổng doanh thu (VND, base=đồng) ở `revenue`.
# TỒN KHO: `stock_no_contract` (chưa HĐ: chủng loại·loại bành·số lượng kg) + `stock_contract` (đã HĐ:
# chủng loại·kg·đơn giá·lịch giao·file) + `stock_material_kg` (nguyên liệu, chỉ đơn vị KHÔNG có nhà máy).
CONSUMPTION_FIELDS: frozenset[str] = frozenset({
    "revenue",            # tổng doanh thu tiêu thụ (BASE = đồng) — tính từ dòng bán
    "fx_revenue",         # tỷ giá USD→VND (nước ngoài)
    "stock_material_kg",  # tồn kho nguyên liệu chưa có HĐ (kg) — đơn vị chưa có nhà máy
})

_SALE_CONTRACTS = {"long_term", "spot"}   # loại HĐ: Dài hạn | Chuyến
_SALE_CHANNELS = {"export", "domestic"}   # hình thức: XK/UTXK | Nội tiêu

ALLOWED: dict[str, frozenset[str]] = {"purchase": PURCHASE_FIELDS}


def _to_float(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _clean_sales(sales) -> list[dict]:
    """Lọc/chuẩn hoá các dòng tiêu thụ (loại HĐ, hình thức, loại mủ, số lượng, giá bán)."""
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
        })
    return out


def _clean_stock_no_contract(rows) -> list[dict]:
    """Tồn kho thành phẩm CHƯA có HĐ: chủng loại · loại bành · số lượng (kg)."""
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        out.append({
            "grade": str(r.get("grade") or "")[:60],
            "bale": str(r.get("bale") or "")[:20],
            "qty_kg": _to_float(r.get("qty_kg")),
        })
    return out


def _clean_stock_contract(rows) -> list[dict]:
    """Tồn kho thành phẩm ĐÃ có HĐ: chủng loại · kg · đơn giá · lịch giao · file HĐ (tên file đã upload)."""
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        out.append({
            "grade": str(r.get("grade") or "")[:60],
            "qty_kg": _to_float(r.get("qty_kg")),
            "price": _to_float(r.get("price")),
            "delivery_date": str(r.get("delivery_date") or "")[:10] or None,
            "file": str(r.get("file") or "")[:120] or None,       # tên file lưu server
            "filename": str(r.get("filename") or "")[:200] or None,  # tên gốc hiển thị
        })
    return out


def clean_fields(kind: str, fields: dict) -> dict:
    """Chuẩn hoá payload theo `kind` (chống ghi rác). Thu mua: ô phẳng. Tiêu thụ: dòng bán + tồn kho (mảng)."""
    fields = fields or {}
    if kind == "consumption":
        out: dict = {}
        if "sales" in fields:
            out["sales"] = _clean_sales(fields.get("sales"))
        if "stock_no_contract" in fields:
            out["stock_no_contract"] = _clean_stock_no_contract(fields.get("stock_no_contract"))
        if "stock_contract" in fields:
            out["stock_contract"] = _clean_stock_contract(fields.get("stock_contract"))
        for k in CONSUMPTION_FIELDS:
            fv = _to_float(fields.get(k))
            if fv is not None:
                out[k] = fv
        return out
    allow = ALLOWED.get(kind, frozenset())
    out = {}
    for k, v in fields.items():
        if k not in allow:
            continue
        fv = _to_float(v)
        if fv is not None:
            out[k] = fv
    return out
