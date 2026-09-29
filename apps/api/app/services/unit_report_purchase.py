"""Bảng thống kê THU MUA — gộp dòng chi tiết theo bộ lọc (đơn vị · khu vực · loại mủ · chủng loại).

Đơn giá mủ nước/mủ chén theo **đồng/độ**, thành phẩm theo **triệu đ/tấn** — KHÔNG quy đổi chéo,
mỗi loại một chỉ tiêu bình quân GIA QUYỀN riêng (xem `unit_report_query`).
"""

from __future__ import annotations

from typing import Any

from app.services import unit_report_rows as rows_mod
from app.services.unit_report_query import (
    GROUPERS, avg, filter_scope, merge_rollup, merge_scope, merge_view, sort_groups, split_csv,
    year_plan_by_group,
)
from app.services.unit_report_rows import TRIEU


#: Loại mủ nhập theo SẢN LƯỢNG + đơn giá riêng (mọi loại trừ thành phẩm — thành phẩm tính theo
#: doanh thu/tấn nên có rổ `_fin` riêng). Lấy thẳng từ `rows_mod.MATERIALS` để thêm loại mủ mới là
#: bảng thống kê tự có ô đếm: thiếu một ô là `_feed_purchase` ném KeyError và cả bảng trả lỗi 500
#: (đã xảy ra 10/08/2026 — 2 loại nguyên liệu thêm ngày 30/07 làm vỡ mọi kỳ chạm tháng 01/2026).
_QTY_MATERIALS: tuple[str, ...] = tuple(m for m in rows_mod.MATERIALS if m != "finished")

#: Chỉ tiêu kế hoạch thu mua NĂM ở màn "Kế hoạch năm" (cũng là công tắc bật màn Thu mua).
_PLAN_KEY = "plan_tonnes"
#: Tử số của % kế hoạch = **sản lượng mủ NGUYÊN LIỆU** (mủ nước + mủ chén + mủ dây, đều là số QUY
#: KHÔ), KHÔNG gồm thành phẩm mua ngoài. Đúng mẫu gốc Ban TTKD ("% Kế hoạch thực hiện thu mua" tính
#: trên sản lượng mủ thu mua) và khớp cột `total_purchase` của Báo cáo tổng hợp — hai màn phải ra
#: cùng một con số, nên thêm loại mủ nguyên liệu ở đây thì phải thêm cả bên `unit_period_report`.
_PLAN_MATERIALS: tuple[str, ...] = ("latex", "cup", "lace")


def _new_purchase(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region,
            **{f"qty_{m}": 0.0 for m in rows_mod.MATERIALS},
            "_w": {m: [0.0, 0.0] for m in _QTY_MATERIALS}, "_fin": [0.0, 0.0],
            "_days": set(), "_bought": set(), "_no_days": set()}


def _close_purchase(g: dict) -> dict[str, Any]:
    w, fin = g.pop("_w"), g.pop("_fin")
    days, bought = g.pop("_days"), g.pop("_bought")
    g["days"] = len(days)
    # Ngày "không thu mua" = cặp (đơn vị hiện hành, ngày) KHÁC NHAU, trừ ngày đã có số thu mua. Sau
    # khi gộp sáp nhập, đơn vị cũ và đơn vị nhận cùng khai một ngày vẫn chỉ là MỘT ngày; bên này khai
    # "không mua" mà bên kia có mua thì ngày đó là ngày CÓ số (Lộc Ninh từng ra 201 ngày có số + 154
    # ngày không mua trong kỳ 272 ngày — thực chỉ 84 ngày khai không mua khác nhau). Chỉ trừ ngày có
    # sản lượng > 0: ô khai 0 tấn vẫn sinh dòng, trừ cả nó là bỏ oan ngày "không mua" (Hà Tĩnh mất 41).
    g["no_purchase_days"] = len(g.pop("_no_days") - bought) or None
    g["qty_total"] = sum(g[f"qty_{m}"] for m in rows_mod.MATERIALS)
    # Tách riêng phần đem so kế hoạch, để người đọc bảng thấy luôn tử số thay vì phải tự cộng.
    g["qty_material"] = sum(g[f"qty_{m}"] for m in _PLAN_MATERIALS) or None
    # Đơn giá BQ tách theo ĐƠN VỊ TÍNH, không gộp: mủ nước là đồng/độ TSC, mủ chén và mủ dây là
    # đồng/độ DRC, thành phẩm là triệu đ/tấn — cộng chung là ra một con số vô nghĩa.
    for m in _QTY_MATERIALS:
        g[f"price_{m}_avg"] = avg(*w[m])
    fin_avg = avg(*fin)
    g["price_finished_avg"] = (fin_avg / TRIEU) if fin_avg is not None else None  # triệu đ/tấn
    # Tử/mẫu của giá BQ thành phẩm — bảng chéo chủng loại cần để gộp ô bằng BQ GIA QUYỀN
    # (xem `unit_scorecard_grade`), cộng thẳng hai con số giá là sai.
    g["finished_revenue_vnd"] = fin[0] or None
    g["finished_priced_qty"] = fin[1] or None
    for m in rows_mod.MATERIALS:
        g[f"qty_{m}"] = g[f"qty_{m}"] or None
    g["qty_total"] = g["qty_total"] or None
    return g


def _attach_plan(g: dict, plan: float | None) -> None:
    """Gắn chỉ tiêu năm + % thực hiện vào 1 dòng. Chưa giao kế hoạch thì để TRỐNG, không ghi 0%."""
    g["plan_tonnes"] = plan or None
    g["pct_plan"] = ((g["qty_material"] or 0.0) / plan * 100) if plan else None


def _feed_purchase(g: dict, r: dict) -> None:
    m, qty = r["material"], r["qty"] or 0.0
    g[f"qty_{m}"] += qty
    g["_days"].add((r["company"], r["as_of"]))
    if qty > 0:
        g["_bought"].add((r["company"], r["as_of"]))
    if m == "finished":
        if r["revenue_vnd"] is not None and qty:
            g["_fin"][0] += r["revenue_vnd"]
            g["_fin"][1] += qty
    elif r["price"] is not None and qty:
        g["_w"][m][0] += r["price"] * qty
        g["_w"][m][1] += qty


def purchase_report(date_from: str, date_to: str, *, companies: str | None = None,
                    regions: str | None = None, materials: str | None = None,
                    grades: str | None = None, group_by: str = "company",
                    split_merged: bool = False) -> dict[str, Any]:
    """Bảng thống kê Thu mua theo bộ lọc (đơn vị · khu vực · loại mủ · chủng loại · kỳ).

    `split_merged=True` → TÁCH đơn vị đã sáp nhập thành dòng riêng; mặc định gộp số của họ vào
    đơn vị hiện hành (xem `unit_report_query.merge_rollup`).
    """
    comps, regs = split_csv(companies), split_csv(regions)
    mats, grds = split_csv(materials), split_csv(grades)
    # Mốc xét sáp nhập là NGÀY CUỐI KỲ: kỳ kết thúc trước ngày sáp nhập thì lúc ấy hai đơn vị còn
    # độc lập nên vẫn đứng riêng, dù bảng đang ở chế độ gộp.
    data = rows_mod.purchase_rows(date_from, date_to, merge_scope(comps, split_merged))
    view = merge_view(comps, split_merged)
    rows = filter_scope(merge_rollup(data["rows"], split_merged), view, regs)
    if mats:
        rows = [r for r in rows if r["material"] in set(mats)]
    if grds:   # chủng loại chỉ áp cho mủ thành phẩm (mủ nước/chén/dây không có chủng loại)
        keep = set(grds)
        rows = [r for r in rows if r["material"] == "finished" and r["grade"] in keep]

    key_of = GROUPERS[group_by]
    groups: dict[str, dict] = {}
    for r in rows:
        k = key_of(r)
        if k is None:
            continue
        g = groups.get(k) or groups.setdefault(k, _new_purchase(k, r.get("region") if group_by == "company" else None))
        _feed_purchase(g, r)
    # Ngày không tổ chức thu mua: chỉ đếm được khi nhóm theo đơn vị/khu vực/ngày.
    if group_by in ("company", "region", "day") and not (mats or grds):
        meta = rows_mod.unit_meta()
        for p in merge_rollup(data["no_purchase"], split_merged):
            pseudo = {**p, "region": (meta.get(p["company"]) or {}).get("region")}
            if view and p["company"] not in set(view):
                continue
            if regs and (pseudo["region"] or "") not in set(regs):
                continue
            k = key_of(pseudo)
            g = groups.get(k) or groups.setdefault(k, _new_purchase(k, pseudo["region"] if group_by == "company" else None))
            g["_no_days"].add((p["company"], p["as_of"]))

    total = _new_purchase("Tổng cộng", None)
    for r in rows:
        _feed_purchase(total, r)
    total["_no_days"] = set().union(*(g["_no_days"] for g in groups.values()))
    out_rows = [_close_purchase(g) for g in sort_groups(groups, group_by)]
    totals = _close_purchase(total)

    warnings = _purchase_warnings(rows)
    # Kế hoạch là chỉ tiêu NĂM → lấy theo năm của ngày CUỐI kỳ. Lọc theo loại mủ/chủng loại thì tử
    # số chỉ còn một phần sản lượng trong khi mẫu số vẫn là kế hoạch cả năm → KHÔNG tính %, để trống.
    year = int(date_to[:4])
    filtered = bool(mats or grds)
    plan_by_key, plan_total = (({}, 0.0) if filtered
                               else year_plan_by_group(_PLAN_KEY, group_by, comps, regs, year,
                                                       split_merged))
    _attach_plan(totals, plan_total)
    for row in out_rows:
        _attach_plan(row, plan_by_key.get(row["key"]))   # nhóm khác đơn vị/khu vực → để trống
    if filtered:
        warnings.append("Đang lọc theo loại mủ/chủng loại nên không tính % kế hoạch thu mua — "
                        "kế hoạch là chỉ tiêu cho toàn bộ sản lượng thu mua của đơn vị.")
    elif plan_total and date_from[:4] != date_to[:4]:
        warnings.append(f"% kế hoạch thu mua đang so với chỉ tiêu NĂM {year}, trong khi kỳ xem "
                        f"bắt đầu từ năm {date_from[:4]} — chỉ để tham khảo.")

    return {"kind": "purchase", "date_from": date_from, "date_to": date_to, "group_by": group_by,
            "rows": out_rows, "totals": totals, "warnings": warnings}


def _purchase_warnings(rows: list[dict]) -> list[str]:
    out = []
    if (n := sum(1 for r in rows if r.get("missing_fx"))):
        out.append(f"{n} dòng nhập ngoại tệ nhưng thiếu tỷ giá — không tính vào giá bình quân.")
    # Ngày đơn vị ĐÃ KHAI RÕ "không có giá" (sản lượng chênh lệch sau chế biến) không phải lỗi —
    # đếm cả những ngày đó là nhắc oan, đơn vị đã làm đúng phần việc của mình.
    if (n := sum(1 for r in rows if r["material"] != "finished" and r["price"] is None and r["qty"]
                 and not r.get("price_declared_none"))):
        out.append(f"{n} ngày có sản lượng thu mua nhưng chưa có đơn giá — không tính vào giá bình quân.")
    if (n := sum(1 for r in rows if r.get("price_declared_none") and r["qty"])):
        out.append(f"{n} ngày đơn vị khai không có đơn giá (sản lượng vẫn tính, giá không vào bình quân).")
    return out
