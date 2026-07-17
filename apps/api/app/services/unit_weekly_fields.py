"""Danh mục ô số liệu hợp lệ cho báo cáo tuần đơn vị (2 biểu mẫu).

Chỉ liệt kê các ô NHẬP TAY (đầu vào). Các ô suy ra (tổng tiêu thụ, % kế hoạch, giá BQ lũy kế…)
được tính ở frontend nên KHÔNG lưu. Bộ key này PHẢI khớp `apps/web/src/lib/unit-weekly-fields.ts`.
Server dùng bộ này để lọc payload (chỉ nhận key hợp lệ) — chống ghi rác/khoá ngoài ý muốn.
"""

from __future__ import annotations

# Biểu mẫu Thu mua — số thời điểm/lũy kế (tấn), riêng doanh thu = tỷ đồng.
PURCHASE_FIELDS: frozenset[str] = frozenset({
    "latex_wet",        # thu mua mủ nước trong tuần (quy khô, tấn)
    "coagulum",         # thu mua mủ đông trong tuần (quy khô, tấn)
    "cum_purchase",     # lũy kế sản lượng mủ thu mua (tấn)
    "cum_consumption",  # sản lượng tiêu thụ lũy kế mủ thu mua (tấn)
    "cum_revenue",      # doanh thu tiêu thụ lũy kế mủ thu mua (tỷ đồng)
})

# Biểu mẫu Tiêu thụ – Tồn kho — số thời điểm/lũy kế (tấn), doanh thu = tỷ đồng, giá = triệu đồng/tấn.
CONSUMPTION_FIELDS: frozenset[str] = frozenset({
    "signed_lt_2026",     # tổng SL đã ký theo HĐ dài hạn 2026 (lũy kế)
    "lt_export",          # tiêu thụ HĐ dài hạn — XK/UTXK (lũy kế)
    "lt_domestic",        # tiêu thụ HĐ dài hạn — nội tiêu (lũy kế)
    "spot_export",        # tiêu thụ HĐ chuyến — XK/UTXK (lũy kế)
    "spot_domestic",      # tiêu thụ HĐ chuyến — nội tiêu (lũy kế)
    "revenue",            # doanh thu cao su (tỷ đồng, lũy kế)
    "price_week",         # giá bán BQ trong tuần (triệu đồng/tấn)
    "stock_finished",     # tồn kho thành phẩm (tấn)
    "stock_finished_hd",  # trong đó đã có hợp đồng (tấn)
    # tồn kho thành phẩm CHƯA có hợp đồng, tách theo chủng loại (tấn)
    "g_cv", "g_10cv20cv", "g_l3l", "g_rss", "g_5_5s", "g_10_20", "g_latex", "g_skim", "g_other",
    "stock_material",     # tồn kho nguyên liệu chưa có HĐ (đơn vị chưa có nhà máy)
    "carry_lt_2025",      # tiêu thụ HĐ dài hạn 2025 chuyển sang 2026
    "carry_spot_2025",    # tiêu thụ HĐ chuyến 2025 chuyển sang 2026
})

ALLOWED: dict[str, frozenset[str]] = {
    "purchase": PURCHASE_FIELDS,
    "consumption": CONSUMPTION_FIELDS,
}


def clean_fields(kind: str, fields: dict) -> dict[str, float]:
    """Chỉ giữ key hợp lệ theo `kind`, ép về float, bỏ giá trị None/không phải số."""
    allow = ALLOWED.get(kind, frozenset())
    out: dict[str, float] = {}
    for k, v in (fields or {}).items():
        if k not in allow or v is None:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out
