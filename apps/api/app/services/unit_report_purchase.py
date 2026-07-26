"""Bảng thống kê THU MUA — gộp dòng chi tiết theo bộ lọc (đơn vị · khu vực · loại mủ · chủng loại).

Đơn giá mủ nước/mủ chén theo **đồng/độ**, thành phẩm theo **triệu đ/tấn** — KHÔNG quy đổi chéo,
mỗi loại một chỉ tiêu bình quân GIA QUYỀN riêng (xem `unit_report_query`).
"""

from __future__ import annotations

from typing import Any

from app.services import unit_report_rows as rows_mod
from app.services.unit_report_query import (
    GROUPERS, avg, filter_scope, sort_groups, split_csv,
)
from app.services.unit_report_rows import TRIEU


def _new_purchase(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region,
            "qty_latex": 0.0, "qty_cup": 0.0, "qty_finished": 0.0,
            "_w": {"latex": [0.0, 0.0], "cup": [0.0, 0.0]}, "_fin": [0.0, 0.0],
            "_days": set(), "no_purchase_days": 0}


def _close_purchase(g: dict) -> dict[str, Any]:
    w, fin = g.pop("_w"), g.pop("_fin")
    days = g.pop("_days")
    g["days"] = len(days)
    g["qty_total"] = g["qty_latex"] + g["qty_cup"] + g["qty_finished"]
    g["price_latex_avg"] = avg(*w["latex"])         # đồng/độ
    g["price_cup_avg"] = avg(*w["cup"])             # đồng/độ
    fin_avg = avg(*fin)
    g["price_finished_avg"] = (fin_avg / TRIEU) if fin_avg is not None else None  # triệu đ/tấn
    for k in ("qty_latex", "qty_cup", "qty_finished", "qty_total"):
        g[k] = g[k] or None
    g["no_purchase_days"] = g["no_purchase_days"] or None
    return g


def _feed_purchase(g: dict, r: dict) -> None:
    m, qty = r["material"], r["qty"] or 0.0
    g[f"qty_{m}"] += qty
    g["_days"].add((r["company"], r["as_of"]))
    if m == "finished":
        if r["revenue_vnd"] is not None and qty:
            g["_fin"][0] += r["revenue_vnd"]
            g["_fin"][1] += qty
    elif r["price"] is not None and qty:
        g["_w"][m][0] += r["price"] * qty
        g["_w"][m][1] += qty


def purchase_report(date_from: str, date_to: str, *, companies: str | None = None,
                    regions: str | None = None, materials: str | None = None,
                    grades: str | None = None, group_by: str = "company") -> dict[str, Any]:
    """Bảng thống kê Thu mua theo bộ lọc (đơn vị · khu vực · loại mủ · chủng loại · kỳ)."""
    comps, regs = split_csv(companies), split_csv(regions)
    mats, grds = split_csv(materials), split_csv(grades)
    data = rows_mod.purchase_rows(date_from, date_to, comps)
    rows = filter_scope(data["rows"], comps, regs)
    if mats:
        rows = [r for r in rows if r["material"] in set(mats)]
    if grds:   # chủng loại chỉ áp cho mủ thành phẩm (mủ nước/chén không có chủng loại)
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
        for p in data["no_purchase"]:
            pseudo = {**p, "region": (meta.get(p["company"]) or {}).get("region")}
            if comps and p["company"] not in set(comps):
                continue
            if regs and (pseudo["region"] or "") not in set(regs):
                continue
            k = key_of(pseudo)
            g = groups.get(k) or groups.setdefault(k, _new_purchase(k, pseudo["region"] if group_by == "company" else None))
            g["no_purchase_days"] += 1

    total = _new_purchase("Tổng cộng", None)
    for r in rows:
        _feed_purchase(total, r)
    total["no_purchase_days"] = sum(g["no_purchase_days"] for g in groups.values())
    out_rows = [_close_purchase(g) for g in sort_groups(groups, group_by)]
    return {"kind": "purchase", "date_from": date_from, "date_to": date_to, "group_by": group_by,
            "rows": out_rows, "totals": _close_purchase(total),
            "warnings": _purchase_warnings(rows)}


def _purchase_warnings(rows: list[dict]) -> list[str]:
    out = []
    if (n := sum(1 for r in rows if r.get("missing_fx"))):
        out.append(f"{n} dòng nhập ngoại tệ nhưng thiếu tỷ giá — không tính vào giá bình quân.")
    if (n := sum(1 for r in rows if r["material"] != "finished" and r["price"] is None and r["qty"])):
        out.append(f"{n} ngày có sản lượng thu mua nhưng chưa có đơn giá — không tính vào giá bình quân.")
    bases = {r["cup_basis"] for r in rows if r["material"] == "cup" and r["cup_basis"]}
    if len(bases) > 1:
        out.append("Giá mủ chén đang lẫn cơ sở tính TSC và DRC — chỉ nên so sánh trong cùng cơ sở.")
    return out
