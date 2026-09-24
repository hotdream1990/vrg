"""Màn "Chỉ số đơn vị" — một bảng, hai cấp dòng: KHU VỰC (mở/gập) → ĐƠN VỊ.

Không tự cộng lại số liệu: mỗi tab gọi đúng các bảng thống kê đã có (`unit_report_*`) hai lần —
`group_by="company"` cho dòng đơn vị, `group_by="region"` cho dòng khu vực — rồi ghép thành cây.
Nhờ vậy dòng khu vực ở đây LUÔN khớp con số của màn thống kê cũ, và các luật gộp khó (giá bình
quân GIA QUYỀN, `% KH = Σ thực hiện ÷ Σ kế hoạch`) vẫn nằm nguyên một chỗ trong `unit_report_query`
thay vì bị chép lại lần hai.

Khung dòng là DANH SÁCH ĐƠN VỊ, không phải danh sách đơn vị có số: đơn vị chưa nộp vẫn có dòng với
các ô TRỐNG, và dòng khu vực ghi rõ mấy đơn vị chưa có số. Ô trống ≠ 0.
"""

from __future__ import annotations

from typing import Any

from app.services import member_region_repo
from app.services import unit_report_consumption as con
from app.services import unit_report_purchase as pur
from app.services import unit_report_status as sta
from app.services import unit_report_stock as st
from app.services.unit_report_query import NO_REGION_LABEL, dmy, report_units, split_csv
from app.services.unit_scorecard_cols import TABS, sources


def _fetch(src: str, group_by: str, p: dict[str, Any]) -> dict[str, Any]:
    """Gọi đúng bảng thống kê nguồn ở một mức gộp nhóm."""
    if src == "purchase":
        return pur.purchase_report(p["date_from"], p["date_to"], companies=p["companies"],
                                   regions=p["regions"], materials=p["materials"],
                                   grades=p["grades"], group_by=group_by,
                                   split_merged=p["split_merged"])
    if src == "consumption":
        return con.consumption_report(p["date_from"], p["date_to"], companies=p["companies"],
                                      regions=p["regions"], grades=p["grades"],
                                      contract=p["contract"], channel=p["channel"],
                                      source=p["source"], group_by=group_by,
                                      split_merged=p["split_merged"])
    if src == "stock":
        # `days_back=0`: cây hai cấp luôn là ảnh chụp TẠI ngày chốt, không có trục ngày để lùi.
        return st.stock_report(p["as_of"], 0, companies=p["companies"], regions=p["regions"],
                               grades=p["grades"], group_by=group_by,
                               split_merged=p["split_merged"])
    raise ValueError(f"Nguồn số liệu không hỗ trợ: {src}")


#: Quét lùi tối đa bấy nhiêu ngày để gợi ý "ngày gần nhất có số tồn kho" khi ngày chốt trống.
_STOCK_HINT_DAYS = 60


def _latest_stock_day(as_of: str, companies: list[str] | None = None) -> str | None:
    """Ngày gần nhất ≤ ngày chốt mà CÓ đơn vị khai tồn kho — chỉ để GỢI Ý đổi ngày chốt.

    Tồn kho không được đắp số ngày khác sang ngày đang xem, nên khi ngày chốt trống thì thay vì
    lặng lẽ hiện bảng rỗng, màn hình mời người dùng bấm sang đúng ngày có số. `companies` thu hẹp
    về một nhóm đơn vị (Dashboard đơn vị) — None = mọi đơn vị.
    """
    from datetime import date, timedelta

    from app.services import unit_daily_repo
    from app.services.unit_report_rows import has_stock

    start = (date.fromisoformat(as_of) - timedelta(days=_STOCK_HINT_DAYS)).isoformat()
    days = [e["as_of"] for e in unit_daily_repo.in_range("consumption", start, as_of, companies,
                                                         attach_contracts=False)
            if has_stock(e["fields"])]
    return max(days, default=None)


def _rate(filled: int, expected: int) -> float | None:
    """Tỷ lệ nộp tính LẠI từ tổng, không lấy trung bình các tỷ lệ của từng đơn vị."""
    return (filled / expected * 100) if expected else None


def _status_maps(p: dict[str, Any]) -> tuple[dict, dict, dict]:
    """Tình trạng nộp: gộp khu vực bằng phép CỘNG số ngày rồi tính lại tỷ lệ.

    `status_report` luôn để đơn vị đã sáp nhập đứng riêng (ai nộp là chuyện của từng đơn vị nhập
    liệu) nên bảng này không nhận `split_merged` — đúng như màn "Theo dõi nộp báo cáo".
    """
    rep = sta.status_report(p["status_kind"], p["date_from"], p["date_to"],
                            companies=p["companies"], regions=p["regions"])
    comp: dict[str, dict] = {}
    reg: dict[str, dict] = {}
    for r in rep["rows"]:
        expected = r["filled"] + r["no_purchase"] + r["missing"]
        comp[r["company"]] = {"expected": expected, "filled": r["filled"],
                              "no_purchase": r["no_purchase"], "missing": r["missing"],
                              "rate": _rate(r["filled"], expected), "last_day": r["last_day"]}
        g = reg.setdefault(r["region"] or NO_REGION_LABEL,
                           {"expected": 0, "filled": 0, "no_purchase": 0, "missing": 0,
                            "last_day": None})
        for k in ("expected", "filled", "no_purchase", "missing"):
            g[k] += comp[r["company"]][k]
        # Ngày nộp gần nhất của khu vực = ngày MỚI nhất trong các đơn vị của khu vực đó.
        if r["last_day"] and (g["last_day"] is None or r["last_day"] > g["last_day"]):
            g["last_day"] = r["last_day"]
    for g in reg.values():
        g["rate"] = _rate(g["filled"], g["expected"])
    t = rep["totals"]
    totals = {**t, "rate": _rate(t["filled"], t["expected"]),
              "last_day": max((g["last_day"] for g in reg.values() if g["last_day"]),
                              default=None)}
    return comp, reg, totals


def _values(cols: list[dict], maps: dict[str, dict], key: str) -> dict[str, Any]:
    """Rút giá trị của một dòng: mỗi cột lấy đúng `field` trong bảng nguồn `src` của nó."""
    return {c["key"]: (maps[c["src"]].get(key) or {}).get(c["field"]) for c in cols}


def _skeleton(p: dict[str, Any]) -> list[dict]:
    """Danh sách đơn vị làm khung dòng, đã áp bộ lọc đơn vị/khu vực của người dùng."""
    units = report_units(p["split_merged"])
    if comps := split_csv(p["companies"]):
        keep = set(comps)
        units = [u for u in units if u["name"] in keep]
    if regs := split_csv(p["regions"]):
        keep = set(regs)
        units = [u for u in units if (u.get("region") or NO_REGION_LABEL) in keep]
    return units


def region_tree(p: dict[str, Any]) -> list[tuple[str, list[dict]]]:
    """Khung dòng dùng chung: [(khu vực, [đơn vị…])] theo đúng thứ tự admin đã sắp ở màn Khu vực.

    Khu vực CHƯA GÁN xuống cuối bảng. Dùng cho cả bảng chỉ số lẫn bảng chéo chủng loại nên hai
    màn không bao giờ lệch nhau về danh sách/thứ tự đơn vị.
    """
    groups: dict[str, list[dict]] = {}
    for u in _skeleton(p):
        groups.setdefault(u.get("region") or NO_REGION_LABEL, []).append(u)
    order = {name: i for i, name in enumerate(member_region_repo.active_names())}
    return sorted(groups.items(),
                  key=lambda kv: (kv[0] == NO_REGION_LABEL, order.get(kv[0], len(order)), kv[0]))


def scorecard(tab: str, **p: Any) -> dict[str, Any]:
    """Cây hai cấp khu vực → đơn vị cho một tab chỉ số."""
    if tab not in TABS:
        raise ValueError(f"Tab không hợp lệ: {tab}")
    cols = TABS[tab]["cols"]
    comp_maps: dict[str, dict] = {}
    reg_maps: dict[str, dict] = {}
    tot_maps: dict[str, dict] = {}
    warnings: list[str] = []
    coverage: dict | None = None

    for src in sources(tab):
        if src == "status":
            comp_maps[src], reg_maps[src], tot_maps[src] = _status_maps(p)
            continue
        by_company = _fetch(src, "company", p)
        by_region = _fetch(src, "region", p)
        comp_maps[src] = {r["key"]: r for r in by_company["rows"]}
        reg_maps[src] = {r["key"]: r for r in by_region["rows"]}
        tot_maps[src] = by_company["totals"]
        if src == "stock":
            # Cảnh báo tồn kho rất dài (liệt kê đơn vị thiếu số) — chỉ hợp ở tab Tồn kho. Các tab
            # khác chỉ mượn 1-2 cột tồn nên thay bằng một dòng ngắn, không lấp mất bảng.
            coverage = by_company.get("coverage")
            if tab == "stock":
                warnings += by_company.get("warnings") or []
            elif coverage and not coverage["units_counted"]:
                warnings.append(f"Chưa đơn vị nào khai tồn kho ngày {dmy(p['as_of'])} — "
                                f"các cột tồn kho để trống. Xem chi tiết ở tab Tồn kho.")
            continue
        warnings += by_company.get("warnings") or []

    regions = []
    for label, units in region_tree(p):
        children = []
        for u in units:
            vals = _values(cols, comp_maps, u["name"])
            children.append({"company": u["name"], "merged_into": u.get("merged_into"),
                             "has_data": any(v is not None for v in vals.values()),
                             "values": vals})
        regions.append({
            "region": label, "units": len(children),
            "no_data": sum(1 for c in children if not c["has_data"]),
            "values": _values(cols, reg_maps, label), "children": children,
        })

    totals = {c["key"]: tot_maps[c["src"]].get(c["field"]) for c in cols}
    # Ngày chốt không đơn vị nào khai → mời sang ngày gần nhất có số, thay vì để bảng rỗng câm.
    # Chỉ làm ở tab Tồn kho: các tab khác đã có một dòng cảnh báo ngắn, không cần thêm khối gợi ý.
    stock_tab = tab == "stock"
    hint = (_latest_stock_day(p["as_of"])
            if stock_tab and coverage and not coverage["units_counted"] else None)
    return {
        "tab": tab, "axis": TABS[tab]["axis"], "date_from": p["date_from"],
        "date_to": p["date_to"], "as_of": p["as_of"],
        "cols": [{k: c[k] for k in ("key", "label", "unit", "note", "compare")} for c in cols],
        "regions": regions, "totals": totals, "latest_stock_day": hint,
        "coverage": coverage if stock_tab else None,
        "warnings": list(dict.fromkeys(warnings)),
    }
