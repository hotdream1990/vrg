"""Bảng thống kê TIÊU THỤ — gộp dòng bán theo bộ lọc, hoặc trả CHI TIẾT từng dòng.

Nguồn số: các LẦN GIAO của hợp đồng (chốt 02/08/2026). Dòng nhập USD thiếu tỷ giá không được tính
vào doanh thu/giá BQ (không đoán số) và được cảnh báo.

Kèm % THỰC HIỆN so với kế hoạch tiêu thụ HĐ chuyến và kế hoạch doanh thu (chỉ tiêu NĂM ở màn
"Kế hoạch năm") — xem `_attach_plan`.
"""

from __future__ import annotations

from typing import Any

from app.services import config_repo
from app.services import unit_report_rows as rows_mod
from app.services.anomaly_types import THRESHOLDS, vn_num
from app.services.unit_report_query import (
    CHANNEL_LABELS, CONTRACT_LABELS, GROUPERS, avg, filter_scope, label_of, merge_rollup,
    merge_scope, merge_view, sort_groups, split_csv, year_plan_by_group,
)
from app.services.unit_report_rows import SOURCE_LABELS, TRIEU


def _new_consumption(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region, "qty": 0.0,
            "qty_long_term": 0.0, "qty_spot": 0.0, "qty_principle": 0.0, "qty_unknown_type": 0.0,
            "qty_export": 0.0, "qty_domestic": 0.0, "qty_internal": 0.0,
            "revenue_vnd": 0.0, "_rev_qty": 0.0, "lines": 0, "_days": set(),
            # Số lần giao CHƯA TÍNH ĐƯỢC doanh thu (thiếu tỷ giá hoặc thiếu đơn giá) — nơi đem doanh
            # thu so kế hoạch cần biết để để trống % như Báo cáo tổng hợp (`total_revenue_vnd` ra
            # None vì BẤT KỲ dòng nào thiếu), thay vì báo tỷ lệ thấp hơn thực tế.
            "no_revenue_lines": 0,
            # Số dòng bán có đơn giá vượt trần — nghi gõ ĐỒNG vào ô TRIỆU đồng (xem `is_bad_price`).
            # Doanh thu vẫn cộng như đã khai (không tự sửa số), nơi so kế hoạch dựa cờ này để trống %.
            "bad_price_lines": 0,
            # Rổ % KH doanh thu: chỉ dòng của đơn vị ĐƯỢC GIAO KH doanh thu — xem `_attach_plan`.
            "_plan_rev": 0.0, "_plan_blocked": False}


#: Giá trị enum → ô cộng dồn. Giá trị lạ/thiếu đi vào ô "chưa khai" riêng, KHÔNG dồn vào ô nào
#: khác: dồn "single/multi" vào "HĐ chuyến" từng làm chỉ tiêu HĐ dài hạn về 0.
_TYPE_BUCKET = {"long_term": "qty_long_term", "spot": "qty_spot", "principle": "qty_principle"}
_CHANNEL_BUCKET = {"export": "qty_export", "domestic": "qty_domestic", "internal": "qty_internal"}


def _feed_consumption(g: dict, r: dict, rev_planned: frozenset[str] = frozenset()) -> None:
    qty = r["qty"] or 0.0
    g["qty"] += qty
    g[_TYPE_BUCKET.get(r["contract"] or "", "qty_unknown_type")] += qty
    ch = _CHANNEL_BUCKET.get(r["channel"] or "")
    if ch:
        g[ch] += qty
    g["lines"] += 1
    g["bad_price_lines"] += 1 if r.get("bad_price") else 0
    g["_days"].add((r["company"], r["as_of"]))
    if r["revenue_vnd"] is not None:
        g["revenue_vnd"] += r["revenue_vnd"]
        g["_rev_qty"] += qty
    elif qty:
        g["no_revenue_lines"] += 1
    if r["company"] in rev_planned:
        g["_plan_rev"] += r["revenue_vnd"] or 0.0
        g["_plan_blocked"] |= bool(r.get("bad_price") or (r["revenue_vnd"] is None and qty))


#: Khoá ngưỡng DÙNG CHUNG với luật "Giá bán sai đơn vị tính" của màn Cảnh báo bất thường — admin sửa
#: một chỗ ở Cấu hình hệ thống thì dashboard và trang cảnh báo cùng đổi, không có hai mức trần.
_PRICE_CEILING_KEY = "ANOMALY_SALE_PRICE_MAX"


def sale_price_ceiling() -> float:
    """Trần đơn giá bán quy đổi (triệu đ/tấn) đang áp dụng: đã lưu thì lấy, chưa thì mặc định."""
    default = float(THRESHOLDS[_PRICE_CEILING_KEY]["default"])
    try:
        return float(config_repo.get_value(_PRICE_CEILING_KEY) or default) or default
    except (TypeError, ValueError):
        return default


def is_bad_price(r: dict, ceiling: float) -> bool:
    """Đơn giá quy về triệu đ/tấn vượt trần → gần như chắc chắn gõ nhầm đơn vị tính.

    VND: ô đơn giá đã là triệu đ/tấn. Ngoại tệ: quy đổi bằng tỷ giá CỦA CHÍNH DÒNG đó; thiếu tỷ giá
    thì KHÔNG xét — dòng đó đã nằm ngoài doanh thu (cảnh báo thiếu tỷ giá riêng), đoán tỷ giá để soi
    giá là bịa dữ kiện. Cùng công thức với `anomaly_rules._wrong_sale_price`.
    """
    price = r.get("price")
    if price is None:
        return False
    if (r.get("ccy") or "VND") == "VND":
        return price > ceiling
    return bool(r.get("fx")) and price * r["fx"] / 1_000_000 > ceiling


def _bad_price_warning(rows: list[dict], ceiling: float) -> str | None:
    bad = [r for r in rows if r.get("bad_price")]
    if not bad:
        return None
    names = list(dict.fromkeys(r["company"] for r in bad))
    shown = ", ".join(names[:5]) + ("…" if len(names) > 5 else "")
    return (f"{len(bad)} dòng bán có đơn giá vượt {vn_num(ceiling)} triệu đ/tấn (nghi nhập đồng thay "
            f"cho triệu đồng) — doanh thu & giá bán BQ đang bị đội lên: {shown}.")


def _close_consumption(g: dict) -> dict[str, Any]:
    rev_qty = g.pop("_rev_qty")
    g["days"] = len(g.pop("_days"))
    # Giá bán BQ = doanh thu ÷ sản lượng CÓ doanh thu (bỏ dòng thiếu tỷ giá, tránh kéo giá xuống).
    price = avg(g["revenue_vnd"], rev_qty)
    g["avg_price_trieu"] = (price / TRIEU) if price is not None else None
    g["revenue_ty"] = (g["revenue_vnd"] / 1_000_000_000) or None
    for k in ("qty", "qty_long_term", "qty_spot", "qty_principle", "qty_unknown_type",
              "qty_export", "qty_domestic", "qty_internal", "revenue_vnd"):
        g[k] = g[k] or None
    return g


#: Kế hoạch tiêu thụ CHỈ đặt cho HĐ CHUYẾN → % thực hiện so với sản lượng HĐ chuyến, KHÔNG so với
#: tổng tiêu thụ (so tổng thì đơn vị nào cũng "vượt kế hoạch" giả tạo vì HĐ dài hạn được cộng vào
#: tử số mà không có trong mẫu số). HĐ nguyên tắc cũng KHÔNG vào tử số (chủ dự án chốt 01/10/2026:
#: "HĐ chuyến là HĐ chuyến, nguyên tắc là riêng"). Cùng quy ước với "Báo cáo tổng hợp".
_PLAN_KEY = "plan_sales_spot_tonnes"


def _attach_plan(g: dict, spot_plan: float | None, revenue_plan: float | None,
                 partial: bool = False) -> None:
    """Gắn chỉ tiêu + % thực hiện vào 1 dòng. Chưa giao kế hoạch thì để TRỐNG, không ghi 0%.

    % KH doanh thu (tỷ đồng) cùng luật Dashboard (`unit_dashboard_targets._progress`): tử số chỉ gồm
    doanh thu của đơn vị ĐƯỢC GIAO KH doanh thu (đo prod 29/09/2026: 27/62 đơn vị có KH — chia doanh
    thu cả Tập đoàn cho KH của 27 đơn vị ra 213% thay vì 80,6%). Đơn vị trong rổ có lần giao thiếu tỷ
    giá/đơn giá (doanh thu đang THIẾU) hoặc đơn giá vượt trần (doanh thu đang bị ĐỘI LÊN) thì để
    TRỐNG — không coi là 0, không báo một tỷ lệ sai. % KH chuyến vẫn Σ/Σ cả nhóm (chờ chốt luật rổ).
    """
    rev, blocked = g.pop("_plan_rev"), g.pop("_plan_blocked")
    g["plan_sales_spot_tonnes"] = spot_plan or None
    g["pct_plan_sales_spot"] = ((g["qty_spot"] or 0.0) / spot_plan * 100) if spot_plan else None
    g["plan_revenue_ty"] = revenue_plan or None
    g["pct_plan_revenue"] = (rev / 1_000_000_000 / revenue_plan * 100
                             if revenue_plan and not blocked and not partial else None)


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
    ceiling = sale_price_ceiling()
    rows = [{**r, "bad_price": is_bad_price(r, ceiling)} for r in rows]

    # Kế hoạch là chỉ tiêu NĂM → lấy theo năm của ngày CUỐI kỳ. Kỳ vắt qua 2 năm thì tử số có cả
    # sản lượng năm trước trong khi mẫu số chỉ là kế hoạch 1 năm → phải nói rõ, đừng để đọc nhầm.
    year = int(date_to[:4])
    plan_by_key, plan_total = year_plan_by_group(_PLAN_KEY, group_by, comps, regs, year,
                                                 split_merged)
    rev_unit, rev_plan_total = year_plan_by_group("plan_revenue_ty", "company", comps, regs, year,
                                                  split_merged)
    rev_plan_by_key = rev_unit if group_by == "company" else year_plan_by_group(
        "plan_revenue_ty", group_by, comps, regs, year, split_merged)[0]
    rev_planned = frozenset(c for c, v in rev_unit.items() if v)
    # Lọc chủng loại / loại HĐ / hình thức / nguồn mủ thì doanh thu chỉ còn một phần, mẫu số vẫn là
    # KH cả năm → % KH doanh thu để TRỐNG (cùng cách màn Thu mua khi lọc loại mủ/chủng loại).
    partial = any(split_csv(v) for v in (grades, contract, channel, source))

    total = _new_consumption("Tổng cộng", None)
    for r in rows:
        _feed_consumption(total, r, rev_planned)
    if (n := sum(1 for r in rows if r.get("missing_fx"))):
        warnings.append(f"{n} dòng bán bằng USD nhưng thiếu tỷ giá — chưa tính vào doanh thu & giá bán BQ.")
    if (n := sum(1 for r in rows if r["revenue_vnd"] is None and r["qty"] and not r.get("missing_fx"))):
        warnings.append(f"{n} dòng bán chưa có đơn giá — chưa tính vào doanh thu & giá bán BQ.")
    if msg := _bad_price_warning(rows, ceiling):
        warnings.append(msg)

    totals = _close_consumption(total)
    _attach_plan(totals, plan_total, rev_plan_total, partial)
    if (plan_total or rev_plan_total) and date_from[:4] != date_to[:4]:
        warnings.append(f"% kế hoạch tiêu thụ / doanh thu đang so với chỉ tiêu NĂM {year}, trong khi "
                        f"kỳ xem bắt đầu từ năm {date_from[:4]} — chỉ để tham khảo.")

    base = {"kind": "consumption", "date_from": date_from, "date_to": date_to, "group_by": group_by,
            "totals": totals, "warnings": warnings, "price_ceiling": ceiling}
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
        _feed_consumption(g, r, rev_planned)
    out: list[dict[str, Any]] = []
    for g in sort_groups(groups, group_by):
        row = _close_consumption(g)
        # Nhóm khác đơn vị/khu vực → để trống.
        _attach_plan(row, plan_by_key.get(row["key"]), rev_plan_by_key.get(row["key"]), partial)
        out.append(row)
    return {**base, "detail": False, "rows": out}
