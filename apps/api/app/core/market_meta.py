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

# Map grade reuters → dòng canonical bản tin (gồm cả Latex để không bỏ sót dữ liệu đã có).
PHYSICAL_GRADE_MAP = {
    "RSS3": "RSS3", "STR20": "STR20", "SMR20": "SMR20", "SIR20": "SIR20",
    "Thai Latex 60% (Bulk)": "Thai Latex 60% (Bulk)",
    "Thai Latex 60% (Drums)": "Thai Latex 60% (Drums)",
}

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
FX_PAIRS = ["USD/JPY", "USD/CNY", "USD/MYR", "USD/THB", "USD/VND (Mua)", "USD/VND (Bán)"]

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
                  "currency": "USc", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
        {"key": "SGX:TSR20", "grade": "TSR20", "label": "TSR20",
         "show_native": False, "show_fx": False,
         "edit": {"source": "sgx", "grade": "TSR20", "price_type": "settlement",
                  "currency": "USc", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
    ]},
    {"exchange": "MRB", "label": "MRB", "cols": [
        {"key": "MRB:SMRCV", "grade": "SMRCV", "label": "SMRCV",
         "show_native": False, "show_fx": False,
         "edit": {"source": "lgm", "grade": "SMRCV", "price_type": "physical",
                  "currency": "USc", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
        {"key": "MRB:SMR20", "grade": "SMR20", "label": "SMR20",
         "show_native": False, "show_fx": False,
         "edit": {"source": "lgm", "grade": "SMR20", "price_type": "physical",
                  "currency": "USc", "unit": "US cents/kg", "scale": 0.1, "field": "usd"}},
        {"key": "MRB:LATEX", "grade": "LATEX", "label": "LATEX",
         "show_native": True, "native_label": "Sen", "native_unit": "Sen/kg",
         "show_fx": True, "fx_pair": "USD/MYR",
         "edit": {"source": "lgm", "grade": "LATEX", "price_type": "physical",
                  "currency": "MYR", "unit": "Sen/kg", "scale": 1, "field": "native"}},
    ]},
]


# Chủng loại cho "Giá sàn Tập đoàn" (FOB USD/T + Nội địa VNĐ/T) — đúng tên & thứ tự báo cáo giá sàn.
VRG_FLOOR_GRADES = [
    "SVR CV 50", "SVR CV60", "SVR L", "SVR 3L Mix", "SVR 3L", "SVR 5S", "SVR 5",
    "SVR 10 Mix", "SVR 10 / CSR 10", "SVR 20 / CSR 20", "RSS 3", "RSS 1", "LATEX", "Skim Block",
]

# Chủng loại CHỈ có giá nội địa (không có FOB) — engine gợi ý giá sàn dự báo trên
# domestic_vnd (VNĐ/T) thay vì fob_usd, nhưng vẫn qua cùng cơ chế hồi quy rổ chỉ số.
VRG_DOMESTIC_ONLY_GRADES = {"Skim Block"}


# 2 loại MỦ NGUYÊN LIỆU bổ sung (chốt 30/07/2026) — tên giữ NGUYÊN VĂN như khách chốt.
# Chủng loại BÁN được trên hợp đồng. (Ô THU MUA riêng của 2 loại này đã bỏ 14/08/2026 — đơn vị
# không thu mua chúng; xem `services/unit_daily_fields.PURCHASE_FIELDS`.)
RAW_MATERIAL_GRADES = [
    "Mủ nguyên liệu nước chưa cán vắt (chén)",
    "Mủ nguyên liệu đã cán vắt (RSS)",
]

# MỦ DÂY (chốt 28/08/2026) — loại mủ nguyên liệu thứ BA mà đơn vị THỰC SỰ thu mua, đứng ngang hàng
# mủ nước và mủ chén. Khác 2 tên ở `RAW_MATERIAL_GRADES` phía trên (chỉ để bán): mủ dây có mặt ở CẢ
# ba biểu — thu mua (khối nhập riêng, đơn giá đồng/độ DRC) · tồn kho (chủng loại) · tiêu thụ (dòng
# hợp đồng, bắt buộc khai quy khô).
LACE_GRADE = "Mủ dây"

# DANH MỤC CHỦNG LOẠI DÙNG CHUNG cho MỌI màn nhập liệu của đơn vị thành viên — thu mua · tồn kho ·
# tiêu thụ đều đọc đúng danh sách này (đồng bộ 08/08/2026). Trước đó tồn kho/thu mua thiếu 2 loại
# mủ nguyên liệu mà hợp đồng bán lại có, nên cùng một đơn vị thấy 3 danh mục khác nhau.
#
# TÁCH THEO TỪNG LOẠI y như bảng Giá sàn Tập đoàn (SVR CV 50 và SVR CV60 là 2 loại riêng, không
# gộp). Bám thẳng `VRG_FLOOR_GRADES` để hai nơi luôn khớp, rồi thêm các mục giá sàn không có:
#   - "SVR 10CV / 20CV": dòng 13.2 của biểu mẫu tuần.
#   - "Chủng loại khác": gom phần còn lại (dòng 13.8).
#   - "Mủ ngoại lệ": hàng không xếp được vào loại nào ở trên (chốt 08/08/2026).
#   - "RSS 5" (thêm 13/09/2026): đơn vị có sản xuất/bán nhưng Tập đoàn KHÔNG ra giá sàn loại này →
#     chèn ngay dưới "RSS 1" cho các loại RSS đứng liền nhau, không đụng bảng giá sàn/bản tin.
# ⚠ THỨ TỰ là thứ tự hiện trên ô chọn của người nhập — đổi chỗ là đổi trải nghiệm nhập liệu.
# Web giữ một bản sao ở `apps/web/src/lib/unit-daily-consumption.ts`; `test_unit_daily.py` so 2 bên
# và sẽ đỏ nếu lệch — sửa ở đây thì sửa luôn bên đó.
_AFTER_RSS1 = VRG_FLOOR_GRADES.index("RSS 1") + 1
UNIT_GRADES = [
    *VRG_FLOOR_GRADES[:_AFTER_RSS1], "RSS 5", *VRG_FLOOR_GRADES[_AFTER_RSS1:],
    "SVR 10CV / 20CV", "Chủng loại khác", "Mủ ngoại lệ", *RAW_MATERIAL_GRADES,
    LACE_GRADE,
]

# Bán các loại này BẮT BUỘC nhập quy khô mới cho lưu (chốt Q4 — 30/07/2026; thêm mủ dây 28/08/2026).
DRY_REQUIRED_GRADES = frozenset({"LATEX", *RAW_MATERIAL_GRADES, LACE_GRADE})

# Hình thức tiêu thụ — dùng "Tiêu thụ nội bộ", KHÔNG dùng "nội tiêu" (chốt 30/07/2026).
SALE_CHANNELS: dict[str, str] = {
    "export": "Xuất khẩu / UTXK",
    "domestic": "Tiêu thụ trong nước",
    "internal": "Tiêu thụ nội bộ",
}

# Loại giao của hợp đồng: giao trọn 1 lần, hoặc chia thành nhiều ĐỢT GIAO.
DELIVERY_TYPES: dict[str, str] = {
    "single": "Giao 1 lần",
    "multi": "Giao nhiều lần (chia đợt giao)",
}

# Loại HỢP ĐỒNG của TỪNG bản ghi — hợp đồng này là PHỤ LỤC của một hồ sơ mẹ, hay bán đứt từng
# chuyến. ĐỘC LẬP với loại GIAO: một phụ lục vẫn có thể giao trọn 1 lần, nên KHÔNG suy ra từ
# `DELIVERY_TYPES`.
#
# ⚠ Nhãn `long_term` là "Phụ lục hợp đồng mẹ", KHÔNG phải "HĐ dài hạn" (đổi 29/08/2026): hồ sơ mẹ
# có CẢ HAI loại — nguyên tắc (HĐNT) và dài hạn (HĐDH), xem `MASTER_CONTRACT_TYPES` — nên gọi phụ
# lục là "dài hạn" là sai với phân nửa số hồ sơ. Khoá `long_term` GIỮ NGUYÊN (dữ liệu đã lưu theo
# khoá, không theo nhãn).
#
# ⚠ Các CỘT TỔNG HỢP của biểu Ban TTKD vẫn gọi "HĐ dài hạn" (chốt với chủ dự án 29/08/2026):
# `unit_period_excel` (lt_export/lt_domestic/signed_lt_tonnes/carry_lt_tonnes) và
# `unit_report_query.CONTRACT_LABELS` của màn Thống kê — đó là TÊN CHỈ TIÊU trên biểu mẫu gốc,
# đổi đi là chuyên viên đối chiếu với file Excel của họ bị lệch. Đây là khác biệt CỐ Ý.
CONTRACT_TYPES: dict[str, str] = {
    "long_term": "Phụ lục hợp đồng mẹ",
    "spot": "HĐ chuyến",
}

# Loại HỢP ĐỒNG MẸ (chốt 21/08/2026) — hồ sơ gốc ký với khách hàng, phụ lục nối về đây:
#   - `principle` HĐ NGUYÊN TẮC (HĐNT): khung nguyên tắc, thường KHÔNG có công thức giá.
#   - `long_term` HĐ DÀI HẠN (HĐDH): có công thức giá, mỗi chuyến hàng là một phụ lục.
# KHÁC `CONTRACT_TYPES` ở trên: cái đó là chỉ tiêu báo cáo của từng hợp đồng/phụ lục.
MASTER_CONTRACT_TYPES: dict[str, str] = {
    "principle": "HĐ nguyên tắc (HĐNT)",
    "long_term": "HĐ dài hạn (HĐDH)",
}

# Loại tiền trên dòng bán/thu mua — thêm nội tệ đơn vị nước ngoài (Lào LAK · Campuchia KHR).
SALE_CURRENCIES: tuple[str, ...] = ("VND", "USD", "LAK", "KHR")

# ── HÀNG CÓ CHỨNG CHỈ (chốt 26/08/2026) ────────────────────────────────────────────────────────
#: Chứng chỉ truy xuất nguồn gốc / bền vững gắn cho lô hàng của hợp đồng. Khách mua hàng có chứng
#: chỉ thường trả THÊM một khoản (premium) trên giá tham chiếu — trước đây đơn vị phải nhét chữ
#: "PEFC"/"EUDR" vào SỐ HỢP ĐỒNG hoặc TÊN FILE scan vì không có ô nào để khai.
#: Lưu đúng nhãn hiển thị (giống cách lưu chủng loại) — không dựng mã riêng để khỏi phải map 2 chiều.
CONTRACT_CERTS: tuple[str, ...] = ("PEFC", "EUDR", "VRG GREEN")

#: Loại tiền của khoản premium. CHỈ 2 loại: hợp đồng xuất khẩu tính USD/tấn, nội địa tính VNĐ —
#: nội tệ Lào/Campuchia không dùng cho khoản này (chốt 26/08/2026).
PREMIUM_CURRENCIES: tuple[str, ...] = ("USD", "VND")


# Chủng loại cho "Báo giá mủ thị trường" (Mục 1-3: giá tư nhân/VRG XK/VRG nội địa) — theo phiếu Excel.
MARKET_QUOTE_GRADES = ["SVR CV 50", "SVR CV 60", "SVR 3L", "SVR 10", "RSS3", "LATEX"]

# Gợi ý bao bì đóng gói cho các chủng loại SVR (Mục 1-3) — chọn nhanh trên form.
# LATEX dùng 2 lựa chọn cố định ("Đã có bao bì"/"Chưa có bao bì") xử lý riêng ở frontend.
MARKET_QUOTE_PACKAGING = ["Hàng rời", "Pallet"]


# Kho "Giá mủ nguyên liệu" tách LÀM HAI theo NGƯỜI NHẬP — trước đây chung một chỗ nên đơn vị
# lưu biểu Thu mua là ghi đè số chuyên viên đã chốt (và ngược lại).
#   `vrg`      — giá Ban TTKD (chuyên viên) chốt: dùng cho bản tin ngày, báo cáo tuần, gợi ý giá sàn.
#   `vrg_unit` — giá đơn vị thành viên tự khai: dùng cho biểu Thu mua và các bảng thống kê của đơn vị.
# Hai lớp vẫn TÁCH RIÊNG; chuyên viên có thể bắc CẦU MỘT CHIỀU `vrg_unit` → `vrg` cho từng đơn vị
# mình tin (bật ở màn Giá mủ nguyên liệu, xem `services/purchase_price_sync.py`) — đơn vị nhập là
# số chảy thẳng sang lớp chuyên viên, khỏi gõ lại. Cầu chỉ chảy MỘT CHIỀU: chuyên viên sửa ô của
# mình KHÔNG bao giờ ghi ngược về số đơn vị đã khai.
PURCHASE_SOURCE_HQ = "vrg"
PURCHASE_SOURCE_UNIT = "vrg_unit"
PURCHASE_SOURCES = (PURCHASE_SOURCE_HQ, PURCHASE_SOURCE_UNIT)
#: 3 loại giá của kho "Giá mủ nguyên liệu" (mủ nước · mủ chén · mủ dây).
#: ⚠ Mọi truy vấn lọc theo nhóm giá thu mua phải dựng mệnh đề IN từ hằng số này, KHÔNG viết tay
#: `IN ('purchase', 'purchase_cup')` — thêm loại mủ mới mà sót một chỗ là giá loại đó lặng lẽ
#: biến mất khỏi báo cáo/lưới giá mà không có lỗi nào báo.
PURCHASE_PRICE_TYPES = ("purchase", "purchase_cup", "purchase_lace")

# CƠ SỞ TÍNH ĐỘ — chốt 17/08/2026, KHÔNG cho chọn nữa (trước đây mủ chén có ô chọn TSC/DRC và
# mặc định TSC → 3.437 bản ghi bị gán nhầm nhãn). Quy ước của khách:
#   - đơn giá thu mua MỦ NƯỚC  → đồng/độ **TSC**
#   - đơn giá thu mua MỦ CHÉN  → đồng/độ **DRC**
#   - đơn giá thu mua MỦ DÂY   → đồng/độ **DRC** (chốt 28/08/2026)
#   - MỌI số "quy khô" trong hệ thống (sản lượng thu mua, tồn kho nguyên liệu, quy khô của hợp
#     đồng bán) đều là **DRC**.
# Mọi đường ghi giá phải lấy nhãn từ đây, không tự viết chuỗi — hai nơi viết tay sẽ lệch nhau.
PURCHASE_PRICE_UNIT: dict[str, str] = {
    "purchase": "đồng/độ TSC",
    "purchase_cup": "đồng/độ DRC",
    "purchase_lace": "đồng/độ DRC",
}
#: Nhãn ngắn dùng trong câu tóm tắt/nhận định.
DRY_BASIS = "DRC"

# ⚠ ĐƠN GIÁ THU MUA = 0 NGHĨA LÀ "KHÔNG CÓ GIÁ", KHÔNG PHẢI MỘT MỨC GIÁ (chốt 11/08/2026).
# Người nhập được phép gõ 0 (ngày đó đơn vị không công bố giá / không mua), nhưng số 0 KHÔNG
# được lưu thành một mức giá: để lọt vào kho là bản tin in ra "0-550 đồng/độ" cho cả khu vực,
# gợi ý giá sàn hồi quy trên một cú rơi về 0 không có thật, và giá bình quân gia quyền bị kéo tụt.
# Chặn ngay ở `price_repo.upsert_record` (0 → XOÁ bản ghi) để mọi đường ghi đều tuân thủ.
# Khác hẳn giá SÀN: ở đó 0 = phiên No Trading, vẫn là dữ liệu thật (xem bulletin/convert.py).

# Khu vực (nhóm đơn vị thành viên) — seed ban đầu; admin thêm/bớt ở tab Khu vực.
VRG_REGIONS = ["Bình Dương", "Bình Phước", "Bình Thuận", "Tây Ninh"]


# Công ty cao su thành viên VRG cho "Giá thu mua mủ nước" (đồng/độ TSC) — theo file Excel gốc.
VRG_COMPANIES = [
    "Bà Rịa", "Bình Long", "Dầu Tiếng", "Đồng Nai", "Phước Hòa", "Phú Riềng",
    "Đồng Phú", "Lộc Ninh", "Hàng Gòn", "Hòa Bình", "Phú Thịnh", "Tân Biên",
    "Tây Ninh (Tham khảo)", "Bình Thuận", "Quảng Trị", "Hà Tĩnh",
]
