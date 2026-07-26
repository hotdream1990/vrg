"""Bảng thống kê TIÊU THỤ — gộp dòng bán theo bộ lọc, hoặc trả CHI TIẾT từng dòng.

Dòng nhập USD thiếu tỷ giá không được tính vào doanh thu/giá BQ (không đoán số) và được cảnh báo;
doanh thu đã lưu của ngày lệch tổng các dòng cũng được cảnh báo để rà lại.
"""

from __future__ import annotations

from typing import Any

from app.services import unit_report_rows as rows_mod
from app.services.unit_report_query import (
    CHANNEL_LABELS, CONTRACT_LABELS, GROUPERS, avg, filter_scope, sort_groups, split_csv,
)
from app.services.unit_report_rows import SOURCE_LABELS, TRIEU


#: Ngưỡng coi là LỆCH giữa doanh thu đã lưu của ngày và tổng các dòng bán (bỏ qua sai số làm tròn).
_MISMATCH_PCT = 0.01
_MISMATCH_ABS = 1_000_000        # 1 triệu đồng


def _revenue_mismatches(days: list[dict]) -> list[str]:
    """Bản ghi có doanh thu ĐÃ LƯU khác tổng các dòng bán → dấu hiệu số liệu cần rà lại.

    Thường gặp khi đơn vị sửa loại tiền của dòng sau lúc lưu (giá USD bị cộng như VNĐ hoặc ngược lại).
    Chỉ CẢNH BÁO — báo cáo vẫn lấy số tính lại từ các dòng, không tự sửa dữ liệu gốc.
    """
    bad = []
    for d in days:
        stored, lines = d.get("revenue_stored"), d.get("revenue_lines") or 0.0
        if stored is None:
            continue
        gap = abs(stored - lines)
        if gap > _MISMATCH_ABS and gap > _MISMATCH_PCT * max(abs(stored), abs(lines), 1):
            bad.append(f"{d['company']} ({d['as_of']})")
    if not bad:
        return []
    head = ", ".join(bad[:3]) + (f" và {len(bad) - 3} bản ghi khác" if len(bad) > 3 else "")
    return [f"{len(bad)} bản ghi có doanh thu đã lưu lệch với tổng các dòng bán — cần rà lại: {head}."]


def _new_consumption(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region, "qty": 0.0,
            "qty_long_term": 0.0, "qty_spot": 0.0, "qty_export": 0.0, "qty_domestic": 0.0,
            "revenue_vnd": 0.0, "_rev_qty": 0.0, "lines": 0, "_days": set()}


def _feed_consumption(g: dict, r: dict) -> None:
    qty = r["qty"] or 0.0
    g["qty"] += qty
    g["qty_long_term" if r["contract"] == "long_term" else "qty_spot"] += qty
    g["qty_export" if r["channel"] == "export" else "qty_domestic"] += qty
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
    for k in ("qty", "qty_long_term", "qty_spot", "qty_export", "qty_domestic", "revenue_vnd"):
        g[k] = g[k] or None
    return g


def consumption_report(date_from: str, date_to: str, *, companies: str | None = None,
                       regions: str | None = None, grades: str | None = None,
                       contract: str | None = None, channel: str | None = None,
                       source: str | None = None, group_by: str = "company") -> dict[str, Any]:
    """Bảng thống kê Tiêu thụ (đơn vị · khu vực · chủng loại · loại HĐ · hình thức · nguồn mủ).

    `group_by='none'` → trả DÒNG CHI TIẾT từng lần bán (để đối chiếu chứng từ).
    """
    comps, regs = split_csv(companies), split_csv(regions)
    data = rows_mod.consumption_rows(date_from, date_to, comps)
    rows = filter_scope(data["rows"], comps, regs)
    # Cảnh báo đối chiếu tính TRƯỚC các bộ lọc chi tiết (lọc 1 chủng loại thì lệch là đương nhiên).
    warnings = _revenue_mismatches(filter_scope(data["days"], comps, regs))
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
        # Nhãn tiếng Việt gắn sẵn để bảng web và file Excel dùng chung, không dịch 2 nơi.
        detail = [{**r, "source_label": SOURCE_LABELS.get(r["source"], r["source"]),
                   "contract_label": CONTRACT_LABELS.get(r["contract"], r["contract"]),
                   "channel_label": CHANNEL_LABELS.get(r["channel"], r["channel"])} for r in rows]
        return {**base, "detail": True, "rows": detail}

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
