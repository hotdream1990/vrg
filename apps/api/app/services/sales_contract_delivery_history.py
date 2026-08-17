"""LỊCH SỬ TỪNG LẦN GIAO của Báo cáo tiêu thụ — mỗi dòng là một lần giao có thật.

Bảng tổng hợp chỉ cho con số cộng dồn theo đơn vị; muốn kiểm "vì sao đơn vị này ra 120 tấn" thì
phải lần được về từng lần giao. Dùng CHUNG `sales_contract_report.deliveries()` với bảng tổng hợp
nên hai nơi không thể lệch số — sửa luật lọc ở đó là cả hai cùng đổi.

Phân trang Ở SERVER: prod đã hơn 3.000 lần giao, trả hết một lượt là tải vài MB cho một màn hình
chỉ hiện được vài chục dòng.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import CONTRACT_TYPES, SALE_CHANNELS
from app.services import customer_repo, sales_contract_report

#: Trần số dòng một trang — chặn client tự nâng `page_size` để kéo cả bảng về.
MAX_PAGE_SIZE = 200


def _grades(lines: list[dict] | None) -> str:
    """Chuỗi chủng loại của một lần giao — gộp trùng, giữ nguyên thứ tự xuất hiện trên phiếu."""
    seen: list[str] = []
    for ln in lines or []:
        g = (ln.get("grade") or "").strip() or "(chưa khai)"
        if g not in seen:
            seen.append(g)
    return ", ".join(seen)


def _shape(r: dict[str, Any], names: dict[int, str]) -> dict[str, Any]:
    """Một dòng lịch sử — đã dịch sẵn nhãn để bảng web không phải mang theo bản đồ nhãn."""
    is_batch = r.get("parent_id") is not None
    return {
        "id": r["id"],
        "delivered_at": r.get("delivered_at"),
        "company": r["company"],
        # Mã của ĐỢT GIAO chỉ là số thứ tự trong hợp đồng ("1", "2"…) nên tự nó vô nghĩa —
        # luôn kèm mã hợp đồng mẹ, không thì không tra ngược được chứng từ.
        "contract_code": r.get("parent_code") or r.get("code"),
        "batch_code": r.get("code") if is_batch else None,
        "customer_name": names.get(r.get("customer_id") or 0),
        "contract_type": CONTRACT_TYPES.get(r.get("contract_type") or ""),
        "channel": SALE_CHANNELS.get(r.get("channel") or ""),
        "grades": _grades(r.get("lines")),
        "qty": r["qty"],
        "qty_dry": r["qty_dry"],
        "qty_wet": r["qty_wet"],
        "revenue": r["revenue"],
        "invoice_no": r.get("invoice_no") or None,
    }


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Lũy kế CẢ KỲ (mọi trang) — bảng chỉ hiện một trang nên người đọc không tự cộng ra được.

    Doanh thu để `None` khi có lần giao thiếu tỷ giá, giống bảng tổng hợp: hiện "—" chứ không
    hiện một con số thiếu mà trông như đủ.
    """
    missing_fx = any(r.get("revenue") is None for r in rows)
    return {
        "qty": sum(r["qty"] for r in rows),
        "qty_dry": sum(r["qty_dry"] for r in rows),
        "qty_wet": sum(r["qty_wet"] for r in rows),
        "revenue": None if missing_fx else sum(r["revenue"] for r in rows),
    }


def history(date_from: str, date_to: str, companies: list[str] | None = None,
            customer_ids: list[int] | None = None, grades: list[str] | None = None,
            page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """Các lần giao trong kỳ, mới nhất trước, đã phân trang.

    Bộ lọc y hệt bảng tổng hợp (đơn vị · khách hàng · chủng loại) nên tổng của mọi trang đúng bằng
    số trên bảng tổng hợp — mở lịch sử ra là đối chiếu được ngay.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    rows = sales_contract_report.deliveries(date_from, date_to, companies, customer_ids, grades)
    # Mới nhất trước: người dùng mở lịch sử để soát lần giao vừa ghi, không phải đọc lại từ đầu kỳ.
    rows.sort(key=lambda r: (r.get("delivered_at") or "", r["id"]), reverse=True)
    page_rows = rows[(page - 1) * page_size: page * page_size]
    # Chỉ tra tên của đúng những khách xuất hiện TRONG TRANG — danh mục cả Tập đoàn rất dài.
    names = customer_repo.names_by_id(companies, sorted({
        r["customer_id"] for r in page_rows if r.get("customer_id")}))
    return {"rows": [_shape(r, names) for r in page_rows], "total": len(rows),
            "totals": _totals(rows), "page": page, "page_size": page_size}
