"""Sheet TỔNG HỢP theo đơn vị của file Excel Báo cáo tiêu thụ — cột + dòng + dòng Tổng cộng.

Tách khỏi `sales_contract_consumption_excel` cho gọn file. Đọc đúng khối `_consumption` của router
(`by_company` · `undelivered` · `backlog`) nên file và bảng trên web luôn cùng một số.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import CONSUMPTION_SOURCES, SALE_CHANNELS
from app.services.unit_analytics_excel import Col

TY = 1_000_000_000

SUMMARY_COLS: list[Col] = [
    ("deliveries", "Số lần giao", "lần"),
    # Sản lượng tiêu thụ đã là QUY KHÔ (xem `sales_contract_calc.sale_qty`) → nói rõ ngay ở tiêu đề,
    # và cột kế bên trả lại số cân thực tế của chủng loại còn nước thay vì lặp lại số khô.
    ("qty", "Sản lượng tiêu thụ", "tấn quy khô"),
    ("qty_wet", "Trong đó: SL chưa quy khô", "tấn"),
    ("qty_export", SALE_CHANNELS["export"], "tấn"),
    ("qty_domestic", SALE_CHANNELS["domestic"], "tấn"),
    ("qty_internal", SALE_CHANNELS["internal"], "tấn"),
    # Nguồn tiêu thụ (03/10/2026) — cùng tổng với 3 cột hình thức, chỉ cắt theo chiều khác.
    ("qty_exploit", f"Nguồn {CONSUMPTION_SOURCES['exploit'].lower()}", "tấn quy khô"),
    ("qty_purchase", f"Nguồn {CONSUMPTION_SOURCES['purchase'].lower()}", "tấn quy khô"),
    ("qty_goods", f"Nguồn {CONSUMPTION_SOURCES['goods'].lower()}", "tấn quy khô"),
    ("revenue_ty", "Doanh thu", "tỷ đồng"),
    # Khối 3 của biểu Tồn kho — tính trên hợp đồng đã ký. KHÁC "Tổng phải giao" bên dưới (phần dài
    # hạn theo cam kết HĐDH, gồm cả sản lượng chưa ký phụ lục) → hai nhãn phải khác nhau (Q4).
    ("remaining", "Đã ký HĐ chưa giao (khối 3)", "tấn quy khô"),
    ("spot_undelivered", "HĐ chuyến chưa giao", "tấn quy khô"),
    ("principle_undelivered", "HĐ nguyên tắc chưa giao", "tấn quy khô"),
    ("lt_remaining", "HĐ dài hạn còn phải giao", "tấn quy khô"),
    # Hợp đồng chưa khai loại vẫn là nợ giao thật: thiếu cột này thì chuyến + dài hạn không cộng ra
    # được "Tổng phải giao" và người đọc không biết phần chênh ở đâu.
    ("unknown_undelivered", "HĐ chưa khai loại chưa giao", "tấn quy khô"),
    ("to_deliver", "Tổng phải giao", "tấn quy khô"),
    ("master_committed", "Cam kết HĐDH", "tấn quy khô"),
    ("master_delivered", "Đã giao theo HĐDH", "tấn quy khô"),
    ("master_pct", "% thực hiện HĐDH", "%"),
]

_BACKLOG_KEYS = ("spot_undelivered", "principle_undelivered", "lt_remaining",
                 "unknown_undelivered", "to_deliver",
                 "master_committed", "master_delivered", "master_pct")


def summary(rep: dict[str, Any]) -> tuple[list[dict], dict, bool]:
    """Dòng theo đơn vị + dòng Tổng cộng của sheet tổng hợp (đúng bảng đang hiện trên web)."""
    backlog = rep.get("backlog") or {}
    rows, totals = [], {k: 0.0 for k, _, _ in SUMMARY_COLS}
    missing_fx = False
    for name in sorted(set(rep["by_company"]) | set(rep["undelivered"]) | set(backlog)):
        c = rep["by_company"].get(name) or {}
        ch = c.get("by_channel") or {}
        src = c.get("by_source") or {}
        rev = c.get("revenue")
        missing_fx = missing_fx or (name in rep["by_company"] and rev is None)
        bl = backlog.get(name) or {}
        row = {
            "label": name, "deliveries": c.get("deliveries", 0),
            "qty": c.get("qty", 0.0), "qty_wet": c.get("qty_wet", 0.0),
            "qty_export": ch.get("export", 0.0), "qty_domestic": ch.get("domestic", 0.0),
            "qty_internal": ch.get("internal", 0.0),
            "qty_exploit": src.get("exploit", 0.0), "qty_purchase": src.get("purchase", 0.0),
            "qty_goods": src.get("goods", 0.0),
            # Doanh thu để TRỐNG khi thiếu tỷ giá — không quy về 0 để khỏi đọc nhầm là "bán không thu tiền".
            "revenue_ty": None if rev is None else rev / TY,
            "remaining": (rep["undelivered"].get(name) or {}).get("qty", 0.0),
            **{k: bl.get(k, 0.0 if k != "master_pct" else None) for k in _BACKLOG_KEYS},
        }
        rows.append(row)
        for k, _, _ in SUMMARY_COLS:
            v = row.get(k)
            if isinstance(v, (int, float)):
                totals[k] += v
    # Tỷ lệ của dòng Tổng cộng chia lại trên tổng — cộng tỷ lệ của từng đơn vị là vô nghĩa.
    committed = totals["master_committed"]
    totals["master_pct"] = totals["master_delivered"] / committed * 100 if committed else None
    return rows, totals, missing_fx
