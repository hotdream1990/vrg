"""Bảng SỐ LIỆU SẼ CHỐT của đơn vị — thứ đơn vị nhìn trước khi bấm xác nhận.

Yêu cầu 25/08/2026: *"trong cảnh báo về chốt số liệu cần hỗ trợ thông tin về các con số đến tại
thời điểm đó để đơn vị nắm được số liệu cần chốt là bao nhiêu, để confirm"*.

Nguồn số: dùng LẠI `unit_period_report` — đúng bộ chỉ tiêu Ban TTKD đọc ở *Báo cáo tổng hợp*, nên
con số đơn vị xác nhận ở đây và con số trên báo cáo là MỘT. Tự cộng lại một bộ khác là mầm lệch số.

Kỳ chốt = **từ sau lần chốt trước đến ngày chốt** (chưa chốt lần nào thì tính từ đầu năm của ngày
chốt). Riêng TỒN KHO là chỉ tiêu thời điểm — luôn là ảnh chụp tại ngày chốt, không phụ thuộc kỳ.

⚠ Tính cho NHIỀU đơn vị thì gọi `summary_many` (một lượt truy vấn cho cả danh sách). Quản trị
"khoá hộ" cả 70 đơn vị một lần: gọi `summary` trong vòng lặp là nhân 70 lần toàn bộ báo cáo kỳ.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import unit_daily_repo, unit_period_report, unit_report_status

#: Chỉ tiêu hiện trong bảng xác nhận — gọn để đơn vị đọc được trong một màn, không phải cả báo cáo.
PURCHASE_KEYS = ("latex_wet", "coagulum", "finished_qty", "total_purchase",
                 "price_latex_avg", "price_cup_avg", "no_purchase_days", "plan_tonnes", "pct_plan")
CONSUMPTION_KEYS = ("total_consumption", "export_total", "domestic_total", "internal_total",
                    "lt_total", "spot_total", "revenue_ty", "avg_sell_price")
STOCK_KEYS = ("stock_as_of", "stock_finished", "stock_not_warehoused", "stock_warehoused",
              "stock_material", "stock_finished_hd")

#: Số ngày thiếu hiện ra trong bảng xác nhận (mới nhất trước) — phần còn lại chỉ đếm.
MISSING_SHOWN = 10

#: ⚠ NGOẠI LỆ của biểu TỒN KHO (chốt với chủ dự án 26/08/2026): các đơn vị mới bắt đầu nộp tồn kho
#: từ ngày này, trước đó KHÔNG ai phải nộp nên không được tính là "còn thiếu". Không có mốc này thì
#: kỳ chốt đầu tiên (tính từ 01/01) báo hơn 200 ngày thiếu — toàn ngày đơn vị không có lỗi, đọc xong
#: chỉ tổ hoang mang rồi bỏ qua cả cảnh báo thật.
#: CHỈ ảnh hưởng phần đếm ngày thiếu; con số tồn kho là ảnh chụp THỜI ĐIỂM nên không liên quan.
STOCK_TRACKED_FROM = "2026-07-24"


def period_start(lock_date: str, prev_lock: str | None) -> str:
    """Ngày đầu kỳ chốt: hôm sau lần chốt trước, hoặc 01/01 của năm chứa ngày chốt."""
    if prev_lock and prev_lock < lock_date:
        return (date.fromisoformat(prev_lock) + timedelta(days=1)).isoformat()
    return f"{lock_date[:4]}-01-01"


def _rows_by_company(kind: str, companies: list[str], date_from: str,
                     date_to: str) -> dict[str, dict[str, Any]]:
    rep = unit_period_report.period_report(kind, date_from, date_to, companies=companies,
                                           split_merged=True)
    return {r["company"]: r for r in rep["rows"]}


def _missing_by_company(kind: str, companies: list[str], date_from: str,
                        date_to: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in companies}
    for m in unit_report_status.missing_cells(kind, date_from, date_to,
                                              companies=",".join(companies)):
        out.setdefault(m["company"], []).append(m["as_of"])
    return out


def summary_many(companies: list[str], lock_date: str,
                 prev_lock: str | None = None) -> dict[str, dict[str, Any]]:
    """Số liệu sẽ chốt của NHIỀU đơn vị trong một lượt: {đơn vị: bảng số liệu}."""
    if not companies:
        return {}
    date_from = period_start(lock_date, prev_lock)
    year = int(lock_date[:4])
    planned = unit_daily_repo.companies_with_purchase_plan(year)

    pur_rows = _rows_by_company("purchase", companies, date_from, lock_date)
    con_rows = _rows_by_company("consumption", companies, date_from, lock_date)
    miss_pur = _missing_by_company("purchase", companies, date_from, lock_date)
    # Tồn kho rà từ mốc bắt đầu thu thập (xem STOCK_TRACKED_FROM); kỳ chốt kết thúc trước mốc đó
    # thì không có gì để đòi.
    stock_from = max(date_from, STOCK_TRACKED_FROM)
    miss_con = (_missing_by_company("consumption", companies, stock_from, lock_date)
                if stock_from <= lock_date else {})

    out: dict[str, dict[str, Any]] = {}
    for company in companies:
        has_plan = company in planned
        pur = pur_rows.get(company, {}) if has_plan else {}
        con = con_rows.get(company, {})
        mp = miss_pur.get(company, []) if has_plan else []
        mc = miss_con.get(company, [])
        # CHỈ trả vài ngày gần nhất: kỳ chốt đầu tiên tính từ 01/01 nên đơn vị nhập thưa có thể
        # thiếu vài trăm ngày — đổ hết danh sách ra bảng xác nhận thì không ai đọc nổi. Con số cần
        # biết là "còn thiếu bao nhiêu"; danh sách chỉ để nhận ra mấy ngày cuối kỳ vừa quên.
        out[company] = {
            "company": company,
            "lock_date": lock_date,
            "date_from": date_from,
            "prev_lock_date": prev_lock,
            "has_purchase_plan": has_plan,
            "days_entered": {"purchase": pur.get("days") or 0,
                             "consumption": con.get("days") or 0},
            "purchase": {k: pur.get(k) for k in PURCHASE_KEYS},
            "consumption": {k: con.get(k) for k in CONSUMPTION_KEYS},
            "stock": {k: con.get(k) for k in STOCK_KEYS},
            "missing": {"purchase": mp[-MISSING_SHOWN:], "consumption": mc[-MISSING_SHOWN:]},
            "missing_counts": {"purchase": len(mp), "consumption": len(mc)},
            # Mốc bắt đầu rà của từng biểu — màn hình ghi rõ "chỉ tính từ ngày…" cho biểu tồn kho,
            # nếu không người đọc tưởng những ngày trước đó đã nộp đủ.
            "missing_from": {"purchase": date_from, "consumption": stock_from},
            "missing_total": len(mp) + len(mc),
        }
    return out


def summary(company: str, lock_date: str, prev_lock: str | None = None) -> dict[str, Any]:
    """Số liệu 1 đơn vị sẽ chốt: thu mua · tiêu thụ (cộng dồn trong kỳ) · tồn kho (tại ngày chốt).

    Kèm `missing` = những ngày trong kỳ đơn vị CHƯA nộp biểu — để đơn vị không chốt nhầm lúc còn
    thiếu số (chốt xong là hết tự sửa). Không chặn: thiếu ngày vẫn được chốt, chỉ cảnh báo.
    """
    return summary_many([company], lock_date, prev_lock).get(company, {})
