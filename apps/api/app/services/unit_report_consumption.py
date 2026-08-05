"""Bảng thống kê TIÊU THỤ — gộp dòng bán theo bộ lọc, hoặc trả CHI TIẾT từng dòng.

Nguồn số: các LẦN GIAO của hợp đồng (chốt 02/08/2026). Dòng nhập USD thiếu tỷ giá không được tính
vào doanh thu/giá BQ (không đoán số) và được cảnh báo; kỳ còn dữ liệu cũ chưa chuyển đổi cũng được
cảnh báo để không ai đọc nhầm số 0.
"""

from __future__ import annotations

from typing import Any

from app.services import legacy_data_notice, unit_report_rows as rows_mod
from app.services.unit_report_query import (
    CHANNEL_LABELS, CONTRACT_LABELS, GROUPERS, avg, filter_scope, label_of, sort_groups, split_csv,
)
from app.services.unit_report_rows import SOURCE_LABELS, TRIEU


def _new_consumption(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region, "qty": 0.0,
            "qty_long_term": 0.0, "qty_spot": 0.0, "qty_unknown_type": 0.0,
            "qty_export": 0.0, "qty_domestic": 0.0, "qty_internal": 0.0,
            "revenue_vnd": 0.0, "_rev_qty": 0.0, "lines": 0, "_days": set()}


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


def consumption_report(date_from: str, date_to: str, *, companies: str | None = None,
                       regions: str | None = None, grades: str | None = None,
                       contract: str | None = None, channel: str | None = None,
                       source: str | None = None, group_by: str = "company",
                       limit: int | None = None, offset: int = 0) -> dict[str, Any]:
    """Bảng thống kê Tiêu thụ (đơn vị · khu vực · chủng loại · loại HĐ · hình thức · nguồn mủ).

    `group_by='none'` → trả DÒNG CHI TIẾT từng lần bán (để đối chiếu chứng từ).
    """
    comps, regs = split_csv(companies), split_csv(regions)
    data = rows_mod.consumption_rows(date_from, date_to, comps)
    rows = filter_scope(data["rows"], comps, regs)
    # Kỳ còn dữ liệu cũ chưa chuyển đổi → nói rõ, nếu không người đọc hiểu 0 tấn là "không bán gì".
    warnings = legacy_data_notice.warnings(date_from, date_to, comps)
    for field, val in (("grade", grades), ("contract", contract), ("channel", channel), ("source", source)):
        if vals := split_csv(val):
            keep = set(vals)
            rows = [r for r in rows if r[field] in keep]

    total = _new_consumption("Tổng cộng", None)
    for r in rows:
        _feed_consumption(total, r)
    if (n := sum(1 for r in rows if r.get("missing_fx"))):
        warnings.append(f"{n} dòng bán bằng USD nhưng thiếu tỷ giá — chưa tính vào doanh thu & giá bán BQ.")

    base = {"kind": "consumption", "date_from": date_from, "date_to": date_to, "group_by": group_by,
            "totals": _close_consumption(total), "warnings": warnings}
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
    return {**base, "detail": False,
            "rows": [_close_consumption(g) for g in sort_groups(groups, group_by)]}
