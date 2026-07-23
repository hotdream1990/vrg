"""Service Báo cáo phân tích thị trường TUẦN.

Bảng số liệu tự dựng từ giá (TB tuần USD/tấn — reuse `price_sheet.build_sheet` cho III.1,
`price_repo.history` cho III.2, `price_repo.purchase_sheet` cho III.3). Narrative (các phần
viết) lưu bền trong bảng `weekly_report`; bảng luôn dựng lại từ dữ liệu. Xuất PDF qua package
`services/weekly_report`.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.paths import bulletin_dir, data_dir, services_dir
from app.services import price_repo, price_sheet

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import r0, r1, r2  # noqa: E402 - 1 nguồn làm tròn nửa-lên dùng chung

# III.1 — (nhãn sàn, chủng loại hiển thị, key trong build_sheet)
_EXCHANGE_MAP = [
    ("OSE", "RSS3", "OSE:RSS3"),
    ("SHANGHAI", "RSS3", "SHANGHAI:RSS3"),
    ("SGX", "RSS3", "SGX:RSS3"),
    ("SGX", "TSR20", "SGX:TSR20"),
    ("MRE", "SMR CV", "MRB:SMRCV"),
    ("MRE", "SMR20", "MRB:SMR20"),
    ("MRE", "LATEX", "MRB:LATEX"),
]
# III.2 — (chủng loại hiển thị, grade nguồn reuters)
_PHYSICAL_MAP = [
    ("RSS3", "RSS3"),
    ("STR20", "STR20"),
    ("SMR20", "SMR20"),
    ("LATEX", "Thai Latex 60% (Bulk)"),
]
_MACRO_TITLES = [
    "1. Thị trường Năng lượng và giá cao su tổng hợp (Butadien):",
    "2. Cung – Cầu cơ bản:",
    "3. Tỷ giá và Tài chính Nhật Bản:",
    "4. Các thông tin kinh tế Trung Quốc và dữ liệu khác:",
]

_MONTHS = None  # (không cần locale)


# ── Tuần ──
def week_key_for(d: date) -> str:
    """Ngày Thứ 2 (ISO) của tuần chứa `d` — dùng làm khóa tuần."""
    return (d - timedelta(days=d.weekday())).isoformat()


def _monfri(week_key: str) -> tuple[date, date]:
    mon = date.fromisoformat(week_key)
    return mon, mon + timedelta(days=4)


def _range_label(mon: date, fri: date, with_year: bool = False) -> str:
    if mon.month == fri.month:
        s = f"{mon.day}-{fri.day}/{fri.month}"
    else:
        s = f"{mon.day}/{mon.month}-{fri.day}/{fri.month}"
    return f"{s}/{fri.year}" if with_year else s


def _col_label(no: int, mon: date, fri: date) -> str:
    return f"Tuần {no} ({mon.day}/{mon.month} - {fri.day}/{fri.month})"


def _meta(week_key: str) -> dict[str, Any]:
    mon, fri = _monfri(week_key)
    week_no, year = mon.isocalendar()[1], mon.isocalendar()[0]
    pmon, pfri = mon - timedelta(days=7), fri - timedelta(days=7)
    nmon = mon + timedelta(days=7)
    # Tuần trước/sau lấy CẢ số tuần lẫn năm qua isocalendar (chống lỗi cuối/đầu năm ISO,
    # vd tuần 53/2026 → tuần kế là 1/2027, không phải 54/2026).
    p_iso, n_iso = pmon.isocalendar(), nmon.isocalendar()
    return {
        "week_key": week_key, "week_no": week_no, "year": year,
        "date_range": _range_label(mon, fri, with_year=True),
        "prev_week_no": p_iso[1], "prev_year": p_iso[0],
        "next_week_no": n_iso[1], "next_year": n_iso[0],
        "prev_col_label": _col_label(p_iso[1], pmon, pfri),
        "curr_col_label": _col_label(week_no, mon, fri),
        "_mon": mon, "_fri": fri, "_pmon": pmon, "_pfri": pfri,
    }


def _avg(vals: list[float | None]) -> float | None:
    """Bình quân tuần — làm tròn nửa LÊN (round() của Python làm tròn về số CHẴN: bình quân
    4 phiên = 2579,45 ra 2579,4 thay vì 2579,5, tức luôn thiệt xuống ở đuôi ,5)."""
    xs = [v for v in vals if v is not None]
    return r1(statistics.mean(xs)) if xs else None


def _row(exchange: str | None, grade: str, prev: float | None, curr: float | None) -> dict[str, Any]:
    change_abs = r1(curr - prev) if (prev is not None and curr is not None) else None
    change_pct = (r2((curr - prev) / prev * 100)
                  if (prev is not None and curr is not None and prev) else None)
    return {"exchange": exchange, "grade": grade, "prev": prev, "curr": curr,
            "change_abs": change_abs, "change_pct": change_pct}


# ── III.1 — sàn quốc tế (TB tuần) ──
def _exchange_rows(m: dict[str, Any]) -> list[dict[str, Any]]:
    days = (date.today() - m["_pmon"]).days + 3
    sheet = price_sheet.build_sheet(days=max(days, 14),
                                    date_from=m["_pmon"].isoformat(), date_to=m["_fri"].isoformat())
    rows = sheet["rows"]
    p0, p1 = m["_pmon"].isoformat(), m["_pfri"].isoformat()
    c0, c1 = m["_mon"].isoformat(), m["_fri"].isoformat()

    def week_avg(key: str, a: str, b: str) -> float | None:
        return _avg([r["cells"].get(key, {}).get("usd") for r in rows if a <= r["as_of"] <= b])

    return [_row(exc, g, week_avg(key, p0, p1), week_avg(key, c0, c1))
            for exc, g, key in _EXCHANGE_MAP]


# ── III.2 — giao ngay reuters (TB tuần) ──
def _physical_rows(m: dict[str, Any]) -> list[dict[str, Any]]:
    days = (date.today() - m["_pmon"]).days + 3
    p0, p1 = m["_pmon"].isoformat(), m["_pfri"].isoformat()
    c0, c1 = m["_mon"].isoformat(), m["_fri"].isoformat()
    out = []
    for disp, src_grade in _PHYSICAL_MAP:
        pts = price_repo.history("reuters", src_grade, days=max(days, 14))
        by = {str(p["as_of"]): float(p["price"]) for p in pts}
        prev = _avg([v for d, v in by.items() if p0 <= d <= p1])
        curr = _avg([v for d, v in by.items() if c0 <= d <= c1])
        out.append(_row(None, disp, prev, curr))
    return out


# ── III.3 — mủ nước (biên độ min–max tuần, đã loại outlier) ──
# Đơn vị nhập lệch hẳn khỏi nhóm (nhập nhầm) làm sai biên độ tuần → loại theo trung vị tuần.
_LATEX_OUTLIER_LO = 0.85   # < 85% trung vị tuần → loại
_LATEX_OUTLIER_HI = 1.15   # > 115% trung vị tuần → loại (chặn cả nhập nhầm cao bất thường)


def _core_range(xs: list[float]) -> tuple[int, int] | None:
    """Min–max 'vùng lõi' giá mủ nước trong tuần, bỏ đơn vị lệch hẳn khỏi trung vị."""
    if not xs:
        return None
    if len(xs) < 3:                                  # quá ít điểm → không đủ cơ sở lọc
        return r0(min(xs)), r0(max(xs))
    med = statistics.median(xs)
    core = [v for v in xs if _LATEX_OUTLIER_LO * med <= v <= _LATEX_OUTLIER_HI * med] or xs
    return r0(min(core)), r0(max(core))


def _latex_band(m: dict[str, Any]) -> dict[str, str | None]:
    sheet = price_repo.purchase_sheet(m["_pmon"].isoformat(), m["_fri"].isoformat())
    vals = sheet.get("values", {})
    p0, p1 = m["_pmon"].isoformat(), m["_pfri"].isoformat()
    c0, c1 = m["_mon"].isoformat(), m["_fri"].isoformat()

    def band(a: str, b: str) -> tuple[int, int] | None:
        xs = [pv for dmap in vals.values() for d, pv in dmap.items()
              if pv is not None and a <= d <= b]
        return _core_range(xs)

    pb, cb = band(p0, p1), band(c0, c1)
    prev = f"{pb[0]} – {pb[1]}" if pb else None
    curr = f"{cb[0]} - {cb[1]}" if cb else None
    change = None
    if pb and cb:
        dmin, dmax = cb[0] - pb[0], cb[1] - pb[1]
        change = f"{dmin:+d} /{dmax:+d}".replace("+0", "0")
    return {"latex_prev": prev, "latex_curr": curr, "latex_change": change}


# ── Cao/Thấp nhất tuần + tỷ giá (TỪ DATA — chống AI bịa số đỉnh/đáy) ──
def _ddmm(iso: str) -> str:
    return f"{int(iso[8:10])}/{int(iso[5:7])}"


_FX_FOR_CONTEXT = ["USD/JPY", "USD/CNY", "USD/MYR"]


def weekly_stats(week_key: str) -> dict[str, Any]:
    """Đỉnh/đáy tuần (USD/tấn) + ngày cho từng sàn & giao ngay + tỷ giá TB tuần, TÍNH TỪ DATA."""
    m = _meta(week_key)
    days = max((date.today() - m["_pmon"]).days + 3, 14)
    c0, c1 = m["_mon"].isoformat(), m["_fri"].isoformat()
    sheet = price_sheet.build_sheet(days=days, date_from=m["_pmon"].isoformat(), date_to=m["_fri"].isoformat())
    rows = [r for r in sheet["rows"] if c0 <= r["as_of"] <= c1]

    def hl(pairs: list[tuple[str, float | None]]) -> dict[str, Any] | None:
        pairs = [(d, v) for d, v in pairs if v is not None]
        if not pairs:
            return None
        hi, lo = max(pairs, key=lambda x: x[1]), min(pairs, key=lambda x: x[1])
        return {"high": r1(hi[1]), "high_date": _ddmm(hi[0]),
                "low": r1(lo[1]), "low_date": _ddmm(lo[0])}

    exch = {}
    for exc, g, key in _EXCHANGE_MAP:
        s = hl([(r["as_of"], r["cells"].get(key, {}).get("usd")) for r in rows])
        if s:
            exch[f"{exc} {g}"] = s
    phys = {}
    for disp, src in _PHYSICAL_MAP:
        pts = price_repo.history("reuters", src, days=days)
        s = hl([(str(p["as_of"]), float(p["price"])) for p in pts if c0 <= str(p["as_of"]) <= c1])
        if s:
            phys[disp] = s
    fx = {p: r2(a) for p in _FX_FOR_CONTEXT if (a := _avg([r["fx"].get(p) for r in rows])) is not None}
    return {"exchange": exch, "physical": phys, "fx": fx}


# ── Draft (narrative) ──
def _load_narrative(week_key: str) -> dict[str, Any]:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM weekly_report WHERE week_key = :k"),
                         {"k": week_key}).mappings().first()
    if not row:
        return {}
    p = row["payload"]
    return p if isinstance(p, dict) else json.loads(p)


def _default_macro() -> list[dict[str, Any]]:
    return [{"title": t, "bullets": []} for t in _MACRO_TITLES]


def build_report(week_key: str) -> dict[str, Any]:
    """Dựng báo cáo tuần: bảng auto từ giá + narrative từ draft (seed macro/III.3 nếu trống)."""
    m = _meta(week_key)
    band = _latex_band(m)
    nar = _load_narrative(week_key)

    macro = nar.get("macro") or _default_macro()
    narrative = {
        "summary_prev": nar.get("summary_prev", []),
        "movement": nar.get("movement", []),
        "exchange_notes": nar.get("exchange_notes", []),
        "physical_notes": nar.get("physical_notes", []),
        "latex_notes": nar.get("latex_notes", []),
        "macro": macro,
        "forecast": nar.get("forecast", []),
        "conclusion": nar.get("conclusion", []),
        # override biên độ III.3 (nếu người dùng đã sửa) — else seed từ giá
        "latex_prev": nar.get("latex_prev") or band["latex_prev"],
        "latex_curr": nar.get("latex_curr") or band["latex_curr"],
        "latex_change": nar.get("latex_change") or band["latex_change"],
    }
    return {
        "week_key": m["week_key"], "week_no": m["week_no"], "year": m["year"],
        "date_range": m["date_range"], "prev_week_no": m["prev_week_no"],
        "prev_year": m["prev_year"], "next_week_no": m["next_week_no"], "next_year": m["next_year"],
        "prev_col_label": m["prev_col_label"], "curr_col_label": m["curr_col_label"],
        "exchange_rows": _exchange_rows(m),
        "physical_rows": _physical_rows(m),
        "latex_prev": narrative["latex_prev"], "latex_curr": narrative["latex_curr"],
        "latex_change": narrative["latex_change"],
        "narrative": narrative,
    }


def save_narrative(week_key: str, narrative: dict[str, Any]) -> dict[str, Any]:
    """Lưu bền narrative (+ override III.3) rồi trả báo cáo dựng lại."""
    ensure_schema()
    with session_scope() as db:
        db.execute(text("""
            INSERT INTO weekly_report (week_key, payload) VALUES (:k, CAST(:p AS jsonb))
            ON CONFLICT (week_key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
        """), {"k": week_key, "p": json.dumps(narrative, ensure_ascii=False)})
    return build_report(week_key)


def list_reports() -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT week_key, updated_at FROM weekly_report ORDER BY week_key DESC"
        )).mappings().all()
    out = []
    for r in rows:
        m = _meta(str(r["week_key"]))
        out.append({"week_key": m["week_key"], "week_no": m["week_no"], "year": m["year"],
                    "label": f"Tuần {m['week_no']}/{m['year']} ({m['date_range']})",
                    "updated": str(r["updated_at"]) if r["updated_at"] else None})
    return out


def delete_report(week_key: str) -> bool:
    ensure_schema()
    with session_scope() as db:
        res = db.execute(text("DELETE FROM weekly_report WHERE week_key = :k"), {"k": week_key})
        return res.rowcount > 0


# ── Xuất PDF ──
def _pdf_pkg():
    wr = str(services_dir() / "weekly_report")
    if wr not in sys.path:
        sys.path.insert(0, wr)
    from weekly import models, pdf_export  # noqa: E402
    return models, pdf_export


def _assets() -> dict[str, str]:
    wa = data_dir() / "weekly-report-assets"
    ba = data_dir() / "bulletin-assets"
    return {
        "cover-front": str(wa / "cover-front.jpg"),
        "cover-back": str(wa / "cover-back.jpg"),
        "header-banner": str(ba / "header-banner.png"),
        "footer-banner": str(ba / "footer-banner.png"),
        "logo-vrg": str(ba / "logo-vrg.png"),
    }


def _to_pdf_data(rep: dict[str, Any]):
    models, _ = _pdf_pkg()
    nar = rep["narrative"]
    ex = [models.ExchangeWeekRow(r["exchange"], r["grade"], r["prev"], r["curr"])
          for r in rep["exchange_rows"]]
    ph = [models.PhysicalWeekRow(r["grade"], r["prev"], r["curr"]) for r in rep["physical_rows"]]
    macro = [models.MacroSection(s["title"], s.get("bullets", [])) for s in nar["macro"]]
    return models.WeeklyReportData(
        week_no=rep["week_no"], year=rep["year"], date_range=rep["date_range"],
        prev_week_no=rep["prev_week_no"], prev_year=rep["prev_year"],
        next_week_no=rep["next_week_no"], next_year=rep["next_year"],
        prev_col_label=rep["prev_col_label"], curr_col_label=rep["curr_col_label"],
        summary_prev=nar["summary_prev"], movement=nar["movement"],
        exchange_rows=ex, exchange_notes=nar["exchange_notes"],
        physical_rows=ph, physical_notes=nar["physical_notes"],
        latex_prev=rep["latex_prev"], latex_curr=rep["latex_curr"],
        latex_change=rep["latex_change"], latex_notes=nar["latex_notes"],
        macro=macro, forecast=nar["forecast"], conclusion=nar["conclusion"],
    )


def generate_pdf(week_key: str):
    """Xuất PDF báo cáo tuần → đường dẫn file trong data/weekly-reports/."""
    _, pdf_export = _pdf_pkg()
    rep = build_report(week_key)
    data = _to_pdf_data(rep)
    out = data_dir() / "weekly-reports" / f"Bao-cao-tuan-{rep['week_no']:02d}-{rep['year']}.pdf"
    return pdf_export.generate_pdf(data, _assets(), out)
