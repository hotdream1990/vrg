"""Kỹ năng "Kế hoạch năm & % thực hiện" của Trợ lý AI — ra ĐÚNG số của Dashboard đơn vị.

Hai lỗi đã gặp khi tool tự cộng số (rà chéo trên bản sao prod 29/09/2026):
- Sản lượng theo đơn vị lấy từ hàm VẼ BIỂU ĐỒ `unit_series_purchase.purchase_volume_series`: giữ 8
  nhóm lớn nhất, còn lại dồn "Khác" (8.587 tấn), không gộp đơn vị đã sáp nhập → sai % ở 26/38 đơn
  vị (Phú Thịnh 0% thay vì 52,7%; Chư prông 0% thay vì 132%; Lộc Ninh 35,4% thay vì 40,4%).
- % doanh thu = doanh thu CẢ Tập đoàn ÷ kế hoạch của riêng 27 đơn vị đã giao → 213,2% (Dashboard 80,6%).

Nay theo đúng luật RỔ của Dashboard: tử số và mẫu số cùng là các đơn vị ĐƯỢC GIAO chỉ tiêu. Tổng
Tập đoàn gọi thẳng `unit_dashboard_targets.targets_block` (kể cả luật để trống % doanh thu khi có dòng
bán thiếu tỷ giá/đơn giá hoặc đơn giá vượt trần). Từng khu vực/đơn vị dựng từ đúng hai nguồn Dashboard
dùng: `purchase_report(group_by="company")` → `qty_material` (đã gộp đơn vị sáp nhập) và
`year_plan_by_group("plan_tonnes", "company")`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services import unit_daily_repo as udr
from app.services import unit_dashboard_scope as scope_svc
from app.services import unit_dashboard_targets as targets_svc
from app.services import unit_report_purchase as pur
from app.services import unit_report_query as urq

from ._common import cols, err, table, today


def _r(v: float | None, digits: int) -> float | None:
    return round(v, digits) if v is not None else None


def purchase_plan_rows(year: int, date_from: str, date_to: str, group_by: str,
                       order: list[str]) -> list[dict[str, Any]]:
    """% kế hoạch thu mua từng khu vực/đơn vị theo luật RỔ của Dashboard.

    Đơn vị chưa được giao kế hoạch mà vẫn mua thì KHÔNG vào tử số (bỏ ra thì mẫu số hụt, cộng vào
    thì % tự đội lên) — phần đó hiện riêng ở `ngoai_ro_tan` để tổng khu vực vẫn đối chiếu được.
    `order` = thứ tự khu vực admin đã sắp (dòng ngoài danh sách xuống cuối).
    """
    plan, _ = urq.year_plan_by_group("plan_tonnes", "company", None, None, year)
    done = {r["key"]: r["qty_material"] or 0.0
            for r in pur.purchase_report(date_from, date_to, group_by="company")["rows"]}
    region_of = urq.region_of_units()

    def label_of(c: str) -> str:
        return c if group_by == "company" else (region_of.get(c) or urq.NO_REGION_LABEL)

    acc: dict[str, list[float]] = {}                  # nhóm → [kế hoạch, thực hiện trong rổ, ngoài rổ]
    for c in set(plan) | set(done):
        g = acc.setdefault(label_of(c), [0.0, 0.0, 0.0])
        if plan.get(c):
            g[0] += plan[c]
            g[1] += done.get(c, 0.0)
        else:
            g[2] += done.get(c, 0.0)

    rank = {k: i for i, k in enumerate(order)}
    rows = []
    for k in sorted(acc, key=lambda k: (rank.get(k, len(rank)), k)):
        p, d, out = acc[k]
        rows.append({"nhom": k, "ke_hoach_tan": _r(p, 3) or None,
                     # Chưa giao kế hoạch → hiện sản lượng thật, % để trống (không ghi 0%).
                     "thuc_hien_tan": _r(d if p else out, 3) or None,
                     "pct_thuc_hien": _r(d / p * 100, 1) if p else None,
                     **({"ngoai_ro_tan": _r(out, 3)} if p and out else {})})
    return rows


def _item_block(it: dict[str, Any], digits: int, unit_word: str, n_units: int) -> dict[str, Any]:
    """Một chỉ tiêu của Dashboard → khối summary: rổ tính % và tổng cả Tập đoàn tách bạch."""
    return {"ke_hoach": _r(it["plan"], digits), "thuc_hien_trong_ro": _r(it["done"], digits),
            "pct_thuc_hien": _r(it["pct"], 1),
            "so_don_vi_duoc_giao_ke_hoach": f"{it['units_planned']}/{n_units}",
            "thuc_hien_ca_tap_doan": _r(it["scope_done"], digits), "don_vi": unit_word,
            "ghi_chu": " ".join(filter(None, [
                "% = thực hiện của các đơn vị ĐƯỢC GIAO kế hoạch ÷ kế hoạch của chính họ (cùng cách "
                "tính Dashboard đơn vị); đơn vị chưa giao kế hoạch chỉ nằm trong 'thuc_hien_ca_tap_doan'.",
                it.get("note")]))}


def run(args: dict) -> dict:
    try:
        year = int(args.get("year") or today()[:4])
    except (TypeError, ValueError):
        return err(f"Năm '{args.get('year')}' không hợp lệ.")
    group_by = args.get("group_by") if args.get("group_by") in ("region", "company") else "region"
    cur = date.fromisoformat(today())
    if year > cur.year:
        return err(f"Chưa có số liệu thực hiện cho năm {year} (năm tương lai).")
    y_from, y_to = f"{year}-01-01", (f"{year}-12-31" if year < cur.year else today())

    sc = scope_svc.resolve("group", None, None)
    items = {it["key"]: it for it in targets_svc.targets_block(sc, y_to, today())["items"]}
    # Tử và mẫu của tỷ lệ "đã khai" cùng MỘT tập (đơn vị đang hoạt động) — đếm cả kế hoạch của đơn
    # vị đã sáp nhập/ngừng vào tử số thì tỷ lệ có thể vượt 100% (vd 65/64).
    active = {u["name"] for u in urq.report_units()}
    n_units = len(active)
    _, plan_exploit_total = urq.year_plan_by_group("plan_exploit_tonnes", "company", None, None, year)
    n_exploit = sum(1 for c, p in udr.year_plan(year).items()
                    if c in active and p.get("plan_exploit_tonnes"))

    rows = purchase_plan_rows(year, y_from, y_to, group_by, sc["children"])
    art = table(f"Kế hoạch & thực hiện thu mua {year} theo {group_by}",
                cols(("nhom", "Nhóm"), ("ke_hoach_tan", "Kế hoạch (tấn)"),
                     ("thuc_hien_tan", "Thực hiện (tấn)"), ("pct_thuc_hien", "% thực hiện")), rows)
    revenue = _item_block(items["revenue"], 2, "tỷ đồng", n_units)
    revenue["ghi_chu"] += " Doanh thu chưa chia theo khu vực/đơn vị ở công cụ này."
    return {"summary": {
        "year": year, "group_by": group_by, "ky_thuc_hien": f"{y_from} → {y_to}",
        # Khai thác CHỈ có chỉ tiêu — hệ thống chưa thu số thực hiện khai thác, KHÔNG suy % từ thu mua.
        "khai_thac": {"ke_hoach_tan": round(plan_exploit_total, 3) or None,
                      "so_don_vi_da_khai": f"{n_exploit}/{n_units}",
                      "ghi_chu": "Chưa có số liệu thực hiện khai thác trong hệ thống — chỉ có kế "
                                 "hoạch, không tính được % thực hiện."},
        "san_luong_thu_mua": _item_block(items["purchase"], 3, "tấn quy khô", n_units),
        "doanh_thu": revenue,
        # ĐỦ mọi nhóm (không cắt top): hỏi một đơn vị nhỏ phải có dòng của nó.
        "cac_nhom": rows},
            "artifact": art,
            "source": f"Dashboard đơn vị (chỉ tiêu năm) + unit_report_purchase · năm {year}"}
