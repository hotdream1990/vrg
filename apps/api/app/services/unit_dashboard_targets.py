"""Phần "Chỉ tiêu năm" của Dashboard đơn vị — thực hiện LŨY KẾ từ 01/01 so với kế hoạch năm.

Vì sao lũy kế mà không theo kỳ đang xem: chỉ tiêu là số của CẢ NĂM, đem một tháng ra so thì đơn vị
nào cũng "đạt 8%" — con số đúng mà vô nghĩa. Mốc so tiến độ là % thời gian đã qua của năm.

Ba chỉ tiêu, cùng quy ước với Báo cáo tổng hợp:
- Thu mua: tử số = mủ NGUYÊN LIỆU (nước + chén + dây, quy khô), không gồm thành phẩm mua ngoài.
- Tiêu thụ: kế hoạch chỉ đặt cho HĐ CHUYẾN → so với sản lượng HĐ chuyến, không so tổng tiêu thụ.
- Doanh thu (tỷ đồng): đơn vị có lần giao chưa tính được doanh thu (thiếu tỷ giá hoặc đơn giá) thì
  doanh thu đang THIẾU → % để trống.

⚠ Tử số và mẫu số cùng MỘT RỔ ĐƠN VỊ — các đơn vị ĐƯỢC GIAO chỉ tiêu đó (kể cả đơn vị chưa làm
được gì: bỏ họ ra là % tự đẹp lên). Đơn vị chưa được giao mà vẫn có số thì KHÔNG vào tử số: đo trên
bản sao prod 24/09/2026 mới 1/64 đơn vị có kế hoạch doanh thu, cộng doanh thu cả Tập đoàn chia cho
kế hoạch của một đơn vị là ra hàng nghìn %. Tổng cả phạm vi vẫn được nói ra trong `note`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services import unit_report_consumption as con
from app.services import unit_report_purchase as pur
from app.services.unit_report_query import (
    NO_REGION_LABEL, region_of_units, split_csv, year_plan_by_group,
)
from app.services.weekly_ai_compose import vn

#: (khoá, nhãn, đơn vị, cột kế hoạch năm, trường thực hiện, bảng nguồn, lời giải thích)
_ITEMS = (
    ("purchase", "Thu mua mủ nguyên liệu", "tấn", "plan_tonnes", "qty_material", "purchase",
     "Mủ nước + mủ chén + mủ dây (quy khô), không gồm thành phẩm mua ngoài."),
    ("sales_spot", "Tiêu thụ HĐ chuyến", "tấn", "plan_sales_spot_tonnes", "qty_spot", "consumption",
     "Kế hoạch tiêu thụ chỉ giao cho hợp đồng chuyến."),
    ("revenue", "Doanh thu", "tỷ đồng", "plan_revenue_ty", "revenue_ty", "consumption", ""),
)


def time_pct(day: str) -> float:
    """% thời gian đã qua của năm tính đến hết ngày `day` (mốc để so tiến độ chỉ tiêu)."""
    d = date.fromisoformat(day)
    total = (date(d.year + 1, 1, 1) - date(d.year, 1, 1)).days
    return ((d - date(d.year, 1, 1)).days + 1) / total * 100


def _progress(planned: list[str], plan: dict[str, float], done: dict[str, float | None],
              blocked: set[str]) -> dict[str, Any]:
    """Tiến độ của một rổ đơn vị ĐƯỢC GIAO chỉ tiêu. Rổ rỗng → chưa giao chỉ tiêu (tất cả None)."""
    plan_sum = sum(plan[c] for c in planned)
    if not plan_sum:
        return {"done": None, "plan": None, "pct": None, "units_planned": 0}
    got = sum(done.get(c) or 0.0 for c in planned)
    pct = None if any(c in blocked for c in planned) else got / plan_sum * 100
    return {"done": got, "plan": plan_sum, "pct": pct, "units_planned": len(planned)}


def _note(base: str, prog: dict[str, Any], scope_done: float, unit: str, missing: int) -> str:
    parts = [base] if base else []
    if missing:
        parts.append(f"{missing} lần giao chưa tính được doanh thu (thiếu tỷ giá hoặc đơn giá) — "
                     f"doanh thu đang thiếu phần đó nên chưa tính % kế hoạch.")
    # So sánh có dung sai: hai tổng số thực cộng theo hai thứ tự khác nhau có thể lệch ở số lẻ xa.
    if prog["plan"] and scope_done - (prog["done"] or 0.0) > 1e-6:
        parts.append(f"% chỉ tính trên {prog['units_planned']} đơn vị đã giao kế hoạch; cả phạm vi "
                     f"thực hiện {vn(scope_done)} {unit}.")
    return " ".join(parts)


def targets_block(sc: dict[str, Any], date_to: str, today: str) -> dict[str, Any]:
    end = min(date_to, today)
    year = int(end[:4])
    start = f"{year}-01-01"
    f = sc["filters"]
    comps, regs = split_csv(f["companies"]), split_csv(f["regions"])
    # Một lượt đọc mỗi bảng, theo ĐƠN VỊ — cả tổng lẫn từng khu vực đều cộng lại từ rổ đơn vị được
    # giao kế hoạch, nên không cần thêm lượt `group_by=region`.
    reps = {"purchase": pur.purchase_report(start, end, group_by="company", **f),
            "consumption": con.consumption_report(start, end, group_by="company", **f)}
    rows = {src: {r["key"]: r for r in rep["rows"]} for src, rep in reps.items()}
    blocked = {k for k, r in rows["consumption"].items() if r.get("no_revenue_lines")}
    region_of = region_of_units()

    items, per_item = [], {}
    for key, label, unit, plan_key, field, src, base in _ITEMS:
        plan = year_plan_by_group(plan_key, "company", comps, regs, year, f["split_merged"])[0]
        done = {k: r.get(field) for k, r in rows[src].items()}
        stop = blocked if key == "revenue" else set()
        prog = _progress([c for c in plan if plan[c]], plan, done, stop)
        missing = sum(rows["consumption"][c].get("no_revenue_lines") or 0
                      for c in plan if c in stop) if key == "revenue" else 0
        scope_done = reps[src]["totals"].get(field) or 0.0
        items.append({"key": key, "label": label, "unit": unit, "done": prog["done"],
                      "plan": prog["plan"], "pct": prog["pct"],
                      "units_planned": prog["units_planned"],
                      "note": _note(base, prog, scope_done, unit, missing)})
        per_item[key] = (plan, done, stop)

    return {
        "scope": sc["public"], "year": year, "date_from": start, "date_to": end,
        "time_pct": time_pct(end), "items": items,
        "breakdown": _breakdown(sc, per_item, region_of) if sc["child"] else [],
        # Cảnh báo của bảng thống kê (thiếu đơn giá, thiếu tỷ giá…) đã hiện ở section của kỳ; chỗ
        # duy nhất đụng tới chỉ tiêu — doanh thu chưa tính được — nằm trong `note` của mục đó.
        "warnings": [],
    }


def _breakdown(sc: dict[str, Any], per_item: dict[str, tuple], region_of: dict[str, str | None],
               ) -> list[dict[str, Any]]:
    """Tiến độ từng khu vực / đơn vị — khung dòng là DANH SÁCH, không phải "ai có số".

    Đơn vị được giao kế hoạch mà chưa thực hiện gì không có dòng nào trong bảng thống kê; bỏ qua
    họ thì bảng chỉ còn toàn đơn vị đang chạy tốt. Ngược lại, đơn vị CÓ kế hoạch mà nằm ngoài khung
    (chưa gán khu vực, khu vực đã ẩn) thành dòng riêng ở cuối — không thì tổng ở trên có phần của họ
    mà bảng dưới không thấy đâu.
    """
    def label_of(c: str) -> str:
        return c if sc["child"] == "company" else (region_of.get(c) or NO_REGION_LABEL)

    planned = {c for plan, _, _ in per_item.values() for c in plan if plan[c]}
    extra = sorted({label_of(c) for c in planned} - set(sc["children"]))
    out = []
    for child in [*sc["children"], *extra]:
        row: dict[str, Any] = {"label": child}
        for key, (plan, done, stop) in per_item.items():
            members = [c for c in plan if plan[c] and label_of(c) == child]
            row[f"{key}_pct"] = _progress(members, plan, done, stop)["pct"]
        out.append(row)
    return out
