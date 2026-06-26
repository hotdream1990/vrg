"""Hằng số thị trường dùng chung (DRY) — map sàn/grade, tên sàn, FX, công ty VRG.

Trích từ bulletin_service để cả bản tin lẫn dashboard (price_board) dùng chung,
tránh khai báo trùng. Không phụ thuộc DB/HTTP.
"""

from __future__ import annotations

# (source crawler, grade crawler) → (sàn bản tin, grade bản tin)
WORLD_GRADE_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("tocom", "RSS3"): ("OSE", "RSS3"),
    ("tocom", "TSR20"): ("OSE", "TSR20"),
    ("shfe", "RU"): ("SHANGHAI", "RSS3"),
    ("sgx", "RSS3"): ("SGX", "RSS3"),
    ("sgx", "TSR20"): ("SGX", "TSR20"),
    ("lgm", "SMRCV"): ("MRE", "SMRCV"),
    ("lgm", "SMR20"): ("MRE", "SMR20"),
    ("lgm", "LATEX"): ("MRE", "LATEX"),
}

PHYSICAL_GRADE_MAP = {"RSS3": "RSS3", "STR20": "STR20", "SMR20": "SMR20", "SIR20": "SIR20"}

EXCHANGE_NAMES = {
    "OSE": "Sàn TOCOM (Nhật Bản)",
    "SHANGHAI": "Sàn SHFE (Thượng Hải - Trung Quốc)",
    "SGX": "Sàn SGX (Singapore)",
    "MRE": "Sàn MRB (Malaysia)",
}

# Thứ tự hiển thị các sàn (dashboard board).
EXCHANGE_ORDER = ["OSE", "SHANGHAI", "SGX", "MRE"]

# Cấu trúc cố định theo template PPTX (đúng thứ tự + đủ dòng) — thiếu data → N/A khi xuất.
CANON_WORLD = [
    ("OSE", "RSS3"), ("SHANGHAI", "RSS3"), ("SGX", "RSS3"), ("SGX", "TSR20"),
    ("MRE", "SMRCV"), ("MRE", "SMR20"), ("MRE", "LATEX"),
]
CANON_PHYS = ["RSS3", "STR20", "SMR20", "SIR20",
              "Thai Latex 60% (Bulk)", "Thai Latex 60% (Drums)"]

# Cặp tỷ giá hiển thị ở mục "Exchange Rate" (đã được FX crawler nạp sẵn).
FX_PAIRS = ["USD/JPY", "USD/CNY", "USD/MYR", "USD/THB", "USD/VND"]

# ── Spec lưới "Bảng tính giá" (giống sheet mẫu VRG) ──
# Mỗi nhóm = 1 sàn; mỗi cột = 1 mặt hàng. `edit` = khóa fact_price để ghi đè khi sửa ô.
#  - show_native: hiện cột giá nội tệ (YEN/CNY/Sen).  show_fx: hiện cột tỷ giá inline.
#  - edit.field='native' → ô sửa lưu thẳng giá nội tệ; ='usd' → lưu native = USD * scale (cents = USD/10).
SHEET_GROUPS = [
    {"exchange": "OSE", "label": "OSE", "cols": [
        {"key": "OSE:RSS3", "grade": "RSS3", "label": "RSS3 (JPX)",
         "show_native": True, "native_label": "YEN", "native_unit": "JPY/kg",
         "show_fx": True, "fx_pair": "USD/JPY",
         "edit": {"source": "tocom", "grade": "RSS3", "price_type": "settlement",
                  "currency": "JPY", "unit": "JPY/kg", "scale": 1, "field": "native"}},
    ]},
    {"exchange": "SHANGHAI", "label": "SHANGHAI", "cols": [
        {"key": "SHANGHAI:RSS3", "grade": "RSS3", "label": "RSS3",
         "show_native": True, "native_label": "CNY", "native_unit": "CNY/tonne",
         "show_fx": True, "fx_pair": "USD/CNY",
         "edit": {"source": "shfe", "grade": "RU", "price_type": "settlement",
                  "currency": "CNY", "unit": "CNY/tonne", "scale": 1, "field": "native"}},
    ]},
    {"exchange": "SGX", "label": "SGX", "cols": [
        {"key": "SGX:RSS3", "grade": "RSS3", "label": "RSS3",
         "show_native": False, "show_fx": False,
         "edit": {"source": "sgx", "grade": "RSS3", "price_type": "settlement",
                  "currency": "USD", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
        {"key": "SGX:TSR20", "grade": "TSR20", "label": "TSR20",
         "show_native": False, "show_fx": False,
         "edit": {"source": "sgx", "grade": "TSR20", "price_type": "settlement",
                  "currency": "USD", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
    ]},
    {"exchange": "MRB", "label": "MRB", "cols": [
        {"key": "MRB:SMRCV", "grade": "SMRCV", "label": "SMRCV",
         "show_native": False, "show_fx": False,
         "edit": {"source": "lgm", "grade": "SMRCV", "price_type": "physical",
                  "currency": "USD", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
        {"key": "MRB:SMR20", "grade": "SMR20", "label": "SMR20",
         "show_native": False, "show_fx": False,
         "edit": {"source": "lgm", "grade": "SMR20", "price_type": "physical",
                  "currency": "USD", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
        {"key": "MRB:LATEX", "grade": "LATEX", "label": "LATEX",
         "show_native": True, "native_label": "Sen", "native_unit": "US cents/kg",
         "show_fx": False, "fx_pair": "USD/MYR",
         "edit": {"source": "lgm", "grade": "LATEX", "price_type": "physical",
                  "currency": "USD", "unit": "US cents/kg", "scale": 1, "field": "native"}},
    ]},
]


# Chủng loại cho "Giá sàn Tập đoàn" (FOB USD/T + Nội địa VNĐ/T) — đúng thứ tự template bản tin.
VRG_FLOOR_GRADES = [
    "SVR CV 50", "SVR CV60", "SVR L", "SVR 3L Mix", "SVR 3L", "SVR 5S", "SVR 5",
    "SVR 10 Mix", "SVR 10", "SVR 20", "RSS 3", "RSS 1", "LATEX",
]


# Công ty cao su thành viên VRG cho "Giá thu mua mủ nước" (đồng/độ TSC) — theo file Excel gốc.
VRG_COMPANIES = [
    "Bà Rịa", "Bình Long", "Dầu Tiếng", "Đồng Nai", "Phước Hòa", "Phú Riềng",
    "Đồng Phú", "Lộc Ninh", "Hàng Gòn", "Hòa Bình", "Phú Thịnh", "Tân Biên",
    "Tây Ninh (Tham khảo)", "Bình Thuận", "Quảng Trị", "Hà Tĩnh",
]
