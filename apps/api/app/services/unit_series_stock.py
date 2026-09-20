"""Chuỗi TỒN KHO theo ngày từ biểu "Tồn kho" của đơn vị thành viên (Command Center · Bản tin biến động).

Ba quy tắc bắt buộc giữ nguyên để các màn không lệch nhau:

1. **Ảnh chụp từng ngày, KHÔNG cộng dồn**, lấy số theo đúng quy tắc dùng chung ở
   `unit_report_rows.stock_rows`: đơn vị khai ngày nào dùng ngày đó · tick "không phát sinh tồn kho
   để khai" thì giữ số lần khai gần nhất · không khai gì thì không có số.
2. **Tồn kho thành phẩm = "chưa nhập kho" + "đã nhập kho"** — cùng định nghĩa với Thống kê tồn kho,
   Báo cáo tồn kho và Báo cáo tổng hợp (sửa 06/09/2026). Trước đó chuỗi này chỉ cộng khối "đã nhập
   kho" để bằng chuỗi tuần `inventory_auto`, nên thấp hơn các màn kia 16-18% (≈11.900 tấn/ngày đo
   trên prod 03/09/2026) trong khi nhãn vẫn ghi "tồn kho tổng" → người xem không biết tin màn nào.
   Cách nhìn `warehouse` giữ lại đường đối chiếu: cột chồng 2 lớp, lớp dưới đúng bằng số của chuỗi
   tuần Ban TTKD đang dùng.
3. **Đơn vị đã sáp nhập**: bỏ ảnh chụp của đơn vị cũ khi đơn vị nhận cũng có số trong NGÀY ĐÓ
   (`member_unit_merge.superseded_in`) — cùng luật với Thống kê tồn kho, nếu không cùng một lô hàng
   bị đếm hai lần kể từ ngày hiệu lực.
"""

from __future__ import annotations

from typing import Any

from app.services import member_unit_merge, unit_report_rows
from app.services.unit_series import days_between, series_of

#: Ngày đầu tiên các đơn vị nhập biểu Tồn kho đủ độ phủ (42 đơn vị; các ngày trước đó ≤ 12) —
#: trước mốc này chuỗi chỉ là vài đơn vị lẻ, vẽ lên biểu đồ sẽ thành "tồn kho Tập đoàn sụt mạnh".
STOCK_START = "2026-07-24"

#: 5 cách nhìn tồn kho. `warehouse` (mặc định) = cột chồng 2 lớp đã/chưa nhập kho: tổng đúng bằng
#: các màn báo cáo mà vẫn đọc riêng được lớp "đã nhập kho" để đối chiếu số tay Ban TTKD.
#: `free_grade` = phần CÒN BÁN ĐƯỢC của từng chủng loại (tồn − đã ký hợp đồng), câu hỏi thường trực
#: của Ban TTKD: "loại nào đang ế" chứ không chỉ "còn bao nhiêu".
GROUPS = ("warehouse", "structure", "grade", "region", "free_grade")

#: Ngày CUỐI chuỗi thường đang nhập dở (đo prod 21/08/2026: 4 đơn vị lúc 9h sáng so với ~53 ngày
#: trước). Từ khi bỏ đắp số ngày cũ, những ngày đó tụt thành vách đá trên biểu đồ, nhìn như Tập
#: đoàn bán sạch kho trong một đêm. Cắt phần ĐUÔI chưa đạt ngần này so với ngày phủ tốt nhất và
#: nói rõ đã cắt mấy ngày — cắt đuôi chứ không cắt giữa: ngày giữa mà thiếu thì đó là sự thật.
MIN_COVERAGE_RATIO = 0.85
NO_REGION = "Chưa gán khu vực"


STRUCTURE_KEYS: tuple[tuple[str, str], ...] = (
    ("signed", "Đã ký hợp đồng"),
    ("free", "Tồn tự do (chưa ký)"),
)
#: Lớp dưới trước, lớp trên sau — thứ tự này quyết định thứ tự chồng cột trên biểu đồ.
WAREHOUSE_KEYS: tuple[tuple[str, str], ...] = (
    ("warehoused", "Đã nhập kho"),
    ("not_warehoused", "Chưa nhập kho"),
)


def _trim_pending(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bỏ các ngày CUỐI chưa đủ đơn vị nhập; trả (chuỗi đã cắt, các ngày bị cắt) để UI nói rõ."""
    best = max((r["units_counted"] for r in rows), default=0)
    if not best:
        return rows, []
    need = best * MIN_COVERAGE_RATIO
    cut = len(rows)
    while cut and rows[cut - 1]["units_counted"] < need:
        cut -= 1
    pending = [{"as_of": r["as_of"], "units_counted": r["units_counted"]} for r in rows[cut:]]
    return (rows[:cut], pending) if cut else (rows, [])


def _free_by_grade(stock: dict[str, float], signed: dict[str, float]) -> dict[str, float]:
    """Tồn TỰ DO của một đơn vị theo chủng loại = tồn − đã ký hợp đồng, CẮT TRẦN từng chủng loại.

    Cắt trần vì hợp đồng ký cả cho hàng chưa sản xuất (đúng quy tắc `inventory_auto`): lấy nguyên
    số hợp đồng thì phần "tự do" âm và cột chồng vỡ. Chủng loại chỉ có hợp đồng mà không có tồn thì
    không sinh ra dòng nào — không có hàng thì không có gì để bán.
    """
    return {g: q - min(signed.get(g, 0.0), q) for g, q in stock.items() if q > 0}


def _collect(raw_rows: list[dict[str, Any]]) -> tuple[dict, dict, dict, dict]:
    """Làm phẳng dòng chi tiết thành 4 bảng tra theo ngày.

    - `stock[ngày][đơn vị][chủng loại]` — tồn THÀNH PHẨM (cộng cả 2 khối đã/chưa nhập kho)
    - `wh[ngày][đơn vị]`                — riêng khối "đã nhập kho" (cho cách nhìn `warehouse`)
    - `signed[ngày][đơn vị][chủng loại]`— đã ký hợp đồng chưa giao
    - `regions[đơn vị]`                 — khu vực để nhóm
    """
    stock: dict[str, dict[str, dict[str, float]]] = {}
    wh: dict[str, dict[str, float]] = {}
    signed: dict[str, dict[str, dict[str, float]]] = {}
    regions: dict[str, str] = {}
    for r in raw_rows:
        qty = r["qty"] or 0.0
        if not qty:
            continue
        regions[r["company"]] = r.get("region") or NO_REGION
        if r["block"] == unit_report_rows.CONTRACT_BLOCK:
            by_grade = signed.setdefault(r["as_of"], {}).setdefault(r["company"], {})
            by_grade[r["grade"]] = by_grade.get(r["grade"], 0.0) + qty
            continue
        if r["block"] not in unit_report_rows.STOCK_BLOCKS:
            continue                       # tồn NGUYÊN LIỆU không phải thành phẩm → không vào đây
        by_grade = stock.setdefault(r["as_of"], {}).setdefault(r["company"], {})
        by_grade[r["grade"]] = by_grade.get(r["grade"], 0.0) + qty
        if r["block"] == "stock_warehoused":
            day = wh.setdefault(r["as_of"], {})
            day[r["company"]] = day.get(r["company"], 0.0) + qty
    return stock, wh, signed, regions


def stock_series(date_from: str, date_to: str, group_by: str = "warehouse") -> dict[str, Any]:
    """Tồn kho Tập đoàn theo ngày, nhóm theo kho · cơ cấu hợp đồng · chủng loại · khu vực.

    Mỗi ngày kèm `units_counted` = số đơn vị THẬT SỰ có tồn thành phẩm trong ảnh chụp đó: thiếu đơn
    vị mà không nói ra thì người xem tưởng cột thấp là hàng bán được nhiều, trong khi thật ra là
    chưa ai nhập.

    ⚠ KHÔNG trả "n/N đơn vị": mẫu số nào cũng sai. Toàn bộ đơn vị hoạt động (67) gồm 22 đơn vị
    KHÔNG có nhà máy — họ không có tồn thành phẩm để khai; còn cờ `has_factory` cũng không dùng làm
    mẫu số được (đo prod 21/08/2026: 53 đơn vị có tồn thành phẩm nhưng chỉ 43 trong số đó gắn cờ có
    nhà máy). Đếm đơn vị CÓ SỐ là con số duy nhất nói đúng về cái biểu đồ đang vẽ.

    ⚠ `total` LUÔN là tồn kho tổng, kể cả ở cách nhìn `free_grade` (nơi các cột chỉ là phần tự do) —
    dòng tổng dưới biểu đồ và tooltip phải nói đúng con số tồn, không đổi nghĩa theo cách xem.
    """
    if group_by not in GROUPS:
        group_by = "warehouse"
    days = days_between(date_from, date_to)
    # Chỉ 2 cách xem dùng tới khối "đã ký HĐ chưa giao"; 3 cách còn lại (kho · chủng loại ·
    # khu vực) không đụng tới `signed`, mà khối đó là phần đắt nhất của cả chuỗi.
    raw = unit_report_rows.stock_rows(date_to, all_days=True, days_back=len(days) - 1,
                                      with_contracts=group_by in ("structure", "free_grade"))
    stock, wh, signed, regions = _collect(raw["rows"])
    pairs = member_unit_merge.merge_pairs()

    rows: list[dict[str, Any]] = []
    grade_totals: dict[str, float] = {}
    for day in days:
        by_company = dict(stock.get(day, {}))
        # Ảnh chụp cùng NGÀY nên `latest` của mọi đơn vị chính là ngày đó — luật sáp nhập chỉ cắt
        # từ ngày hiệu lực trở đi, và chỉ khi đơn vị nhận cũng có số hôm đó (xem `superseded_in`).
        for dead in member_unit_merge.superseded_in(pairs, dict.fromkeys(by_company, day)):
            by_company.pop(dead, None)
        signed_day = signed.get(day, {})
        wh_day = wh.get(day, {})
        total = sum(sum(g.values()) for g in by_company.values())
        values: dict[str, float] = {}
        if group_by == "warehouse":
            done = sum(q for c, q in wh_day.items() if c in by_company)
            values = {"warehoused": done, "not_warehoused": total - done}
        elif group_by == "structure":
            done = sum(min(sum((signed_day.get(c) or {}).values()), sum(g.values()))
                       for c, g in by_company.items())
            values = {"signed": done, "free": total - done}
        elif group_by == "free_grade":
            for company, grades in by_company.items():
                for grade, q in _free_by_grade(grades, signed_day.get(company) or {}).items():
                    values[grade] = values.get(grade, 0.0) + q
                    grade_totals[grade] = grade_totals.get(grade, 0.0) + q
        elif group_by == "grade":
            for grades in by_company.values():
                for grade, q in grades.items():
                    values[grade] = values.get(grade, 0.0) + q
                    grade_totals[grade] = grade_totals.get(grade, 0.0) + q
        else:
            for company, grades in by_company.items():
                region = regions.get(company) or NO_REGION
                values[region] = values.get(region, 0.0) + sum(grades.values())
        rows.append({"as_of": day, "total": round(total, 3) if by_company else None,
                     "units_counted": len(by_company),
                     "values": {k: round(v, 3) for k, v in values.items()}})

    rows, pending = _trim_pending(rows)

    if group_by in ("grade", "free_grade"):
        series = series_of(rows, grade_totals)
    elif group_by == "region":
        series = series_of(rows)
    else:
        series = [{"key": k, "label": lb} for k, lb in
                  (WAREHOUSE_KEYS if group_by == "warehouse" else STRUCTURE_KEYS)]

    return {"date_from": date_from, "date_to": date_to, "group_by": group_by,
            "start_floor": STOCK_START, "series": series, "rows": rows, "pending": pending}
