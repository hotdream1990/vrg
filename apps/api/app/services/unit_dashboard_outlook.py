"""Thẻ "Tiến độ bán hàng năm" của Dashboard đơn vị (phản hồi khách 26/09/2026).

Bốn câu hỏi, cùng một ngày tính `as_of = min(đến ngày, hôm nay)`:
  1. HĐ dài hạn: đã giao bao nhiêu trên sản lượng CAM KẾT của hợp đồng mẹ, còn lại bao nhiêu.
  2. Còn phải giao đến cuối năm = HĐ chuyến đã ký chưa giao + HĐ dài hạn còn lại (`contract_backlog`).
  3. Bán cả năm (dự kiến) = đã giao lũy kế + còn phải giao, so với KH BÁN HÀNG = KH KHAI THÁC + KH
     THU MUA (cột "KH Sản xuất + Thu mua" của biểu Ban TTKD — chủ dự án chốt 26/09/2026).
  4. Doanh thu dự kiến = doanh thu lũy kế + SL còn phải giao × giá bán BQ lũy kế của CHÍNH đơn vị đó.
     Đơn vị chưa có giá BQ (chưa giao lần nào trong năm) → phần đó CHƯA ĐỊNH GIÁ, không mượn giá đơn
     vị khác (cùng tinh thần "không lấy số chỗ khác lấp chỗ trống").

% kế hoạch theo luật RỔ của khối Chỉ tiêu (`unit_dashboard_targets`): tử + mẫu cùng các đơn vị được
giao kế hoạch. Rổ sản lượng chỉ nhận đơn vị ĐÃ NHẬP KH khai thác (kể cả số 0 = không có vườn): đơn vị
mới nhập KH thu mua mà bỏ trống KH khai thác thì kế hoạch đang thiếu nửa — đưa vào là % đội lên hàng
trăm. Số của cả phạm vi vẫn trả riêng để màn hình nói rõ hai rổ khác nhau.
"""

from __future__ import annotations

from typing import Any

from app.services import contract_backlog as cb
from app.services import unit_report_consumption as con
from app.services.unit_dashboard_outlook_calc import aggregate, label_fn, unit_metrics
from app.services.unit_report_query import region_of_units, split_csv, year_plan_by_group


def outlook_block(sc: dict[str, Any], date_to: str, today: str) -> dict[str, Any]:
    as_of = min(date_to, today)
    year = int(as_of[:4])
    f = sc["filters"]
    comps, regs = split_csv(f["companies"]), split_csv(f["regions"])

    def plan(key: str, keep_zero: bool = False) -> dict[str, float]:
        return year_plan_by_group(key, "company", comps, regs, year, f["split_merged"],
                                  keep_zero=keep_zero)[0]

    sold = {r["key"]: r for r in con.consumption_report(
        f"{year}-01-01", as_of, group_by="company", **f)["rows"]}
    back = cb.roll(cb.backlog_on(as_of, sc["units"]), f["split_merged"])
    plans = {"exploit": plan("plan_exploit_tonnes", keep_zero=True),
             "purchase": plan("plan_tonnes"), "revenue": plan("plan_revenue_ty")}
    units = {c: unit_metrics(c, sold.get(c) or {}, back.get(c) or {}, plans)
             for c in {*sold, *back, *(k for p in plans.values() for k in p)}}

    whole = aggregate(list(units.values()))
    label_of = label_fn(sc, region_of_units())
    return {
        "scope": sc["public"], "year": year, "as_of": as_of,
        "lt": {k: whole[f"lt_{k}"] for k in ("committed", "delivered", "remaining", "pct",
                                             "masters", "expired_short", "unlinked_undelivered",
                                             "remaining_after_year")},
        # `lt_remaining` ở đây = HĐ mẹ còn lại + HĐ dài hạn chưa gắn HĐ mẹ; ở khối `lt` chỉ là HĐ mẹ.
        "backlog": {"spot_undelivered": whole["spot_undelivered"],
                    "lt_remaining": whole["backlog_lt_remaining"],
                    "unknown_undelivered": whole["unknown_undelivered"],
                    "to_deliver": whole["to_deliver"]},
        "volume": {"delivered_ytd": whole["delivered_ytd"], "projected": whole["projected"],
                   "plan_exploit": whole["plan_exploit"], "plan_purchase": whole["plan_purchase"],
                   "plan_total": whole["plan_total"], "basket_projected": whole["qty_basket_projected"],
                   "pct": whole["qty_pct"], "units_planned": whole["qty_units_planned"],
                   "units_missing_exploit": whole["units_missing_exploit"],
                   "note": whole["qty_note"]},
        "revenue": {"done_ytd": whole["revenue_ytd"], "expected_rest": whole["revenue_expected_rest"],
                    "projected": whole["revenue_projected"], "plan": whole["plan_revenue"],
                    "basket_projected": whole["revenue_basket_projected"],
                    "pct": whole["revenue_pct"], "units_planned": whole["revenue_units_planned"],
                    "note": whole["revenue_note"]},
        "breakdown": _breakdown(sc, units, label_of) if sc["child"] else [],
        "items": (back.get(sc["public"]["key"]) or {}).get("items") or []
        if sc["public"]["scope"] == "unit" else [],
        "warnings": [w] if (w := whole["bad_price_warning"]) else [],
    }


def _breakdown(sc: dict[str, Any], units: dict[str, dict[str, Any]], label_of) -> list[dict]:  # noqa: ANN001
    """Mỗi khu vực / đơn vị một dòng — khung dòng là DANH SÁCH (cả dòng chưa có số), dòng ngoài
    khung (đơn vị chưa gán khu vực…) xuống cuối để cột cộng lại vẫn bằng tổng ở trên."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for c, m in units.items():
        groups.setdefault(label_of(c), []).append(m)
    extra = sorted(set(groups) - set(sc["children"]))
    out = []
    for label in [*sc["children"], *extra]:
        a = aggregate(groups.get(label) or [])
        out.append({"label": label,
                    "lt_committed": a["lt_committed"], "lt_delivered": a["lt_delivered"],
                    "lt_remaining": a["lt_remaining"], "lt_pct": a["lt_pct"],
                    "spot_undelivered": a["spot_undelivered"], "to_deliver": a["to_deliver"],
                    "delivered_ytd": a["delivered_ytd"], "projected": a["projected"],
                    "plan_exploit": a["plan_exploit"], "plan_purchase": a["plan_purchase"],
                    "plan_total": a["plan_total"], "qty_basket_projected": a["qty_basket_projected"],
                    "qty_pct": a["qty_pct"], "revenue_projected": a["revenue_projected"],
                    "plan_revenue": a["plan_revenue"],
                    "revenue_basket_projected": a["revenue_basket_projected"],
                    "revenue_pct": a["revenue_pct"]})
    return out
