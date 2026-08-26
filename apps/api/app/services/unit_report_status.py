"""Tình trạng nộp báo cáo ngày của các đơn vị — ma trận đơn vị × ngày (chỉ đọc).

Tách khỏi `unit_report_stock` (thống kê tồn kho) vì là việc khác hẳn: ở đây chỉ quan tâm ĐÃ NỘP
hay CHƯA, không quan tâm con số.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import member_unit_merge, unit_daily_fields as fields, unit_daily_repo
from app.services.unit_report_query import report_units, split_csv


def _date_list(date_from: str, date_to: str) -> list[str]:
    a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def status_report(kind: str, date_from: str, date_to: str, *, companies: str | None = None,
                  regions: str | None = None) -> dict[str, Any]:
    """Ma trận đơn vị × ngày: `ok` đã nhập · `no_purchase` không tổ chức thu mua · `none` chưa nhập.

    Biểu Thu mua chỉ tính các đơn vị ĐƯỢC GIAO kế hoạch thu mua (đơn vị khác không phải nộp) —
    lấy ĐÚNG danh sách bật màn Thu mua cho người dùng, xem `companies_with_purchase_plan`.
    Đơn vị chỉ tính là ĐÃ NỘP khi bản ghi có số liệu thật của biểu đó (`fields.has_data`).

    Bảng này LUÔN để đơn vị đã sáp nhập đứng riêng (không gộp như các bảng số liệu): "ai nộp, ai
    chưa" là chuyện của từng đơn vị nhập liệu. Các ngày TỪ ngày sáp nhập trở đi của đơn vị cũ mang
    trạng thái `merged` — không phải "chưa nộp" (họ không còn phải nộp nữa) và không vào mẫu số.
    """
    comps, regs = split_csv(companies), split_csv(regions)
    units = report_units(split_merged=True)
    merged_at = {m["name"]: m["merged_at"] for m in member_unit_merge.merged_units()}
    if kind == "purchase":
        # KHÔNG dùng cờ `member_unit.has_purchase_plan`: cờ đó bỏ từ 03/08/2026, số ở màn Kế hoạch
        # năm mới là công tắc. Dùng cờ cũ thì bảng đòi nộp cả những đơn vị KHÔNG có màn Thu mua.
        planned = unit_daily_repo.companies_with_purchase_plan(
            date.fromisoformat(date_to).year)
        units = [u for u in units if u["name"] in planned]
    if comps:
        keep = set(comps)
        units = [u for u in units if u["name"] in keep]
    if regs:
        keep = set(regs)
        units = [u for u in units if (u.get("region") or "") in keep]

    # `attach_contracts=False`: bảng này chỉ hỏi "đã nộp hay chưa" (`fields.has_data`, xem
    # `_SUBMITTED_KEYS`) nên không đụng tới khối 3 — mà gắn khối đó là MỘT truy vấn hợp đồng cho
    # MỖI ngày trong khoảng (kỳ 8 tháng = 237 truy vấn, đo được 1,76s chỉ để rồi vứt đi).
    entries = unit_daily_repo.in_range(kind, date_from, date_to, [u["name"] for u in units],
                                       attach_contracts=False)
    state: dict[tuple[str, str], str] = {}
    for e in entries:
        # Bản ghi rỗng KHÔNG tính là đã nộp — biểu Tồn kho đang mang hàng trăm bản ghi cũ của biểu
        # Tiêu thụ (chỉ có mảng `sales` + cờ `sales_migrated`), tính vào là báo cáo tỷ lệ nộp ảo.
        if not fields.has_data(kind, e["fields"]):
            continue
        no_buy = kind == "purchase" and e["fields"].get("no_purchase") is True
        state[(e["company"], e["as_of"])] = "no_purchase" if no_buy else "ok"

    dates = _date_list(date_from, date_to)
    rows, filled, no_purchase, expected = [], 0, 0, 0
    for u in units:
        gone = merged_at.get(u["name"])       # ngày sáp nhập — từ ngày này đơn vị hết phải nộp
        cells = {d: ("merged" if gone and d >= gone else state.get((u["name"], d), "none"))
                 for d in dates}
        # Đơn vị đã sáp nhập TRƯỚC cả kỳ đang xem thì không còn dòng nào để nhắc — bỏ hẳn khỏi bảng
        # thay vì để một dòng xám toàn tập làm loãng tỷ lệ nộp.
        if gone and all(v == "merged" for v in cells.values()):
            continue
        ok = sum(1 for v in cells.values() if v == "ok")
        skip = sum(1 for v in cells.values() if v == "no_purchase")
        due = sum(1 for v in cells.values() if v != "merged")
        filled += ok
        no_purchase += skip
        expected += due
        rows.append({"company": u["name"], "region": u.get("region"), "cells": cells,
                     "merged_into": u.get("merged_into"), "merged_at": gone,
                     "filled": ok, "no_purchase": skip, "missing": due - ok - skip,
                     "last_day": max((d for d, v in cells.items() if v not in ("none", "merged")),
                                     default=None)})
    return {"kind": kind, "date_from": date_from, "date_to": date_to, "dates": dates, "rows": rows,
            "totals": {"expected": expected, "filled": filled, "no_purchase": no_purchase,
                       "missing": expected - filled - no_purchase}}


def missing_cells(kind: str, date_from: str, date_to: str, *, companies: str | None = None,
                  regions: str | None = None) -> list[dict[str, str]]:
    """Các ô (đơn vị × ngày) CÒN TRỐNG trong khoảng — đầu vào cho thao tác đánh dấu hàng loạt.

    Dùng lại đúng `status_report` để "trống" ở đây luôn khớp ô đỏ người dùng thấy trên ma trận
    (cùng danh sách đơn vị phải nộp, cùng luật `has_data`). Ngày SAU hôm nay bị loại: chưa xảy ra
    thì không thể kết luận đơn vị không tổ chức thu mua.
    """
    rep = status_report(kind, date_from, date_to, companies=companies, regions=regions)
    today = date.today().isoformat()
    return [{"company": r["company"], "as_of": d}
            for r in rep["rows"] for d, v in r["cells"].items() if v == "none" and d <= today]
