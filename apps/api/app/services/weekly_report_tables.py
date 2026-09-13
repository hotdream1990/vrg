"""Bảng số Báo cáo tuần v2 — III.1 sàn quốc tế, III.2 giao ngay, tỷ giá — cho kỳ gộp 1–3 tuần.

Mỗi dòng có `values` = TB tuần USD/tấn theo từng cột `weeks` (cột 0 = tuần mốc) + `changes`/
`changes_pct` theo từng cặp tuần liền nhau. Đọc DB đúng MỘT lần cho cả kỳ: `price_sheet.build_sheet`
cho sàn + tỷ giá, `price_repo.history` mỗi chủng loại giao ngay một lần.

⚠ GIÁ 0 = No Trading (quy ước `bulletin/convert.py`) — KHÔNG phải mức giá: loại khỏi trung bình,
cao/thấp và tính là "không có giá" ở ghi chú dưới bảng. (v1 để lọt số 0 của lưới sàn vào trung bình
— vd SGX 10/08/2026 kéo TB tuần 33 xuống 2.189,6.)
"""

from __future__ import annotations

import statistics
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.market_meta import SHEET_GROUPS
from app.core.paths import bulletin_dir
from app.services import price_repo, price_sheet

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import is_no_trading, r2  # noqa: E402

Series = dict[str, Any]  # ngày ISO → giá

# III.1 — (nhãn sàn, chủng loại hiển thị, key cột trong build_sheet)
EXCHANGE_MAP = [
    ("OSE", "RSS3", "OSE:RSS3"),
    ("SHANGHAI", "RSS3", "SHANGHAI:RSS3"),
    ("SGX", "RSS3", "SGX:RSS3"),
    ("SGX", "TSR20", "SGX:TSR20"),
    ("MRE", "SMR CV", "MRB:SMRCV"),
    ("MRE", "SMR20", "MRB:SMR20"),
    ("MRE", "LATEX", "MRB:LATEX"),
]
# III.2 — (chủng loại hiển thị, grade nguồn reuters)
PHYSICAL_MAP = [
    ("RSS3", "RSS3"),
    ("STR20", "STR20"),
    ("SMR20", "SMR20"),
    ("LATEX", "Thai Latex 60% (Bulk)"),
]
# Tỷ giá TB tuần — (cặp, số lẻ). JPY/THB 2 số lẻ; CNY/MYR biến động nhỏ nên giữ 4.
FX_ROWS = [("USD/JPY", 2), ("USD/CNY", 4), ("USD/MYR", 4), ("USD/THB", 2)]
# Giá nội tệ kèm cao/thấp (bám mẫu tuần 35–36). MRE không ghi nội tệ.
NATIVE_UNITS = {
    "OSE:RSS3": "JPY/kg", "SHANGHAI:RSS3": "CNY/tấn",
    "SGX:RSS3": "US cent/kg", "SGX:TSR20": "US cent/kg",
}
# Cặp tỷ giá quy đổi USD của từng cột lưới sàn (None = sàn yết sẵn USD/US cent) — để ghi chú
# "thiếu tỷ giá USD/JPY" đúng cặp khi ô có giá nội tệ mà chưa quy đổi được.
FX_PAIR_OF = {c["key"]: c.get("fx_pair") for g in SHEET_GROUPS for c in g["cols"]}
# SGX lưu fact_price bằng US cents/kg nhưng lưới chỉ giữ USD/tấn (= cents × 10, xem
# market_meta SHEET_GROUPS edit.scale 0.1) → nội tệ = USD/tấn × 0,1.
_SGX_CENTS_PER_USD_TONNE = 0.1


def is_price(v: Any) -> bool:
    """Có phải một mức giá thật (không thiếu, không phải phiên No Trading)."""
    return v is not None and not is_no_trading(v)


def round_half_up(x: float, digits: int) -> float:
    """Làm tròn nửa LÊN `digits` số lẻ (round() của Python làm tròn về số chẵn)."""
    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def week_avgs(series: Series, weeks: list[dict[str, Any]], digits: int = 1) -> list[float | None]:
    """TB từng tuần (Thứ 2–6) của chuỗi ngày → giá; bỏ ô thiếu và giá 0."""
    out: list[float | None] = []
    for w in weeks:
        xs = [v for d, v in series.items() if w["mon"] <= d <= w["fri"] and is_price(v)]
        out.append(round_half_up(statistics.mean(xs), digits) if xs else None)
    return out


def pair_changes(values: list[float | None], digits: int = 1) -> tuple[list, list]:
    """+/- (làm tròn `digits`) và % (2 số lẻ) cho từng cặp tuần liền nhau — tính trên số đã làm tròn."""
    changes: list[float | None] = []
    pcts: list[float | None] = []
    for a, b in zip(values, values[1:]):
        both = a is not None and b is not None
        changes.append(round_half_up(b - a, digits) if both else None)
        pcts.append(r2((b - a) / a * 100) if both and a else None)
    return changes, pcts


def series_row(exchange: str | None, grade: str, values: list[float | None]) -> dict[str, Any]:
    """Dòng bảng nhiều tuần; prev/curr/change_* = cặp CUỐI (tương thích v1)."""
    changes, pcts = pair_changes(values)
    return {
        "exchange": exchange, "grade": grade,
        "values": values, "changes": changes, "changes_pct": pcts,
        "prev": values[-2] if len(values) > 1 else None,
        "curr": values[-1] if values else None,
        "change_abs": changes[-1] if changes else None,
        "change_pct": pcts[-1] if pcts else None,
    }


def native_of(key: str, cell: dict[str, Any]) -> float | None:
    """Giá nội tệ của 1 ô lưới sàn (None nếu sàn không ghi nội tệ hoặc không có giá)."""
    if key not in NATIVE_UNITS:
        return None
    if key.startswith("SGX:"):
        usd = cell.get("usd")
        return r2(usd * _SGX_CENTS_PER_USD_TONNE) if is_price(usd) else None
    v = cell.get("native")
    return float(v) if is_price(v) else None


def load_market(per: dict[str, Any]) -> dict[str, Any]:
    """Đọc giá cả kỳ [date_from, date_to] (gồm tuần mốc) — 1 lần build_sheet + 1 history/grade.

    Trả {exchange: {key: {ngày: ô lưới}}, physical: {chủng loại: {ngày: USD/tấn}}, fx: {cặp: {ngày: tỷ giá}}}.
    Tỷ giá chỉ có ở ngày có giá sàn và ĐÚNG ngày đó (build_sheet không carry-forward).
    """
    d0, d1 = per["date_from"], per["date_to"]
    rows = price_sheet.build_sheet(date_from=d0, date_to=d1)["rows"]
    exchange = {key: {r["as_of"]: r["cells"].get(key, {}) for r in rows} for _, _, key in EXCHANGE_MAP}
    fx = {pair: {r["as_of"]: r["fx"].get(pair) for r in rows} for pair, _ in FX_ROWS}
    days = max((date.today() - date.fromisoformat(d0)).days + 3, 14)
    physical: dict[str, Series] = {}
    for disp, src in PHYSICAL_MAP:
        pts = price_repo.history("reuters", src, days=days)  # đã bỏ giá 0
        physical[disp] = {str(p["as_of"]): float(p["price"]) for p in pts
                          if d0 <= str(p["as_of"]) <= d1}
    return {"exchange": exchange, "physical": physical, "fx": fx}


def usd_series(cells: dict[str, dict[str, Any]]) -> Series:
    return {d: c.get("usd") for d, c in cells.items()}


def exchange_rows(market: dict[str, Any], weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [series_row(exc, g, week_avgs(usd_series(market["exchange"][key]), weeks))
            for exc, g, key in EXCHANGE_MAP]


def physical_rows(market: dict[str, Any], weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [series_row(None, disp, week_avgs(market["physical"][disp], weeks))
            for disp, _ in PHYSICAL_MAP]


def fx_rows(market: dict[str, Any], weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for pair, digits in FX_ROWS:
        values = week_avgs(market["fx"][pair], weeks, digits)
        changes, pcts = pair_changes(values, digits)
        out.append({"pair": pair, "values": values, "changes": changes, "changes_pct": pcts})
    return out
