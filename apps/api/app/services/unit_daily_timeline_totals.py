"""Dòng lũy kế của bảng Tiêu thụ – Tồn kho theo ngày (biểu `consumption`).

Bảng này cắt trang Ở SERVER nên web không thể tự cộng: cộng trên màn hình chỉ ra tổng của 50 dòng
đang thấy. Service cộng trên TOÀN BỘ khoảng đang lọc rồi trả về đúng đơn vị hiển thị của bảng.

Hai loại chỉ tiêu, tuyệt đối KHÔNG trộn:

* **Dòng chảy** (tiêu thụ, doanh thu) → CỘNG DỒN cả khoảng.
* **Thời điểm** (tồn kho) → lấy ẢNH CHỤP MỚI NHẤT của TỪNG đơn vị rồi mới cộng ngang các đơn vị.
  Cộng tồn kho của nhiều ngày là đếm đi đếm lại cùng một lô hàng. Ngày của ảnh chụp trả kèm
  (`stock_as_of`) vì có thể sớm hơn ngày cuối khoảng — đơn vị chưa cập nhật tồn.

Công thức phải khớp cột cùng tên ở `apps/web/src/lib/unit-daily-fields.ts` (CONSUMPTION), nếu
không dòng tổng sẽ cãi nhau với chính các dòng phía trên. Khoá của kết quả = khoá cột của bảng.
"""

from __future__ import annotations

from typing import Any

from app.services import unit_daily_repo, unit_report_rows

TY = 1_000_000_000      # doanh thu lưu base = đồng, bảng hiện "tỷ đồng"
TRIEU = 1_000_000       # giá bán bình quân hiện "triệu đ/tấn"


def _num(v: Any) -> float:
    try:
        return 0.0 if v is None else float(v)
    except (TypeError, ValueError):
        return 0.0


def _sale_lines(fields: dict) -> list[dict]:
    """Dòng bán của CẢ 2 bảng: mủ thu mua (`sales`) + mủ khai thác (`sales_own`)."""
    out: list[dict] = []
    for key in ("sales", "sales_own"):
        rows = fields.get(key)
        if isinstance(rows, list):
            out.extend(r for r in rows if isinstance(r, dict))
    return out


def _tonnes(fields: dict, key: str) -> float:
    rows = fields.get(key)
    return sum(_num(r.get("qty")) for r in rows if isinstance(r, dict)) if isinstance(rows, list) else 0.0


def _latest_stock_per_company(entries: list[dict]) -> dict[str, dict]:
    """Bản ghi tồn MỚI NHẤT của từng đơn vị trong khoảng (bỏ qua ngày chỉ có dòng bán).

    Dùng chung quy tắc `has_stock` với màn Thống kê tồn kho và Báo cáo tổng hợp — ba nơi phải ra
    cùng một con số, nếu không người dùng không biết tin màn nào.
    """
    latest: dict[str, dict] = {}
    for e in entries:
        if not unit_report_rows.has_stock(e["fields"]):
            continue
        cur = latest.get(e["company"])
        if cur is None or e["as_of"] > cur["as_of"]:
            latest[e["company"]] = e
    return latest


def consumption_totals(date_from: str, date_to: str,
                       companies: list[str] | None = None) -> dict[str, Any]:
    """Lũy kế cả khoảng cho biểu Tiêu thụ – Tồn kho. Khoá = khoá cột của bảng ở web."""
    entries = unit_daily_repo.in_range("consumption", date_from, date_to, companies,
                                       attach_contracts=False)
    total = export = domestic = revenue = 0.0
    for e in entries:
        revenue += _num(e["fields"].get("revenue"))
        for ln in _sale_lines(e["fields"]):
            qty = _num(ln.get("qty"))
            total += qty
            if ln.get("channel") == "export":
                export += qty
            elif ln.get("channel") == "domestic":
                domestic += qty

    latest = _latest_stock_per_company(entries)
    not_wh = sum(_tonnes(e["fields"], "stock_not_warehoused") for e in latest.values())
    wh = sum(_tonnes(e["fields"], "stock_warehoused") for e in latest.values())
    material = sum(_num(e["fields"].get("stock_material")) for e in latest.values())
    # "Đã ký HĐ chưa giao" là CAM KẾT còn tồn tại NGÀY CUỐI KHOẢNG (không phụ thuộc đơn vị có nhập
    # số ngày đó hay không) — hỏi hợp đồng một lần, giống cách Báo cáo tổng hợp chốt khối này.
    signed = unit_daily_repo.contracts_on(date_to, companies)
    signed_qty = sum(_num(v.get("qty")) for v in signed.values())

    z = lambda v: v or None                                    # noqa: E731 — 0 hiện "—", không phải "0"
    return {
        "total_consumption": z(total),
        "qty_export": z(export),
        "qty_domestic": z(domestic),
        "revenue": z(revenue / TY),
        "avg_price": (revenue / total / TRIEU) if total else None,
        "stock_not_warehoused_t": z(not_wh),
        "stock_warehoused_t": z(wh),
        "stock_finished_t": z(not_wh + wh),
        "stock_signed_t": z(signed_qty),
        "stock_material": z(material),
        # Ngày của ảnh chụp tồn mới nhất — web ghi ra cạnh nhãn để không ai tưởng là số cộng dồn.
        "stock_as_of": max((e["as_of"] for e in latest.values()), default=None),
    }
