"""Thống kê Tồn kho (số THỜI ĐIỂM) + Tình trạng nộp báo cáo của các đơn vị.

Tồn kho KHÔNG cộng dồn theo ngày: mỗi đơn vị lấy số của ngày CUỐI CÙNG có nhập tồn trong kỳ,
và **luôn trả kèm ngày đã lấy** để người xem biết số thuộc ngày nào (không mượn số ngày khác).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import member_unit_repo, unit_daily_repo, unit_report_rows
from app.services.unit_report_query import dmy, filter_scope, sort_groups, split_csv

_BLOCK_KEY = {"stock_not_warehoused": "not_warehoused", "stock_warehoused": "warehoused"}


def _new_group(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region, "not_warehoused": 0.0,
            "warehoused": 0.0, "material": 0.0, "by_grade": {}, "_dates": set()}


def _feed(g: dict, r: dict, with_grade: bool) -> None:
    qty = r["qty"] or 0.0
    g["_dates"].add(r["as_of"])
    if r["block"] == "stock_material":
        g["material"] += qty
        return
    g[_BLOCK_KEY[r["block"]]] += qty
    if with_grade:
        g["by_grade"][r["grade"]] = (g["by_grade"].get(r["grade"]) or 0.0) + qty


def _close(g: dict) -> dict[str, Any]:
    dates = sorted(g.pop("_dates"))
    g["dates"] = dates                 # ĐÚNG các ngày đã lấy số (để đối chiếu, không suy diễn)
    # Nhóm gồm nhiều ngày (vd theo khu vực) → KHÔNG hiện 1 ngày duy nhất, dễ hiểu sai là số cùng ngày.
    g["as_of"] = dates[-1] if len(dates) == 1 else None
    g["total"] = (g["not_warehoused"] + g["warehoused"]) or None
    for k in ("not_warehoused", "warehoused", "material"):
        g[k] = g[k] or None
    g["by_grade"] = {k: v for k, v in sorted(g["by_grade"].items()) if v}
    return g


def stock_report(date_from: str, date_to: str, *, companies: str | None = None,
                 regions: str | None = None, grades: str | None = None,
                 group_by: str = "company") -> dict[str, Any]:
    """Tồn kho tại mốc cuối kỳ theo bộ lọc (đơn vị · khu vực · chủng loại · kỳ)."""
    comps, regs, grds = split_csv(companies), split_csv(regions), split_csv(grades)
    # Nhóm theo NGÀY = xem diễn biến tồn → giữ mọi ngày có số liệu; các cách nhóm khác chỉ lấy mốc cuối.
    raw = unit_report_rows.stock_rows(date_from, date_to, comps, all_days=group_by == "day")
    rows = filter_scope(raw, comps, regs)
    if grds:   # lọc chủng loại: chỉ áp cho 2 khối thành phẩm, tồn nguyên liệu không có chủng loại
        keep = set(grds)
        rows = [r for r in rows if r["block"] == "stock_material" or r["grade"] in keep]

    key_of = {"company": lambda r: r["company"],
              "region": lambda r: r.get("region") or "(Chưa gán khu vực)",
              "grade": lambda r: r["grade"],
              "day": lambda r: r["as_of"]}[group_by]
    groups: dict[str, dict] = {}
    for r in rows:
        if group_by == "grade" and r["block"] == "stock_material":
            continue          # tồn nguyên liệu không thuộc chủng loại nào → chỉ tính ở dòng Tổng
        k = key_of(r)
        g = groups.get(k) or groups.setdefault(k, _new_group(k, r.get("region") if group_by == "company" else None))
        _feed(g, r, with_grade=group_by != "grade")

    # Dòng Tổng cộng: tồn kho là số THỜI ĐIỂM nên khi nhóm theo NGÀY, cộng các ngày lại là tính
    # trùng chính lô hàng đó → lấy ảnh chụp của NGÀY CUỐI thay vì cộng dồn.
    total = _new_group("Tổng cộng", None)
    last_day = max((r["as_of"] for r in rows), default=None)
    for r in rows:
        if group_by == "day" and r["as_of"] != last_day:
            continue
        _feed(total, r, with_grade=True)
    # Đơn vị được chọn nhưng không có bản ghi tồn kho nào trong kỳ → báo rõ, KHÔNG lấy số ngày khác.
    warn = []
    if comps and (no_data := sorted(set(comps) - {r["company"] for r in rows})):
        warn.append("Chưa nhập tồn kho trong kỳ: " + ", ".join(no_data))
    if group_by == "day" and last_day:
        warn.append(f"Mỗi dòng là tồn của riêng ngày đó; dòng Tổng cộng lấy ngày cuối ({dmy(last_day)}), "
                    "không cộng dồn các ngày.")
    return {"date_from": date_from, "date_to": date_to, "group_by": group_by,
            "rows": [_close(g) for g in sort_groups(groups, group_by)],
            "totals": _close(total), "warnings": warn}


# ── Tình trạng nộp báo cáo (đơn vị × ngày) ────────────────────────────────────
def _date_list(date_from: str, date_to: str) -> list[str]:
    a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def status_report(kind: str, date_from: str, date_to: str, *, companies: str | None = None,
                  regions: str | None = None) -> dict[str, Any]:
    """Ma trận đơn vị × ngày: `ok` đã nhập · `no_purchase` không tổ chức thu mua · `none` chưa nhập.

    Biểu Thu mua chỉ tính các đơn vị ĐƯỢC GIAO kế hoạch thu mua (đơn vị khác không phải nộp).
    """
    comps, regs = split_csv(companies), split_csv(regions)
    units = member_unit_repo.list_units(include_inactive=False)
    if kind == "purchase":
        units = [u for u in units if u.get("has_purchase_plan", True)]
    if comps:
        keep = set(comps)
        units = [u for u in units if u["name"] in keep]
    if regs:
        keep = set(regs)
        units = [u for u in units if (u.get("region") or "") in keep]

    entries = unit_daily_repo.in_range(kind, date_from, date_to, [u["name"] for u in units])
    state: dict[tuple[str, str], str] = {}
    for e in entries:
        no_buy = kind == "purchase" and e["fields"].get("no_purchase") is True
        state[(e["company"], e["as_of"])] = "no_purchase" if no_buy else "ok"

    dates = _date_list(date_from, date_to)
    rows, filled, no_purchase = [], 0, 0
    for u in units:
        cells = {d: state.get((u["name"], d), "none") for d in dates}
        ok = sum(1 for v in cells.values() if v == "ok")
        skip = sum(1 for v in cells.values() if v == "no_purchase")
        filled += ok
        no_purchase += skip
        rows.append({"company": u["name"], "region": u.get("region"), "cells": cells,
                     "filled": ok, "no_purchase": skip, "missing": len(dates) - ok - skip,
                     "last_day": max((d for d, v in cells.items() if v != "none"), default=None)})
    expected = len(dates) * len(units)
    return {"kind": kind, "date_from": date_from, "date_to": date_to, "dates": dates, "rows": rows,
            "totals": {"expected": expected, "filled": filled, "no_purchase": no_purchase,
                       "missing": expected - filled - no_purchase}}
