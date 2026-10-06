"""Màn "Dashboard đơn vị" — thu mua · tiêu thụ · tồn kho của MỘT phạm vi (Tập đoàn / khu vực / đơn vị).

Không tự cộng lại số liệu: mọi con số lấy từ đúng các bảng thống kê đang chạy (`unit_report_*`,
`unit_series_stock`) với bộ lọc do `unit_dashboard_scope` dựng. Vì vậy dashboard của một khu vực
luôn khớp dòng khu vực đó ở màn "Chỉ số đơn vị", và các luật khó — giá BQ GIA QUYỀN, gộp đơn vị đã
sáp nhập, tồn kho không mượn số ngày khác — vẫn chỉ nằm một chỗ.

Chỉ tiêu năm (lũy kế từ 01/01) nằm riêng ở `unit_dashboard_targets`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.market_meta import PURCHASE_PRICE_UNIT
from app.services import unit_report_consumption as con
from app.services import unit_report_purchase as pur
from app.services import unit_report_rows as rows_mod
from app.services import unit_report_stock as st
from app.services import unit_series_stock as sst
from app.services.unit_scorecard import _latest_stock_day
from app.services.unit_series import days_between, window

#: Kỳ dài hơn ngần này thì biểu đồ diễn biến gộp theo THÁNG (cả năm vẽ theo ngày là hơn 250 cột).
MAX_DAILY_DAYS = 62
#: Ngày chốt tồn kho tự lấy quét lùi tối đa ngần này ngày (và không lùi quá từ-ngày của kỳ).
_AUTO_STOCK_LOOKBACK = 60

_PURCHASE_TOTALS = ("qty_latex", "qty_cup", "qty_lace", "qty_finished", "qty_material",
                    "qty_total", "price_latex_avg", "price_cup_avg", "price_lace_avg",
                    "price_finished_avg", "days", "no_purchase_days")
_PURCHASE_TREND = ("qty_latex", "qty_cup", "qty_lace", "qty_finished", "price_latex_avg")
#: Nguồn tiêu thụ tính theo từng dòng chủng loại (khai thác · thu mua · hàng hóa cao su).
_CON_SOURCES = ("qty_exploit", "qty_purchase", "qty_goods")
_CON_QTY = ("qty", "qty_long_term", "qty_spot", "qty_principle", "qty_unknown_type", "qty_export",
            "qty_domestic", "qty_internal", *_CON_SOURCES, "revenue_ty")
#: `bad_price_lines` = dòng bán nghi sai đơn vị tính (đơn giá vượt trần) — thẻ KPI Doanh thu đọc để
#: báo số đang bị đội lên, thay vì hiện 4.500 tỷ ảo như một con số thật (phản hồi 26/09/2026).
_CON_TOTALS = (*_CON_QTY, "avg_price_trieu", "lines", "days", "no_revenue_lines", "bad_price_lines")
_CON_BREAKDOWN = ("qty", "revenue_ty", "avg_price_trieu", "bad_price_lines")
_STOCK_TOTALS = ("not_warehoused", "warehoused", "total", "material", "signed_undelivered",
                 "tradable", "age_days", "dates")
_STOCK_BREAKDOWN = ("total", "signed_undelivered", "tradable", "material", "as_of", "age_days")


def bucket_of(date_from: str, date_to: str) -> str:
    days = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days + 1
    return "day" if days <= MAX_DAILY_DAYS else "month"


def _timeline(date_from: str, date_to: str, bucket: str, today: str) -> list[str]:
    """Mọi mốc (ngày hoặc "YYYY-MM") từ đầu kỳ tới min(cuối kỳ, hôm nay) — tương lai thì chưa có gì."""
    end = min(date_to, today)
    if end < date_from:
        return []
    days = days_between(date_from, end)
    return days if bucket == "day" else list(dict.fromkeys(d[:7] for d in days))


def _trend(rows: list[dict[str, Any]], keys: tuple[str, ...], date_from: str, date_to: str,
           bucket: str, today: str) -> list[dict[str, Any]]:
    """Chuỗi diễn biến ĐỦ mốc: bảng thống kê chỉ trả mốc có số, bỏ các mốc trống thì trục thời gian
    dồn lại (3 lần giao ngày 03 · 15 · 22 trông như 3 ngày liền) — mốc trống giữ ô None, không phải 0.
    Dòng ngoài khung (vd kỳ toàn tương lai) vẫn giữ để không mất số."""
    by_key = {r["key"]: {"as_of": r["key"], **_pick(r, keys)} for r in rows}
    empty = dict.fromkeys(keys)
    out = [by_key.pop(k, None) or {"as_of": k, **empty}
           for k in _timeline(date_from, date_to, bucket, today)]
    return sorted(out + list(by_key.values()), key=lambda r: r["as_of"])


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: row.get(k) for k in keys}


def _desc(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda r: -(r.get(key) or 0.0))


def _ordered(sc: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dòng theo chiều con, xếp đúng thứ tự khu vực/đơn vị admin đã sắp; dòng ngoài khung xuống cuối.

    Dòng ngoài khung (đơn vị chưa gán khu vực, đơn vị ngừng hoạt động còn số cũ) vẫn giữ lại để các
    cột cộng lại vẫn bằng tổng — bỏ đi là số của phạm vi tự hụt mà không ai biết vì sao.
    """
    by_key = {r["key"]: r for r in rows}
    head = [by_key.pop(k) for k in sc["children"] if k in by_key]
    return head + list(by_key.values())


def _data_warnings(warnings: list[str]) -> list[str]:
    """Cảnh báo về số liệu của KỲ. Bỏ lời nhắc về % kế hoạch: section kỳ không hiện % kế hoạch
    (so chỉ tiêu năm nằm ở phần Chỉ tiêu, lũy kế từ 01/01), để lại chỉ làm người đọc đi tìm."""
    return list(dict.fromkeys(w for w in warnings if "kế hoạch" not in w))


def purchase_block(sc: dict[str, Any], date_from: str, date_to: str, today: str) -> dict[str, Any]:
    f, child = sc["filters"], sc["child"]
    bucket = bucket_of(date_from, date_to)
    base = pur.purchase_report(date_from, date_to, group_by=child or "company", **f)
    trend = pur.purchase_report(date_from, date_to, group_by=bucket, **f)
    # Chủng loại CHỈ có ở thành phẩm mua ngoài — mủ nước/chén/dây khai theo tổng (luật 22/09/2026).
    fin = pur.purchase_report(date_from, date_to, materials="finished", group_by="grade", **f)
    return {
        "scope": sc["public"], "date_from": date_from, "date_to": date_to, "bucket": bucket,
        "totals": _pick(base["totals"], _PURCHASE_TOTALS),
        "price_units": {"latex": PURCHASE_PRICE_UNIT["purchase"],
                        "cup": PURCHASE_PRICE_UNIT["purchase_cup"],
                        "lace": PURCHASE_PRICE_UNIT["purchase_lace"], "finished": "triệu đ/tấn"},
        "trend": _trend(trend["rows"], _PURCHASE_TREND, date_from, date_to, bucket, today),
        "finished_by_grade": _desc([{"grade": r["key"], "qty": r["qty_finished"],
                                     "price_avg": r["price_finished_avg"]} for r in fin["rows"]],
                                   "qty"),
        "breakdown": [{"label": r["key"],
                       **_pick(r, ("qty_material", "qty_finished", "price_latex_avg"))}
                      for r in _ordered(sc, base["rows"])] if child else [],
        "warnings": _data_warnings(base["warnings"]),
    }


def consumption_block(sc: dict[str, Any], date_from: str, date_to: str,
                      today: str) -> dict[str, Any]:
    f, child = sc["filters"], sc["child"]
    bucket = bucket_of(date_from, date_to)
    base = con.consumption_report(date_from, date_to, group_by=child or "company", **f)
    trend = con.consumption_report(date_from, date_to, group_by=bucket, **f)
    grade = con.consumption_report(date_from, date_to, group_by="grade", **f)
    return {
        "scope": sc["public"], "date_from": date_from, "date_to": date_to, "bucket": bucket,
        "totals": _pick(base["totals"], _CON_TOTALS),
        "trend": _trend(trend["rows"], _CON_QTY, date_from, date_to, bucket, today),
        # Kèm sản lượng theo NGUỒN của từng chủng loại → bảng "tiêu thụ từ nguồn nào, loại nào".
        "by_grade": _desc([{"grade": r["key"],
                            **_pick(r, ("qty", "revenue_ty", "avg_price_trieu", *_CON_SOURCES))}
                           for r in grade["rows"]], "qty"),
        "breakdown": [{"label": r["key"], **_pick(r, _CON_BREAKDOWN)}
                      for r in _ordered(sc, base["rows"])] if child else [],
        "warnings": _data_warnings(base["warnings"]),
    }


def stock_day(sc: dict[str, Any], date_from: str, date_to: str, as_of: str | None,
              today: str) -> tuple[str, bool]:
    """Ngày chốt tồn kho → (ngày, có phải tự lấy không). Chọn tay thì giữ đúng ngày đó (≤ hôm nay).

    Để "Tự động": ngày CUỐI của biểu đồ diễn biến tồn kho cùng trang — cùng luật cắt đuôi
    `unit_series_stock.trim_pending` (bỏ các ngày cuối chưa đủ đơn vị khai), nên thẻ KPI, khối Tồn
    kho và biểu đồ luôn cùng một ngày. Trước 29/09/2026 lấy hôm nay, mà đơn vị được nhập tới 11:00
    hôm sau → sáng nào KPI Tập đoàn cũng tụt (29/09: 6.113 t của 11/63 đơn vị, ngày 28/09: 52.271 t).
    Một đơn vị: thêm ngày cuối có ẢNH CHỤP tồn — khai 0 cũng là số, mà biểu đồ không vẽ cột 0 tấn.
    """
    end = min(as_of or date_to, today)
    if as_of or sc["units"] == []:
        return end, not as_of
    rows = stock_series_block(sc, date_from, date_to, "warehouse", today)["rows"]
    last = max((r["as_of"] for r in rows if r["units_counted"]), default=None)
    if sc["public"]["scope"] == "unit" or not last:
        last = max(filter(None, (last, _last_snapshot_day(sc["units"], date_from, end))),
                   default=None)
    return last or end, True


def _last_snapshot_day(units: list[str] | None, date_from: str, end: str) -> str | None:
    """Ngày cuối trong [từ ngày, `end`] có ảnh chụp tồn kho — theo ĐÚNG luật lấy số của `stock_rows`
    (khai đúng ngày, hoặc tick "không phát sinh" thì giữ số lần khai trước).

    Không dùng "ngày khai gần nhất" (`_latest_stock_day`): nó lùi ra ngoài kỳ (VRG Oudomxay, kỳ
    tháng 9 ra 02/08) và bỏ qua cờ "không phát sinh" — Dầu Tiếng Lai Châu khai 30/08 rồi tick tới
    28/09 thì phải chốt 28/09 kèm "số cũ 29 ngày", không phải chốt 30/08 như số mới.
    """
    lo = max(date.fromisoformat(date_from),
             date.fromisoformat(end) - timedelta(days=_AUTO_STOCK_LOOKBACK))
    back = (date.fromisoformat(end) - lo).days
    if back < 0:
        return None
    snap = rows_mod.stock_rows(end, companies=units, all_days=True, days_back=back,
                               with_contracts=False)
    return max((r["as_of"] for r in snap["rows"] if r["as_of"] >= lo.isoformat()), default=None)


def stock_block(sc: dict[str, Any], as_of: str, auto: bool = False) -> dict[str, Any]:
    """Ảnh chụp tồn kho TẠI ngày chốt — số thời điểm, không cộng dồn theo kỳ.

    `auto` = ngày chốt do `stock_day` tự lấy (người dùng để "Tự động") — web ghi rõ điều đó.
    """
    f, child = sc["filters"], sc["child"]
    rep = st.stock_report(as_of, 0, group_by=child or "company", **f)
    totals, cov = rep["totals"], rep["coverage"]
    # Ngày chốt trống trơn trong phạm vi → mời sang ngày gần nhất CÓ số, không tự đổi ngày.
    hint = (_latest_stock_day(as_of, sc["units"])
            if not cov["units_counted"] and sc["units"] != [] else None)
    return {
        "scope": sc["public"], "as_of": as_of, "auto_as_of": auto,
        "totals": _pick(totals, _STOCK_TOTALS),
        "by_grade": _desc([{"grade": g, "qty": q} for g, q in (totals.get("by_grade") or {}).items()],
                          "qty"),
        "coverage": cov,
        "latest_stock_day": hint,
        "breakdown": [{"label": r["key"], **_pick(r, _STOCK_BREAKDOWN)}
                      for r in _ordered(sc, rep["rows"])] if child else [],
        # Cả phạm vi chưa ai khai ngày chốt → câu gợi ý ngày gần nhất đã nói đủ; bỏ cảnh báo liệt
        # kê từng đơn vị thiếu (toàn Tập đoàn là 60+ cái tên, che mất cả khối).
        "warnings": [] if hint else list(dict.fromkeys(rep["warnings"])),
    }


STOCK_VIEWS = ("warehouse", "grade", "structure", "free_grade")


def stock_series_block(sc: dict[str, Any], date_from: str, date_to: str, view: str,
                       today: str) -> dict[str, Any]:
    """Diễn biến tồn kho theo ngày của phạm vi — cùng chuỗi với Dashboard Tập đoàn, lọc đơn vị.

    Mốc `STOCK_START` chỉ áp cho Tập đoàn/khu vực (trước mốc đó quá ít đơn vị nhập để cộng thành
    số của cả nhóm); một đơn vị thì ngày nào đã khai là số thật của ngày đó.
    """
    floor = None if sc["public"]["scope"] == "unit" else sst.STOCK_START
    a, b = window(date_from, min(date_to, today), start_floor=floor)
    if sc["units"] == []:           # khu vực chưa có đơn vị nào → không có gì để vẽ
        return {"scope": sc["public"], "date_from": a, "date_to": b, "group_by": view,
                "start_floor": floor, "series": [], "rows": [], "pending": []}
    rep = sst.stock_series(a, b, view, companies=sc["units"])
    return {**rep, "scope": sc["public"], "start_floor": floor}
