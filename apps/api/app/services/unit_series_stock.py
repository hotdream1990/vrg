"""Chuỗi TỒN KHO theo ngày từ biểu "Tồn kho" của đơn vị thành viên (Command Center · Bản tin biến động).

Hai quy tắc bắt buộc giữ nguyên để các màn không lệch nhau:

1. **Ảnh chụp từng ngày, KHÔNG cộng dồn.** Mỗi ngày, mỗi đơn vị lấy bản ghi tồn mới nhất ≤ ngày đó
   và cũ không quá `inventory_auto.MAX_AGE_DAYS`; cũ hơn coi như không có số (thà thiếu còn hơn đắp
   số ngày khác vào).
2. **Tồn kho = khối "Đã nhập kho"**, phần "đã có HĐ" = Σ `min(đã ký chưa giao, đã nhập kho)` của
   TỪNG đơn vị — đúng công thức `inventory_auto.compute()` đang ghi vào chuỗi tuần của Tập đoàn.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import unit_daily_repo, unit_report_rows
from app.services.inventory_auto import MAX_AGE_DAYS
from app.services.unit_series import days_between, num, series_of

#: Ngày đầu tiên các đơn vị nhập biểu Tồn kho đủ độ phủ (42 đơn vị; các ngày trước đó ≤ 12) —
#: trước mốc này chuỗi chỉ là vài đơn vị lẻ, vẽ lên biểu đồ sẽ thành "tồn kho Tập đoàn sụt mạnh".
STOCK_START = "2026-07-24"

#: 4 cách nhìn tồn kho. `free_grade` = phần CÒN BÁN ĐƯỢC của từng chủng loại (tồn − đã ký hợp đồng),
#: câu hỏi thường trực của Ban TTKD: "loại nào đang ế" chứ không chỉ "còn bao nhiêu".
GROUPS = ("structure", "grade", "region", "free_grade")
NO_REGION = "Chưa gán khu vực"


STRUCTURE_KEYS: tuple[tuple[str, str], ...] = (
    ("signed", "Đã ký hợp đồng"),
    ("free", "Tồn tự do (chưa ký)"),
)


def _snapshots(date_from: str, date_to: str) -> dict[str, dict[str, dict[str, Any]]]:
    """{ngày: {đơn vị: bản ghi tồn}} — mỗi ngày là ảnh chụp độc lập, KHÔNG cộng dồn.

    Bản ghi được dùng lại cho các ngày sau tối đa `MAX_AGE_DAYS` ngày (đơn vị không nhập hằng ngày),
    quá hạn thì rơi khỏi ảnh chụp — không đắp số quá cũ cho ngày đang xét.
    """
    start = (date.fromisoformat(date_from) - timedelta(days=MAX_AGE_DAYS)).isoformat()
    entries = unit_daily_repo.in_range("consumption", start, date_to, attach_contracts=False)
    latest: dict[str, dict[str, Any]] = {}          # đơn vị → bản ghi tồn mới nhất đã gặp
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        if unit_report_rows.has_stock(e["fields"]):
            by_day.setdefault(e["as_of"], []).append(e)

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for day in days_between(start, date_to):
        for e in by_day.get(day, []):
            latest[e["company"]] = e
        if day < date_from:
            continue
        limit = (date.fromisoformat(day) - timedelta(days=MAX_AGE_DAYS)).isoformat()
        out[day] = {c: e for c, e in latest.items() if e["as_of"] >= limit}
    return out


def _warehoused(fields: dict) -> dict[str, float]:
    """{chủng loại: tấn} của khối "Đã nhập kho" — khối được chọn làm TỒN KHO (xem docstring module)."""
    out: dict[str, float] = {}
    for ln in fields.get("stock_warehoused") or []:
        q = num(ln.get("qty"))
        if q is None:
            continue
        grade = str(ln.get("grade") or "").strip() or "—"
        out[grade] = out.get(grade, 0.0) + q
    return out


def _free_by_grade(stock: dict[str, float], signed: dict[str, float]) -> dict[str, float]:
    """Tồn TỰ DO của một đơn vị theo chủng loại = tồn − đã ký hợp đồng, CẮT TRẦN từng chủng loại.

    Cắt trần vì hợp đồng ký cả cho hàng chưa sản xuất (đúng quy tắc `inventory_auto`): lấy nguyên
    số hợp đồng thì phần "tự do" âm và cột chồng vỡ. Chủng loại chỉ có hợp đồng mà không có tồn thì
    không sinh ra dòng nào — không có hàng thì không có gì để bán.
    """
    return {g: q - min(signed.get(g, 0.0), q) for g, q in stock.items() if q > 0}


def stock_series(date_from: str, date_to: str, group_by: str = "structure") -> dict[str, Any]:
    """Tồn kho Tập đoàn theo ngày, nhóm theo cơ cấu hợp đồng · chủng loại · khu vực.

    Mỗi ngày kèm độ phủ (`units_counted`/`units_expected`): thiếu đơn vị mà không nói ra thì người
    xem tưởng cột thấp là hàng bán được nhiều, trong khi thật ra là chưa ai nhập.

    ⚠ `total` LUÔN là tồn kho tổng, kể cả ở cách nhìn `free_grade` (nơi các cột chỉ là phần tự do) —
    dòng tổng dưới biểu đồ và tooltip phải nói đúng con số tồn, không đổi nghĩa theo cách xem.
    """
    if group_by not in GROUPS:
        group_by = "structure"
    snaps = _snapshots(date_from, date_to)
    meta = unit_report_rows.unit_meta()
    expected = len(meta)

    rows: list[dict[str, Any]] = []
    grade_totals: dict[str, float] = {}
    # Chỉ 2 cách nhìn cần hỏi hợp đồng (1 truy vấn / ngày) — 2 cách còn lại khỏi trả phí đó.
    needs_contracts = group_by in ("structure", "free_grade")
    for day, snap in snaps.items():
        by_company = {c: _warehoused(e["fields"]) for c, e in snap.items()}
        total = sum(sum(g.values()) for g in by_company.values())
        undelivered = (unit_daily_repo.contracts_on(day, list(snap))
                       if needs_contracts and snap else {})
        values: dict[str, float] = {}
        if group_by == "structure":
            signed = sum(min((undelivered.get(c) or {}).get("qty") or 0.0, sum(g.values()))
                         for c, g in by_company.items())
            values = {"signed": signed, "free": total - signed}
        elif group_by == "free_grade":
            for company, stock in by_company.items():
                signed_grades = (undelivered.get(company) or {}).get("by_grade") or {}
                for grade, q in _free_by_grade(stock, signed_grades).items():
                    values[grade] = values.get(grade, 0.0) + q
                    grade_totals[grade] = grade_totals.get(grade, 0.0) + q
        elif group_by == "grade":
            for g in by_company.values():
                for grade, q in g.items():
                    values[grade] = values.get(grade, 0.0) + q
                    grade_totals[grade] = grade_totals.get(grade, 0.0) + q
        else:
            for company, g in by_company.items():
                region = (meta.get(company) or {}).get("region") or NO_REGION
                values[region] = values.get(region, 0.0) + sum(g.values())
        rows.append({"as_of": day, "total": round(total, 3) if snap else None,
                     "units_counted": len(snap), "units_expected": expected,
                     "values": {k: round(v, 3) for k, v in values.items()}})

    if group_by in ("grade", "free_grade"):
        series = series_of(rows, grade_totals)
    elif group_by == "region":
        series = series_of(rows)
    else:
        series = [{"key": k, "label": lb} for k, lb in STRUCTURE_KEYS]

    return {"date_from": date_from, "date_to": date_to, "group_by": group_by,
            "start_floor": STOCK_START, "max_age_days": MAX_AGE_DAYS,
            "series": series, "rows": rows}
