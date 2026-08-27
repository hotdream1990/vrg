"""Thống kê Tồn kho — ảnh chụp tại một NGÀY CHỐT (số THỜI ĐIỂM, không cộng dồn).

Đơn vị KHAI tồn ngày nào thì lấy đúng số ngày đó; đơn vị tick "không phát sinh tồn kho để khai"
thì giữ nguyên số của lần khai gần nhất; đơn vị không khai gì thì báo thiếu, KHÔNG đắp số ngày
khác vào (quy tắc chung ở `unit_report_rows.stock_rows`, chốt 21/08/2026). Mỗi dòng **luôn trả kèm
ngày đã lấy + số ngày đã cũ** để người xem biết số thuộc ngày nào.

Ngoài 3 khối đơn vị nhập tay (chưa nhập kho · đã nhập kho · nguyên liệu), báo cáo còn 2 chỉ tiêu
SUY RA từ hợp đồng bán hàng, lấy tại ĐÚNG ngày của số tồn:
- `signed_undelivered` — đã ký HĐ chưa giao (sản lượng hợp đồng − đã giao), NẰM TRONG tồn thành phẩm
- `tradable`           — tồn có thể giao dịch = `total` − `signed_undelivered` (có thể âm)
"""

from __future__ import annotations

from typing import Any

from app.services import member_unit_merge, unit_report_rows
from app.services.unit_report_query import (
    dmy, filter_scope, merge_rollup, merge_scope, merge_view, report_units, sort_groups,
    split_csv,
)

_BLOCK_KEY = {"stock_not_warehoused": "not_warehoused", "stock_warehoused": "warehoused"}
#: Khối tự tính từ hợp đồng: phần ĐÃ KÝ CHƯA GIAO — NẰM TRONG tồn thành phẩm nên chỉ trừ ra để
#: biết còn bao nhiêu bán được, KHÔNG cộng vào tổng tồn (cộng nữa là tính trùng chính lô hàng đó).
_CONTRACT = unit_report_rows.CONTRACT_BLOCK

#: Số tên đơn vị liệt kê thẳng trong câu cảnh báo (dài hơn thì gộp phần đuôi lại cho đọc được).
_MAX_NAMES = 12


def _new_group(key: str, region: str | None) -> dict[str, Any]:
    return {"key": key, "label": key, "region": region, "not_warehoused": 0.0,
            "warehoused": 0.0, "material": 0.0, "signed_undelivered": 0.0,
            "by_grade": {}, "_dates": set(), "_ages": set()}


def _feed(g: dict, r: dict, with_grade: bool) -> None:
    qty = r["qty"] or 0.0
    g["_dates"].add(r["as_of"])
    g["_ages"].add(r["age_days"])
    if r["block"] == "stock_material":
        g["material"] += qty
        return
    if r["block"] == _CONTRACT:
        g["signed_undelivered"] += qty
        return                       # `by_grade` là TỒN theo chủng loại — không trộn số hợp đồng
    g[_BLOCK_KEY[r["block"]]] += qty
    if with_grade:
        g["by_grade"][r["grade"]] = (g["by_grade"].get(r["grade"]) or 0.0) + qty


def _close(g: dict) -> dict[str, Any]:
    dates = sorted(g.pop("_dates"))
    g["dates"] = dates                 # ĐÚNG các ngày đã lấy số (để đối chiếu, không suy diễn)
    # Nhóm gồm nhiều ngày (vd theo khu vực) → KHÔNG hiện 1 ngày duy nhất, dễ hiểu sai là số cùng ngày.
    g["as_of"] = dates[-1] if len(dates) == 1 else None
    # Số ngày cũ NHẤT trong nhóm: luôn đúng dù nhóm gồm mấy ngày, và là con số người xem cần
    # (nhóm có số cũ 8 ngày thì cả nhóm đáng ngờ, không phải chỉ dòng đó).
    g["age_days"] = max(g.pop("_ages"), default=None)
    g["total"] = (g["not_warehoused"] + g["warehoused"]) or None
    # Tồn CÓ THỂ GIAO DỊCH = tồn thành phẩm − đã ký HĐ chưa giao. Có thể ÂM (đã ký nhiều hơn lượng
    # đang có trong kho) — giữ nguyên dấu âm, cắt về 0 là giấu mất phần đang thiếu hàng để giao.
    signed = g["signed_undelivered"]
    g["tradable"] = ((g["total"] or 0.0) - signed) if (g["total"] is not None or signed) else None
    for k in ("not_warehoused", "warehoused", "material", "signed_undelivered"):
        g[k] = g[k] or None
    g["by_grade"] = {k: v for k, v in sorted(g["by_grade"].items()) if v}
    return g


def _drop_superseded(rows: list[dict]) -> list[dict]:
    """Bỏ ảnh chụp của đơn vị ĐÃ SÁP NHẬP khi kho đó đã nằm trong số của đơn vị nhận.

    Ảnh chụp tại ngày chốt lấy lần khai gần nhất của từng đơn vị, nên đơn vị cũ (ngừng khai từ
    ngày sáp nhập) vẫn còn một ảnh chụp cũ. Đơn vị nhận đã khai kể từ ngày đó thì hàng của đơn vị
    cũ đã được khai chung — cộng thêm ảnh chụp cũ là tính trùng chính lô hàng đó.
    """
    latest: dict[str, str] = {}
    for r in rows:
        if r["as_of"] > latest.get(r["company"], ""):
            latest[r["company"]] = r["as_of"]
    drop = member_unit_merge.stock_superseded(latest)
    return [r for r in rows if r["company"] not in drop] if drop else rows


def _latest_per_company(rows: list[dict]) -> list[dict]:
    """Ảnh chụp tại ngày chốt: giữ các dòng của ngày MỚI NHẤT mà từng đơn vị có số."""
    last: dict[str, str] = {}
    for r in rows:
        if r["as_of"] > last.get(r["company"], ""):
            last[r["company"]] = r["as_of"]
    return [r for r in rows if r["as_of"] == last[r["company"]]]


def _coverage(snap: list[dict], no_stock: dict[str, str], comps: list[str] | None,
              regs: list[str] | None, split_merged: bool = False) -> dict[str, Any]:
    """Độ phủ của ảnh chụp: bao nhiêu đơn vị có số, đơn vị nào chưa có số.

    Thiếu đơn vị là chuyện PHẢI hiện ra: tổng tồn kho toàn Tập đoàn thiếu vài đơn vị mà không báo
    thì người xem tưởng đó là số đầy đủ. Đơn vị khai "không phát sinh tồn kho" tách thành nhóm
    RIÊNG — đã nộp nên không phải "chưa nhập", nhưng cũng không có số nào để cộng vào tổng.

    Số giữ lại theo cờ "không phát sinh" KHÔNG bị điểm mặt riêng: mỗi dòng đã mang sẵn ngày lấy số
    + số ngày đã cũ, người xem tự thấy — thêm cảnh báo ngưỡng nữa chỉ gây nhiễu.
    """
    units = report_units(split_merged)   # xem TÁCH thì đơn vị đã sáp nhập cũng nằm trong khung
    if comps:
        keep = set(comps)
        units = [u for u in units if u["name"] in keep]
    if regs:
        keep = set(regs)
        units = [u for u in units if (u.get("region") or "") in keep]

    got: dict[str, dict[str, Any]] = {}
    for r in snap:
        got.setdefault(r["company"], {"as_of": r["as_of"], "age_days": r["age_days"]})
    rest = [u for u in units if u["name"] not in got]
    empty = [{"company": u["name"], "as_of": no_stock[u["name"]]}
             for u in rest if u["name"] in no_stock]
    missing = [{"company": u["name"], "has_factory": bool(u.get("has_factory", True))}
               for u in rest if u["name"] not in no_stock]
    return {"units_expected": len(units), "units_counted": len(got),
            "no_stock": empty, "missing": missing}


def _names(items: list[dict], key: str = "company") -> str:
    head = ", ".join(str(i[key]) for i in items[:_MAX_NAMES])
    more = len(items) - _MAX_NAMES
    return f"{head} …và {more} đơn vị khác" if more > 0 else head


def _warnings(cov: dict, as_of: str, group_by: str) -> list[str]:
    w: list[str] = []
    if cov["missing"]:
        w.append(f"{len(cov['missing'])} đơn vị chưa có số tồn kho tại ngày {dmy(as_of)} → KHÔNG tính vào "
                 f"tổng (kể cả phần đã ký HĐ chưa giao của họ): {_names(cov['missing'])}.")
    # Đơn vị khai "không phát sinh tồn kho" KHÔNG lên cảnh báo: họ đã nộp đúng hạn, không có gì
    # sai để nhắc. Vẫn giữ trong `coverage` để dải độ phủ cộng đủ (có số + khai trống + chưa có số).
    if group_by == "day":
        w.append(f"Mỗi dòng là tồn của riêng ngày đó (không cộng dồn); dòng Tổng cộng là ảnh chụp "
                 f"tại ngày chốt {dmy(as_of)} — mỗi đơn vị lấy số mới nhất của mình.")
    return w


def stock_report(as_of: str, days_back: int = 0, *, companies: str | None = None,
                 regions: str | None = None, grades: str | None = None,
                 group_by: str = "company", split_merged: bool = False) -> dict[str, Any]:
    """Tồn kho tại NGÀY CHỐT theo bộ lọc (đơn vị · khu vực · chủng loại).

    Số của mỗi đơn vị lấy theo quy tắc ở `unit_report_rows.stock_rows`: khai ngày nào dùng ngày đó,
    tick "không phát sinh" thì giữ số lần khai gần nhất, không khai gì thì KHÔNG có số.
    `days_back` chỉ dùng khi nhóm theo NGÀY (xem diễn biến bao nhiêu ngày trở lại).
    """
    comps, regs, grds = split_csv(companies), split_csv(regions), split_csv(grades)
    # Nhóm theo NGÀY = xem diễn biến tồn → giữ mọi ngày trong cửa sổ; các cách nhóm khác chỉ lấy
    # ảnh chụp tại ngày chốt (mỗi đơn vị 1 dòng số mới nhất của mình).
    raw = unit_report_rows.stock_rows(as_of, merge_scope(comps, split_merged),
                                      all_days=group_by == "day",
                                      days_back=days_back if group_by == "day" else 0)
    rows = raw["rows"]
    # "Số mới nhất của từng đơn vị" phải chọn TRÊN TÊN ĐƠN VỊ GỐC rồi mới gộp: gộp trước thì ảnh
    # chụp của đơn vị cũ và đơn vị mới tranh nhau một chỗ, chỉ một cái sống sót → mất tồn kho.
    snap = _latest_per_company(rows) if group_by == "day" else rows
    # Tồn kho là số THỜI ĐIỂM. Bảng theo NGÀY giữ nguyên mọi dòng (mỗi ngày một ảnh chụp riêng,
    # cộng hai đơn vị trong cùng ngày là đúng); còn ảnh chụp tại ngày chốt phải bỏ đơn vị đã sáp
    # nhập mà kho của họ nay do đơn vị nhận khai chung — xem `_drop_superseded`.
    if not split_merged:
        snap = _drop_superseded(snap)
        if group_by != "day":
            rows = snap
    rows = merge_rollup(rows, split_merged)
    snap = merge_rollup(snap, split_merged)
    view = merge_view(comps, split_merged)
    rows, snap = filter_scope(rows, view, regs), filter_scope(snap, view, regs)
    # Độ phủ tính TRƯỚC khi lọc chủng loại: đơn vị có tồn nhưng không có chủng loại đang lọc thì
    # vẫn là đơn vị "đã nhập", không được đếm thành thiếu số liệu.
    cov = _coverage(snap, raw["no_stock"], comps, regs, split_merged)
    if grds:   # lọc chủng loại: chỉ áp cho 2 khối thành phẩm, tồn nguyên liệu không có chủng loại
        keep = set(grds)
        def _keep(lst: list[dict]) -> list[dict]:
            return [r for r in lst if r["block"] == "stock_material" or r["grade"] in keep]
        rows, snap = _keep(rows), _keep(snap)

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

    # Dòng Tổng cộng LUÔN là ảnh chụp tại ngày chốt (kể cả khi nhóm theo ngày): tồn kho là số thời
    # điểm nên cộng nhiều ngày là tính trùng chính lô hàng đó.
    total = _new_group("Tổng cộng", None)
    for r in snap:
        _feed(total, r, with_grade=True)
    return {"as_of": as_of, "days_back": days_back, "group_by": group_by,
            "rows": [_close(g) for g in sort_groups(groups, group_by)],
            "totals": _close(total), "coverage": cov,
            "warnings": _warnings(cov, as_of, group_by)}
