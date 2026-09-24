"""Bảng thống kê TIÊU THỤ — gộp dòng bán theo bộ lọc, hoặc trả CHI TIẾT từng dòng.

Nguồn số: các LẦN GIAO của hợp đồng (chốt 02/08/2026). Dòng nhập USD thiếu tỷ giá không được tính
vào doanh thu/giá BQ (không đoán số) và được cảnh báo.

Kèm % THỰC HIỆN so với kế hoạch tiêu thụ (chỉ tiêu NĂM ở màn "Kế hoạch năm") — xem `_spot_plan`.
"""

from __future__ import annotations

from typing import Any

from app.services import unit_report_rows as rows_mod
from app.services.unit_report_query import (
    CHANNEL_LABELS, CONTRACT_LABELS, GROUPERS, avg, filter_scope, label_of, merge_rollup,
    merge_scope, merge_view, sort_groups, split_csv, year_plan_by_group,
)
from app.services.unit_report_rows import SOURCE_LABELS, TRIEU


def _new_consumption(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region, "qty": 0.0,
            "qty_long_term": 0.0, "qty_spot": 0.0, "qty_unknown_type": 0.0,
            "qty_export": 0.0, "qty_domestic": 0.0, "qty_internal": 0.0,
            "revenue_vnd": 0.0, "_rev_qty": 0.0, "lines": 0, "_days": set(),
            # Số lần giao THIẾU TỶ GIÁ (không có trong doanh thu) — nơi đem doanh thu so kế hoạch
            # cần biết để để trống % (như Báo cáo tổng hợp), thay vì báo tỷ lệ thấp hơn thực tế.
            "missing_fx_lines": 0}


#: Giá trị enum → ô cộng dồn. Giá trị lạ/thiếu đi vào ô "chưa khai" riêng, KHÔNG dồn vào ô nào
#: khác: dồn "single/multi" vào "HĐ chuyến" từng làm chỉ tiêu HĐ dài hạn về 0.
_TYPE_BUCKET = {"long_term": "qty_long_term", "spot": "qty_spot"}
_CHANNEL_BUCKET = {"export": "qty_export", "domestic": "qty_domestic", "internal": "qty_internal"}


def _feed_consumption(g: dict, r: dict) -> None:
    qty = r["qty"] or 0.0
    g["qty"] += qty
    g[_TYPE_BUCKET.get(r["contract"] or "", "qty_unknown_type")] += qty
    ch = _CHANNEL_BUCKET.get(r["channel"] or "")
    if ch:
        g[ch] += qty
    g["lines"] += 1
    g["_days"].add((r["company"], r["as_of"]))
    if r["revenue_vnd"] is not None:
        g["revenue_vnd"] += r["revenue_vnd"]
        g["_rev_qty"] += qty
    if r.get("missing_fx"):
        g["missing_fx_lines"] += 1


def _close_consumption(g: dict) -> dict[str, Any]:
    rev_qty = g.pop("_rev_qty")
    g["days"] = len(g.pop("_days"))
    # Giá bán BQ = doanh thu ÷ sản lượng CÓ doanh thu (bỏ dòng thiếu tỷ giá, tránh kéo giá xuống).
    price = avg(g["revenue_vnd"], rev_qty)
    g["avg_price_trieu"] = (price / TRIEU) if price is not None else None
    g["revenue_ty"] = (g["revenue_vnd"] / 1_000_000_000) or None
    for k in ("qty", "qty_long_term", "qty_spot", "qty_unknown_type",
              "qty_export", "qty_domestic", "qty_internal", "revenue_vnd"):
        g[k] = g[k] or None
    return g


#: Kế hoạch tiêu thụ CHỈ đặt cho HĐ CHUYẾN → % thực hiện so với sản lượng HĐ chuyến, KHÔNG so với
#: tổng tiêu thụ (so tổng thì đơn vị nào cũng "vượt kế hoạch" giả tạo vì HĐ dài hạn được cộng vào
#: tử số mà không có trong mẫu số). Cùng quy ước với "Báo cáo tổng hợp" — xem `unit_period_report`.
_PLAN_KEY = "plan_sales_spot_tonnes"


def _attach_plan(g: dict, plan: float | None) -> None:
    """Gắn chỉ tiêu + % thực hiện vào 1 dòng. Chưa giao kế hoạch thì để TRỐNG, không ghi 0%."""
    g["plan_sales_spot_tonnes"] = plan or None
    g["pct_plan_sales_spot"] = ((g["qty_spot"] or 0.0) / plan * 100) if plan else None


def consumption_report(date_from: str, date_to: str, *, companies: str | None = None,
                       regions: str | None = None, grades: str | None = None,
                       contract: str | None = None, channel: str | None = None,
                       source: str | None = None, group_by: str = "company",
                       limit: int | None = None, offset: int = 0,
                       split_merged: bool = False) -> dict[str, Any]:
    """Bảng thống kê Tiêu thụ (đơn vị · khu vực · chủng loại · loại HĐ · hình thức · nguồn mủ).

    `group_by='none'` → trả DÒNG CHI TIẾT từng lần bán (để đối chiếu chứng từ).
    `split_merged=True` → tách riêng đơn vị đã sáp nhập; mặc định gộp vào đơn vị hiện hành.
    """
    comps, regs = split_csv(companies), split_csv(regions)
    # Mốc xét sáp nhập là NGÀY CUỐI KỲ (xem `unit_report_purchase.purchase_report`).
    data = rows_mod.consumption_rows(date_from, date_to, merge_scope(comps, split_merged))
    rows = filter_scope(merge_rollup(data["rows"], split_merged),
                        merge_view(comps, split_merged), regs)
    warnings: list[str] = []
    for field, val in (("grade", grades), ("contract", contract), ("channel", channel), ("source", source)):
        if vals := split_csv(val):
            keep = set(vals)
            rows = [r for r in rows if r[field] in keep]

    total = _new_consumption("Tổng cộng", None)
    for r in rows:
        _feed_consumption(total, r)
    if (n := sum(1 for r in rows if r.get("missing_fx"))):
        warnings.append(f"{n} dòng bán bằng USD nhưng thiếu tỷ giá — chưa tính vào doanh thu & giá bán BQ.")

    # Kế hoạch là chỉ tiêu NĂM → lấy theo năm của ngày CUỐI kỳ. Kỳ vắt qua 2 năm thì tử số có cả
    # sản lượng năm trước trong khi mẫu số chỉ là kế hoạch 1 năm → phải nói rõ, đừng để đọc nhầm.
    year = int(date_to[:4])
    plan_by_key, plan_total = year_plan_by_group(_PLAN_KEY, group_by, comps, regs, year,
                                                 split_merged)
    totals = _close_consumption(total)
    _attach_plan(totals, plan_total)
    if plan_total and date_from[:4] != date_to[:4]:
        warnings.append(f"% kế hoạch tiêu thụ đang so với chỉ tiêu NĂM {year}, trong khi kỳ xem bắt "
                        f"đầu từ năm {date_from[:4]} — chỉ để tham khảo.")

    base = {"kind": "consumption", "date_from": date_from, "date_to": date_to, "group_by": group_by,
            "totals": totals, "warnings": warnings}
    if group_by == "none":
        rows.sort(key=lambda r: (r["as_of"], r["company"]))
        # Chế độ CHI TIẾT trả từng lần bán nên số dòng tăng theo ngày (đã hơn 3.000) → cắt trang.
        # Dòng "Tổng cộng" vẫn tính trên TOÀN BỘ dữ liệu khớp lọc, không phải trên trang đang xem.
        total = len(rows)
        page_rows = rows[offset:offset + limit] if limit else rows
        # Nhãn tiếng Việt gắn sẵn để bảng web và file Excel dùng chung, không dịch 2 nơi.
        detail = [{**r, "source_label": SOURCE_LABELS.get(r["source"], r["source"]),
                   "contract_label": label_of(CONTRACT_LABELS, r["contract"]),
                   "channel_label": label_of(CHANNEL_LABELS, r["channel"])} for r in page_rows]
        return {**base, "detail": True, "rows": detail, "total": total}

    key_of = GROUPERS[group_by]
    groups: dict[str, dict] = {}
    for r in rows:
        k = key_of(r)
        if k is None:
            continue
        g = groups.get(k) or groups.setdefault(k, _new_consumption(k, r.get("region") if group_by == "company" else None))
        _feed_consumption(g, r)
    out: list[dict[str, Any]] = []
    for g in sort_groups(groups, group_by):
        row = _close_consumption(g)
        _attach_plan(row, plan_by_key.get(row["key"]))     # nhóm khác đơn vị/khu vực → để trống
        out.append(row)
    return {**base, "detail": False, "rows": out}
