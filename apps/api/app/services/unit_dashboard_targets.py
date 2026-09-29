"""Phần "Chỉ tiêu năm" của Dashboard đơn vị — thực hiện LŨY KẾ từ 01/01 so với kế hoạch năm.

Vì sao lũy kế mà không theo kỳ đang xem: chỉ tiêu là số của CẢ NĂM, đem một tháng ra so thì đơn vị
nào cũng "đạt 8%" — con số đúng mà vô nghĩa. Mốc so tiến độ là % thời gian đã qua của năm.

Ba chỉ tiêu, cùng quy ước với Báo cáo tổng hợp:
- Thu mua: tử số = mủ NGUYÊN LIỆU (nước + chén + dây, quy khô), không gồm thành phẩm mua ngoài.
- Hàng hóa: thành phẩm MUA NGOÀI để bán lại (biểu Thu mua, phần thành phẩm) so với KH hàng hóa —
  chỉ tiêu riêng, không gộp vào thu mua (chỉ tiêu thu mua của Ban TTKD chỉ tính mủ nguyên liệu).
- Tiêu thụ: kế hoạch chỉ đặt cho HĐ CHUYẾN → so với sản lượng HĐ chuyến, không so tổng tiêu thụ.
- Doanh thu (tỷ đồng): đơn vị có lần giao chưa tính được doanh thu (thiếu tỷ giá hoặc đơn giá) thì
  doanh thu đang THIẾU → % để trống. Đơn vị có dòng bán ĐƠN GIÁ VƯỢT TRẦN (nghi gõ đồng vào ô triệu
  đồng) thì doanh thu đang bị ĐỘI LÊN → cũng để trống % (26/09/2026: một đợt giao nhập 56.200 thay
  cho 56,2 đẩy cả Tập đoàn lên 129%, một khu vực lên 1.257%).

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
from app.services.anomaly_types import vn_num
from app.services.unit_report_query import (
    NO_REGION_LABEL, region_of_units, split_csv, year_plan_by_group,
)

#: (khoá, nhãn, đơn vị, cột kế hoạch năm, trường thực hiện, bảng nguồn, lời giải thích)
_ITEMS = (
    ("purchase", "Thu mua mủ nguyên liệu", "tấn", "plan_tonnes", "qty_material", "purchase",
     "Mủ nước + mủ chén + mủ dây (quy khô), không gồm thành phẩm mua ngoài."),
    ("goods", "Hàng hóa (thành phẩm mua ngoài)", "tấn", "plan_goods_tonnes", "qty_finished",
     "purchase", "Thành phẩm mua của đơn vị khác để bán lại — chỉ tiêu riêng, không tính vào thu mua."),
    ("sales_spot", "Tiêu thụ HĐ chuyến", "tấn", "plan_sales_spot_tonnes", "qty_spot", "consumption",
     "Kế hoạch tiêu thụ chỉ giao cho hợp đồng chuyến."),
    ("revenue", "Doanh thu", "tỷ đồng", "plan_revenue_ty", "revenue_ty", "consumption", ""),
)

#: Chỉ tiêu chỉ một số đơn vị có — phạm vi không có cả KH lẫn số thực hiện thì không hiện.
_OPTIONAL = frozenset({"goods"})


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


def _revenue_issues(planned: list[str], con_rows: dict[str, dict], ceiling: float | None,
                    ) -> list[str]:
    """Lý do % doanh thu để trống — chỉ xét rổ đơn vị ĐƯỢC GIAO kế hoạch (rổ tính %)."""
    got = [con_rows[c] for c in planned if c in con_rows]
    out = []
    if missing := sum(r.get("no_revenue_lines") or 0 for r in got):
        out.append(f"{missing} lần giao chưa tính được doanh thu (thiếu tỷ giá hoặc đơn giá) — "
                   f"doanh thu đang thiếu phần đó nên chưa tính % kế hoạch.")
    bad = {c: con_rows[c]["bad_price_lines"] for c in planned
           if (con_rows.get(c) or {}).get("bad_price_lines")}
    if bad:
        # Nêu TÊN đơn vị: người đọc phải biết gọi ai sửa, câu chung chung thì không ai nhận việc.
        names = ", ".join(list(bad)[:5]) + ("…" if len(bad) > 5 else "")
        out.append(f"{sum(bad.values())} dòng bán của {names} có đơn giá vượt "
                   f"{vn_num(ceiling or 0)} triệu đ/tấn — nghi sai đơn vị tính, sửa xong mới tính "
                   f"% kế hoạch.")
    return out


def _note(base: str, issues: list[str]) -> str:
    # Rổ đơn vị có KH (`units_planned`) và tổng cả phạm vi (`scope_done`) là ô số riêng — web đặt
    # cạnh nhau; lặp lại thành câu ở đây thì cùng một ý hiện hai lần (phản hồi 26/09/2026).
    return " ".join([base, *issues] if base else issues)


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
    con_rows = rows["consumption"]
    blocked = {k for k, r in con_rows.items()
               if r.get("no_revenue_lines") or r.get("bad_price_lines")}
    region_of = region_of_units()

    items, per_item = [], {}
    for key, label, unit, plan_key, field, src, base in _ITEMS:
        plan = year_plan_by_group(plan_key, "company", comps, regs, year, f["split_merged"])[0]
        done = {k: r.get(field) for k, r in rows[src].items()}
        stop = blocked if key == "revenue" else set()
        planned = [c for c in plan if plan[c]]
        prog = _progress(planned, plan, done, stop)
        issues = (_revenue_issues(planned, con_rows, reps["consumption"].get("price_ceiling"))
                  if key == "revenue" else [])
        scope_done = reps[src]["totals"].get(field) or 0.0
        per_item[key] = (plan, done, stop)
        # Đa số đơn vị không kinh doanh hàng hóa: không KH, không số thì bỏ hẳn dòng, khỏi hiện
        # "Chưa giao chỉ tiêu" cho một việc đơn vị không làm.
        if key in _OPTIONAL and prog["plan"] is None and not scope_done:
            continue
        items.append({"key": key, "label": label, "unit": unit, "done": prog["done"],
                      "plan": prog["plan"], "pct": prog["pct"],
                      "units_planned": prog["units_planned"],
                      # Tổng CẢ phạm vi (kể cả đơn vị chưa giao kế hoạch) — web hiện cạnh `done`
                      # của rổ tính %, để hai số khác rổ không bị đọc như lệch nhau.
                      "scope_done": scope_done,
                      "note": _note(base, issues)})

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
