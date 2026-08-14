"""Danh mục ô số liệu hợp lệ cho báo cáo tiêu thụ–tồn kho theo ngày (2 biểu mẫu).

Chỉ liệt kê các ô NHẬP TAY (đầu vào). Các ô suy ra (tổng tiêu thụ, % kế hoạch, giá BQ lũy kế…)
được tính ở frontend nên KHÔNG lưu. Bộ key này PHẢI khớp `apps/web/src/lib/unit-daily-fields.ts`.
Server dùng bộ này để lọc payload (chỉ nhận key hợp lệ) — chống ghi rác/khoá ngoài ý muốn.
"""

from __future__ import annotations

from app.core.market_meta import SALE_CURRENCIES
from app.services import contract_docs

# Loại tiền người dùng CHỌN khi nhập đơn giá (thu mua thành phẩm · giá bán tiêu thụ · tồn kho đã HĐ).
# Từ 30/07/2026 mở thêm NỘI TỆ của đơn vị nước ngoài: Lào = LAK, Campuchia = KHR.
_CCY = frozenset(SALE_CURRENCIES)

# Biểu mẫu Thu mua ("Chỉ tiêu Biểu (2)-ngày") — số THỜI ĐIỂM theo ngày (KHÔNG lũy kế, KHÔNG %KH).
# Đơn giá VND đồng bộ kho "Giá mủ nguyên liệu" (không ở đây). Tiền lưu BASE = đồng (VND). Giá BQ = cột suy ra.
# Đơn vị nước ngoài (Lào/Campuchia): thêm đơn giá theo nội tệ + 2 tỷ giá (nội tệ→VND cho đơn giá,
# USD→VND cho doanh thu); doanh thu quy về VND (đồng) là cột chính.
PURCHASE_FIELDS: frozenset[str] = frozenset({
    "latex_wet",         # sản lượng thu mua mủ nước trong ngày (tấn)
    "coagulum",          # sản lượng thu mua mủ chén trong ngày (tấn)
    # ⚠ 2 loại "Mủ NL nước chưa cán vắt (chén)" và "Mủ NL đã cán vắt (RSS)" từng có ô riêng ở đây
    # (chốt 30/07/2026, bỏ 14/08/2026 theo yêu cầu khách: đơn vị KHÔNG thu mua 2 loại này). Hai tên
    # đó VẪN là chủng loại BÁN hợp lệ (`market_meta.RAW_MATERIAL_GRADES`, 39 hợp đồng đang dùng) —
    # đừng nhầm mà xoá luôn bên hợp đồng.
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
#   3 `stock_signed_undelivered` Số lượng ĐÃ KÝ HĐ CHƯA GIAO — KHÔNG lưu ở đây nữa: TỰ TÍNH từ
#                                hợp đồng bán hàng 2 cấp `sales_contract` (cam kết − đã giao tại
#                                ngày báo cáo, chốt 30/07/2026) CỘNG hợp đồng CŨ ở bảng
#                                `unit_stock_contract` còn hiệu lực (giữ để không mất lịch sử trước
#                                ngày chuyển đổi). Khi ĐỌC báo cáo ngày, khối này được tính và gắn
#                                vào (`unit_daily_repo.contracts_on` / `_attach_contracts`), SHAPE:
#                                `{"qty": tổng còn lại (tấn), "by_grade": {chủng loại: số lượng},
#                                  "items": [...]}`; mục từ hợp đồng cũ đánh dấu `"legacy": True`.
#   4 `stock_material`           Tồn kho nguyên liệu CHƯA SẢN XUẤT — chỉ đơn vị KHÔNG có nhà máy
# Tồn kho thành phẩm = khối 1 + khối 2. Khối 3 là phần NẰM TRONG tồn kho thành phẩm đã có hợp đồng
# nhưng chưa giao → chỉ báo, KHÔNG cộng thêm (cộng nữa là tính trùng) và không trừ ra. Khối 4 báo riêng.
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

# Cờ đánh dấu ngày KHÔNG phát sinh tồn kho để khai (song song `no_purchase` của biểu Thu mua) —
# đơn vị bật cờ là đã nộp báo cáo, màn "Theo dõi nộp báo cáo" không còn báo thiếu.
#   `no_stock`       — ngày không phát sinh tồn kho để khai (đơn vị bật, coi như đã nộp).
#   `sales_migrated` — script chuyển đổi đã copy 2 mảng `sales`/`sales_own` của ngày này sang
#                      hợp đồng. Mảng cũ VẪN GIỮ để tra cứu, nhưng báo cáo phải BỎ QUA nó, nếu
#                      không sản lượng/doanh thu bị đếm hai lần (một ở mảng cũ, một ở hợp đồng).
CONSUMPTION_FLAGS: frozenset[str] = frozenset({"no_stock", "sales_migrated"})

#: Hai khối tồn kho thành phẩm nhập thành BẢNG nhiều dòng (khối 1 & 2 của biểu Tồn kho).
STOCK_TABLES: tuple[str, ...] = ("stock_not_warehoused", "stock_warehoused")

#: Ô/khối chứng tỏ đơn vị ĐÃ THẬT SỰ NỘP biểu đó cho một ngày (dùng ở màn "Theo dõi nộp báo cáo").
#:
#: ⚠ CÓ BẢN GHI ≠ ĐÃ NỘP. Biểu Tồn kho nhận một loạt bản ghi CŨ của biểu Tiêu thụ (mảng `sales` +
#: cờ `sales_migrated`) — những ngày đó đơn vị khai TIÊU THỤ theo cơ chế cũ, chưa hề khai tồn kho.
#: Đếm theo "có dòng trong bảng" thì các ngày ấy hiện ✅ và bảng theo dõi báo tỷ lệ nộp cao hơn
#: thực tế (đo 05/08/2026: 151/566 ngày là bản ghi cũ như vậy). Vì thế phải soi ĐÚNG ô của biểu.
_SUBMITTED_KEYS: dict[str, frozenset[str]] = {
    "purchase": PURCHASE_FIELDS | PURCHASE_FLAGS | {FINISHED_TABLE},
    # CỐ Ý bỏ `sales`/`sales_own`/`revenue`/`sales_migrated`: form nay chỉ còn khối Tồn kho.
    "consumption": frozenset({"no_stock", "stock_material", *STOCK_TABLES}),
}


def has_data(kind: str, fields: dict) -> bool:
    """Bản ghi này có số liệu THẬT của biểu `kind` chưa (bảng rỗng / ô None không tính)."""
    for key in _SUBMITTED_KEYS.get(kind, frozenset()):
        v = fields.get(key)
        if isinstance(v, list):
            if v:
                return True
        elif v is not None and v != "":
            return True
    return False

_SALE_CONTRACTS = {"long_term", "spot"}   # loại HĐ: Dài hạn | Chuyến
_SALE_CHANNELS = {"export", "domestic"}   # hình thức: XK/UTXK | Tiêu thụ trong nước

# 2 bảng tiêu thụ nhập TÁCH RIÊNG (để lưu trữ riêng), tổng vẫn cộng chung:
#   `sales`     — tiêu thụ mủ THU MUA
#   `sales_own` — tiêu thụ mủ KHAI THÁC
# ⚠ TỪ 30/07/2026 hai mảng này là DỮ LIỆU CŨ (legacy): tiêu thụ chuyển sang tính từ các LẦN GIAO
# của hợp đồng (`sales_contract`). Form không nhập nữa, nhưng tầng lưu trữ VẪN nhận/giữ nguyên để
# không mất số liệu đã khai — xoá key ở đây là mất sạch lịch sử khi đơn vị lưu lại ngày cũ.
SALE_TABLES: tuple[str, ...] = ("sales", "sales_own")
# 3 Ô đính kèm mỗi dòng bán, mỗi ô nhận NHIỀU file:
#   (khoá danh sách, khoá file lưu server, khoá tên gốc hiển thị)
# Cặp khoá phẳng (file, filename) = file ĐẦU danh sách, giữ lại để bản ghi cũ + Excel vẫn đọc được.
SALE_DOC_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("files", "file", "filename"),               # bộ Hợp đồng
    ("wh_files", "wh_file", "wh_filename"),      # phiếu xuất kho
    ("inv_files", "inv_file", "inv_filename"),   # hoá đơn
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

    Mỗi dòng: SỐ HĐ/PL · loại HĐ · hình thức · loại mủ · số lượng · giá bán · NGÀY XUẤT KHO ·
    NGÀY XUẤT HOÁ ĐƠN · 3 ô đính kèm (bộ Hợp đồng · phiếu xuất kho · hoá đơn), MỖI Ô NHIỀU FILE —
    mỗi file lưu tên uuid trên server + tên gốc để hiển thị (xem `contract_docs`).
    """
    out: list[dict] = []
    for ln in sales if isinstance(sales, list) else []:
        if not isinstance(ln, dict):
            continue
        row = {
            "code": _code(ln.get("code")),   # số Hợp đồng / Phụ lục của dòng bán
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
        for lk, fk, nk in SALE_DOC_SLOTS:
            docs = contract_docs.normalize(ln.get(lk), ln.get(fk), ln.get(nk))
            row[lk] = docs
            row[fk], row[nk] = contract_docs.first(docs)   # giữ khoá cũ cho tương thích ngược
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
        for key in STOCK_TABLES:
            if key in fields:
                out[key] = _clean_stock_qty(fields.get(key))
        # Khối 3 (đã ký HĐ) KHÔNG lưu trong payload ngày — client có gửi kèm cũng bỏ qua.
        for k in CONSUMPTION_FIELDS:
            fv = _to_float(fields.get(k))
            if fv is not None:
                out[k] = fv
        _pick_text(fields, CONSUMPTION_TEXT, out)
        for k in CONSUMPTION_FLAGS:
            if fields.get(k) is True:
                out[k] = True
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
