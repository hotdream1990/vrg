"""Ma trận NGUỒN TIÊU THỤ × CHỦNG LOẠI của Báo cáo tiêu thụ (chốt 05/10/2026).

Trả lời câu đơn vị hỏi: "tiêu thụ từ nguồn nào, theo loại nào". Cộng `by_source_grade` (tấn QUY KHÔ,
tính theo từng dòng chủng loại — xem `sales_contract_report.consumption`) của các đơn vị đang có trong
báo cáo; mỗi chủng loại một dòng: sản lượng theo từng nguồn + tỷ trọng % trong chính chủng loại đó.
Dòng Tổng cộng cho tỷ trọng từng nguồn trên toàn bộ. Bảng trên web dựng cùng phép cộng từ cùng dữ
liệu nên file Excel và màn hình ra một số.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import CONSUMPTION_SOURCES
from app.services.unit_analytics_excel import Col

COLS: list[Col] = [
    ("grade", "Chủng loại", ""),
    *[col for key, label in CONSUMPTION_SOURCES.items()
      for col in ((f"qty_{key}", label, "tấn quy khô"), (f"pct_{key}", label, "% của chủng loại"))],
    ("qty", "Tổng", "tấn quy khô"),
]


def matrix(by_company: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(các dòng chủng loại sắp giảm dần theo tổng, dòng Tổng cộng)."""
    cells: dict[str, dict[str, float]] = {}
    for c in by_company.values():
        for src, grades in (c.get("by_source_grade") or {}).items():
            for grade, qty in (grades or {}).items():
                row = cells.setdefault(grade or "(chưa khai)", {})
                row[src] = row.get(src, 0.0) + (qty or 0.0)
    rows = sorted((_row(g, v) for g, v in cells.items()), key=lambda r: -(r["qty"] or 0.0))
    total = {s: sum(v.get(s, 0.0) for v in cells.values()) for s in CONSUMPTION_SOURCES}
    return rows, _row("Tổng cộng", total)


def _row(label: str, by_src: dict[str, float]) -> dict[str, Any]:
    """Một dòng: tấn theo từng nguồn + % trong dòng. Số 0 để TRỐNG cho bảng dễ đọc."""
    tot = sum(by_src.get(s, 0.0) for s in CONSUMPTION_SOURCES)
    out: dict[str, Any] = {"grade": label, "qty": tot or None}
    for s in CONSUMPTION_SOURCES:
        qty = by_src.get(s, 0.0)
        out[f"qty_{s}"] = qty or None
        out[f"pct_{s}"] = qty / tot * 100 if tot and qty else None
    return out
