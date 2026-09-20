"""Bảng chéo ĐƠN VỊ × CHỦNG LOẠI của màn "Chỉ số đơn vị" — xem cơ cấu chủng loại của mọi đơn vị
cùng một lúc, thay vì lọc lần lượt từng chủng loại.

Bảng chỉ có 2 chiều mà số liệu có 3 (đơn vị · chỉ số · chủng loại) nên ở đây CHỌN MỘT chỉ số đổ vào
ô, còn cột là các chủng loại. Trả về đúng khuôn của `unit_scorecard` (cols · regions · totals) để
web dùng lại một component bảng.

Ô của từng (đơn vị, chủng loại) vẫn do các bảng thống kê gốc tính, qua khoá nhóm ghép đôi
`company+grade` (xem `unit_report_query.pair`) — nhờ vậy giá bán bình quân trong mỗi ô là BQ GIA
QUYỀN thật, không phải trung bình cộng.
"""

from __future__ import annotations

from typing import Any

from app.services.unit_report_rows import MATERIAL_LABELS
from app.services.unit_report_query import unpair
from app.services.unit_scorecard import _fetch, region_tree

#: Lời nhắc bắt buộc cho các chỉ số thu mua: bảng này KHÔNG phải toàn bộ sản lượng thu mua.
_FINISHED_ONLY = ("Chỉ gồm THÀNH PHẨM mua ngoài. Mủ nước · mủ chén · mủ dây đơn vị khai theo tổng, "
                  "không gắn chủng loại nên không có trong bảng này.")

#: Lời nhắc cho chỉ số thu mua mủ nguyên liệu: ngày chưa tách vẫn phải nhìn thấy được.
_RAW_MIXED = ("Ngày đơn vị CHƯA tách chủng loại thì sản lượng nằm ở các cột “Mủ nước” · “Mủ chén” · "
              "“Mủ dây” — không phải chủng loại, mà là phần còn gom chung.")

#: Khoá cột đặc biệt — không phải tên chủng loại nào.
OTHER = "__other"
TOTAL = "__total"

#: Chủng loại chiếm dưới ngần này trong tổng thì gom vào cột "Khác": bày đủ 19 chủng loại thì 13
#: cột gần như trống, đọc không nổi.
MIN_SHARE = 0.01
#: Trần số cột chủng loại hiện ra (chưa kể "Khác" và "TỔNG").
MAX_GRADES = 8

#: Chỉ số đổ vào ô. `sum=False` = KHÔNG cộng được → gộp bằng thương Σ tiền ÷ Σ lượng.
#: `rank` là trường dùng để xếp hạng chủng loại nào đáng hiện thành cột (luôn là sản lượng —
#: xếp theo giá bình quân thì chủng loại bán lắt nhắt lại chiếm mất cột).
MEASURES: dict[str, dict[str, Any]] = {
    "con_qty": {"src": "consumption", "field": "qty", "rank": "qty", "sum": True,
                "label": "Sản lượng tiêu thụ", "unit": "tấn", "axis": "period"},
    "con_revenue": {"src": "consumption", "field": "revenue_ty", "rank": "qty", "sum": True,
                    "label": "Doanh thu", "unit": "tỷ đồng", "axis": "period"},
    "con_price": {"src": "consumption", "field": "avg_price_trieu", "rank": "qty", "sum": False,
                  "num": "revenue_ty", "den": "qty", "label": "Giá bán bình quân",
                  "unit": "triệu đ/tấn", "axis": "period"},
    "stk_total": {"src": "stock", "field": "total", "rank": "total", "sum": True,
                  "label": "Tồn kho thành phẩm", "unit": "tấn", "axis": "as_of"},
    # Thu mua: CHỈ phần thành phẩm mua ngoài mới gắn chủng loại — mủ nước/chén/dây đơn vị khai
    # theo tổng. `filter` ép mọi lượt gọi chỉ lấy khối thành phẩm để cột TỔNG khớp tổng các cột.
    "pur_material_qty": {"src": "purchase", "field": "qty_material", "rank": "qty_material",
                         "sum": True, "label": "Thu mua mủ nguyên liệu", "unit": "tấn",
                         "axis": "period", "filter": {"materials": "latex,cup,lace"},
                         "pin": set(MATERIAL_LABELS.values()), "note": _RAW_MIXED},
    "pur_finished_qty": {"src": "purchase", "field": "qty_finished", "rank": "qty_finished",
                         "sum": True, "label": "Thu mua thành phẩm", "unit": "tấn",
                         "axis": "period", "filter": {"materials": "finished"},
                         "note": _FINISHED_ONLY},
    "pur_finished_price": {"src": "purchase", "field": "price_finished_avg",
                           "rank": "qty_finished", "sum": False,
                           "num": "finished_revenue_vnd", "den": "finished_priced_qty",
                           "scale": 1 / 1_000_000, "label": "Giá thu mua thành phẩm BQ",
                           "unit": "triệu đ/tấn", "axis": "period",
                           "filter": {"materials": "finished"}, "note": _FINISHED_ONLY},
}

#: Quy đổi mặc định khi gộp giá bán: doanh thu tính bằng TỶ đồng, sản lượng tấn → ×1.000 ra triệu/tấn.
_TY_PER_TRIEU = 1000.0


def _combine(rows: list[dict], spec: dict) -> float | None:
    """Gộp nhiều ô thành một (dùng cho cột "Khác") — cộng dồn hoặc bình quân gia quyền."""
    if spec["sum"]:
        return sum(r.get(spec["field"]) or 0.0 for r in rows) or None
    num = sum(r.get(spec["num"]) or 0.0 for r in rows)
    den = sum(r.get(spec["den"]) or 0.0 for r in rows)
    return (num * spec.get("scale", _TY_PER_TRIEU) / den) if den else None


def _split(rows: list[dict]) -> dict[str, dict[str, dict]]:
    """Dòng khoá ghép đôi → {phạm vi: {chủng loại: dòng}}."""
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        scope, grade = unpair(r["key"])
        out.setdefault(scope, {})[grade] = r
    return out


def _from_by_grade(rows: list[dict]) -> dict[str, dict[str, dict]]:
    """Tồn kho: mỗi dòng ĐÃ mang sẵn `by_grade` → khỏi phải gọi thêm lượt gộp ghép đôi.

    Tiết kiệm 3 lượt quét (mỗi lượt còn kéo theo truy vấn hợp đồng), đo được 4,4s → 1,8s.
    """
    return {r["key"]: {g: {"total": q} for g, q in (r.get("by_grade") or {}).items()}
            for r in rows}


def _cells(src: str, scope: str, plain: dict, p: dict) -> dict[str, dict[str, dict]]:
    """{phạm vi: {chủng loại: ô}} cho một mức gộp (đơn vị hoặc khu vực)."""
    if src == "stock":
        return _from_by_grade(plain["rows"])
    return _split(_fetch(src, f"{scope}+grade", p)["rows"])


def _visible_grades(by_scope: dict[str, dict[str, dict]], spec: dict) -> tuple[list[str], set[str]]:
    """Chủng loại nào đáng đứng thành cột; phần còn lại trả về để gom vào "Các loại còn lại"."""
    weight: dict[str, float] = {}
    for grades in by_scope.values():
        for g, row in grades.items():
            weight[g] = weight.get(g, 0.0) + (row.get(spec["rank"]) or 0.0)
    total = sum(weight.values())
    ranked = sorted(weight, key=lambda g: -weight[g])
    # Cột GHIM luôn hiện dù nhỏ: với thu mua mủ nguyên liệu, ba nhãn "Mủ nước/Mủ chén/Mủ dây" là
    # phần CHƯA TÁCH chủng loại — gom nó vào "Các loại còn lại" thì người xem không còn biết bao
    # nhiêu sản lượng đang chưa được tách.
    pin = spec.get("pin") or set()
    keep = [g for g in ranked
            if g in pin or (total and weight[g] / total >= MIN_SHARE)][:MAX_GRADES]
    return keep, {g for g in weight if g not in set(keep)}


def _values(cells: dict[str, dict], keep: list[str], rest: set[str], spec: dict,
            total_row: dict | None) -> dict[str, Any]:
    """Một dòng của bảng chéo: mỗi chủng loại một ô + ô "Khác" + ô TỔNG."""
    vals: dict[str, Any] = {g: (cells.get(g) or {}).get(spec["field"]) for g in keep}
    others = [cells[g] for g in rest if g in cells]
    vals[OTHER] = _combine(others, spec) if others else None
    # Cột TỔNG lấy THẲNG từ bảng thống kê không tách chủng loại — không cộng lại các ô, vì giá
    # bình quân cộng lại sẽ sai và vì tổng phải khớp đúng con số ở các tab khác.
    vals[TOTAL] = (total_row or {}).get(spec["field"])
    return vals


def by_grade(measure: str, **p: Any) -> dict[str, Any]:
    """Bảng chéo: dòng = Tập đoàn → khu vực → đơn vị, cột = chủng loại, ô = một chỉ số."""
    if measure not in MEASURES:
        raise ValueError(f"Chỉ số không hợp lệ: {measure}")
    spec = MEASURES[measure]
    src = spec["src"]
    p = {**p, **spec.get("filter", {})}   # vd chỉ số thu mua chỉ xét khối thành phẩm

    plain_company = _fetch(src, "company", p)
    plain_region = _fetch(src, "region", p)
    by_company = _cells(src, "company", plain_company, p)
    by_region = _cells(src, "region", plain_region, p)
    comp_total = {r["key"]: r for r in plain_company["rows"]}
    reg_total = {r["key"]: r for r in plain_region["rows"]}

    merged: dict[str, dict[str, dict]] = {**by_company, **by_region}
    keep, rest = _visible_grades(merged, spec)

    regions = []
    for label, units in region_tree(p):
        children = [{
            "company": u["name"], "merged_into": u.get("merged_into"),
            "values": _values(by_company.get(u["name"], {}), keep, rest, spec,
                              comp_total.get(u["name"])),
        } for u in units]
        for c in children:
            c["has_data"] = any(v is not None for v in c["values"].values())
        regions.append({
            "region": label, "units": len(children),
            "no_data": sum(1 for c in children if not c["has_data"]),
            "values": _values(by_region.get(label, {}), keep, rest, spec, reg_total.get(label)),
            "children": children,
        })

    unit = spec["unit"]
    cols = [{"key": g, "label": g, "unit": unit, "note": "", "compare": False} for g in keep]
    if rest:
        # KHÔNG đặt tên "Khác": trong danh mục đã có một chủng loại tên thật là "Chủng loại khác",
        # hai cột cùng tên cạnh nhau thì không ai đọc ra được cột nào là cột nào.
        cols.append({"key": OTHER, "label": "Các loại còn lại", "unit": unit, "compare": False,
                     "note": f"{len(rest)} chủng loại lẻ"})
    cols.append({"key": TOTAL, "label": "TỔNG", "unit": unit, "compare": False,
                 "note": "cả chủng loại chưa hiện cột"})

    return {
        "measure": measure, "label": spec["label"], "unit": unit, "axis": spec["axis"],
        "note": spec.get("note", ""),
        "date_from": p["date_from"], "date_to": p["date_to"], "as_of": p["as_of"],
        "cols": cols, "regions": regions,
        # Dòng TOÀN TẬP ĐOÀN: gộp theo chủng loại trên toàn phạm vi lọc (một lượt `group_by=grade`).
        "totals": _values(_total_cells(src, plain_company, p), keep, rest, spec,
                          plain_company["totals"]),
        "hidden_grades": sorted(rest), "warnings": [], "coverage": None,
        "latest_stock_day": None,
    }


def _total_cells(src: str, plain_company: dict, p: dict[str, Any]) -> dict[str, dict]:
    """Ô chủng loại của dòng TOÀN TẬP ĐOÀN (gộp trên toàn phạm vi lọc)."""
    if src == "stock":
        return {g: {"total": q} for g, q in (plain_company["totals"].get("by_grade") or {}).items()}
    return {r["key"]: r for r in _fetch(src, "grade", p)["rows"]}
