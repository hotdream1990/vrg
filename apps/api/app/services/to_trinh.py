"""Sinh dữ liệu TỜ TRÌNH giá sàn từ engine gợi ý + dữ liệu thị trường.

Khối 3 (đề xuất) lấy từ [floor_suggest.suggest]; khối 1-2 (settlement/physical) từ fact_price
quy đổi USD/T. GIỮ ĐÚNG THỨ TỰ chủng loại cố định — KHÔNG sort (xem to-trinh-gia-san-format).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import VRG_DOMESTIC_ONLY_GRADES
from app.services import floor_suggest as fs

# Thứ tự CỐ ĐỊNH (không sort): (tên tờ trình, tên hệ thống trong vrg_floor_price | None)
TT_GRADES = [("CV50", "SVR CV 50"), ("CV60", "SVR CV60"), ("SVRL", "SVR L"), ("SVR 3L Mix", "SVR 3L Mix"),
             ("SVR 3L", "SVR 3L"), ("5S", "SVR 5S"), ("SVR5", "SVR 5"), ("SVR10 Mix", "SVR 10 Mix"),
             ("SVR10", "SVR 10 / CSR 10"), ("SVR20", "SVR 20 / CSR 20"), ("RSS3", "RSS 3"), ("RSS1", "RSS 1"),
             ("Latex", "LATEX"), ("SkimBlock", "Skim Block")]
# Khối 1 settlement: (source, grade nguồn, SÀN hiển thị, grade hiển thị)
SETTLE = [("tocom", "RSS3", "OSE", "RSS3"), ("shfe", "RU", "SHANGHAI", "RSS3"),
          ("sgx", "RSS3", "SGX", "RSS3"), ("sgx", "TSR20", "SGX", "TSR20"),
          ("lgm", "SMRCV", "MRE", "SMRCV"), ("lgm", "SMR20", "MRE", "SMR20"), ("lgm", "LATEX", "MRE", "LATEX")]
PHYS = ["RSS3", "STR20", "SMR20", "SIR20", "Thai Latex 60% (Bulk)", "Thai Latex 60% (Drums)"]
SAN_FULL = {"OSE": "Sàn OSE (Nhật Bản)", "SHANGHAI": "Sàn SHANGHAI (Trung Quốc)",
            "SGX": "Sàn SGX (Singapore)", "MRE": "Sàn MRE (Malaysia)"}
_STALE_DAYS = 45  # physical cũ hơn ngần này so với ngày so sánh ⇒ coi như chưa cập nhật


def vn(n: float | int | None) -> str:
    """Định dạng số kiểu VN: 62400000 -> '62.400.000'."""
    return "—" if n is None else f"{round(n):,}".replace(",", ".")


_PLAUSIBLE_MAX = 6000  # USD/T — chặn giá trị phi lý (vd lgm LATEX lưu Sen/kg thô chưa quy đổi)


def _usd_t(price: float | None, unit: str | None, fx: dict) -> int | None:
    if price is None:
        return None
    v: int | None = None
    if unit == "US cents/kg":
        v = round(price * 10)
    elif unit == "USD/tonne":
        v = round(price)
    elif unit == "CNY/tonne":
        r = fx.get("USD/CNY")
        v = round(price / r) if r else None
    elif unit == "JPY/kg":
        r = fx.get("USD/JPY")
        v = round(price * 1000 / r) if r else None
    return None if (v is None or v > _PLAUSIBLE_MAX) else v


def _at(db, source: str, grade: str, d):
    return db.execute(text("SELECT price, unit, as_of FROM fact_price WHERE source=:s AND grade=:g "
                           "AND as_of<=:d ORDER BY as_of DESC LIMIT 1"), {"s": source, "g": grade, "d": d}).first()


def _fx_at(db, d) -> dict:
    out = {}
    for cur in ("USD/CNY", "USD/JPY"):
        r = db.execute(text("SELECT price FROM fact_price WHERE source='fx' AND grade=:g AND as_of<=:d "
                            "ORDER BY as_of DESC LIMIT 1"), {"g": cur, "d": d}).first()
        if r:
            out[cur] = r[0]
    return out


def _row(prev, curr) -> dict:
    d = (curr - prev) if (prev is not None and curr is not None) else None
    pct = (round(d / prev * 100, 1) if (d is not None and prev) else None)
    return {"prev": prev, "curr": curr, "d_abs": d, "d_pct": pct}


def _settlement(db, t2, t1) -> list[dict]:
    fx1, fx2 = _fx_at(db, t1), _fx_at(db, t2)
    out = []
    for src, g, san, disp in SETTLE:
        r1, r2 = _at(db, src, g, t1), _at(db, src, g, t2)
        v1 = _usd_t(r1[0], r1[1], fx1) if r1 else None
        v2 = _usd_t(r2[0], r2[1], fx2) if r2 else None
        out.append({"san": san, "grade": disp, **_row(v2, v1)})
    return out


def _physical(db, t2, t1) -> list[dict]:
    out = []
    for g in PHYS:
        def val(r, ref):
            return round(r[0]) if (r and (ref - r[2]).days <= _STALE_DAYS) else None
        v1 = val(_at(db, "reuters", g, t1), t1)
        v2 = val(_at(db, "reuters", g, t2), t2)
        out.append({"grade": g, **_row(v2, v1)})
    return out


def _proposal(db, sug: dict, prev_as_of) -> list[dict]:
    # Trị dự báo từ engine theo grade: FOB USD/T (grade thường) hoặc VNĐ/T (grade chỉ-nội-địa).
    sug_val = {it["grade"]: it["suggested"] for it in sug["items"]}
    prev = {}
    if prev_as_of:
        for g, f, v in db.execute(text("SELECT grade, fob_usd, domestic_vnd FROM vrg_floor_price WHERE as_of=:d"),
                                  {"d": prev_as_of}).all():
            prev[g] = (f, v)
    out = []
    for tt, sysg in TT_GRADES:
        pf, pv = prev.get(sysg, (None, None)) if sysg else (None, None)
        if sysg in VRG_DOMESTIC_ONLY_GRADES:
            # Grade chỉ-nội-địa (SkimBlock): engine dự báo thẳng VNĐ/T, không có FOB.
            raw = sug_val.get(sysg)
            vnd = round(raw / 50000) * 50000 if raw is not None else (round(pv) if pv else None)
            vnd_d = round(vnd - pv) if (vnd is not None and pv is not None and raw is not None) else None
            out.append({"grade": tt, "fob": None, "fob_delta": None, "vnd": vnd, "vnd_delta": vnd_d})
            continue
        fob = sug_val.get(sysg) if sysg else None
        fob_d = round(fob - pf) if (fob is not None and pf) else None
        vnd = round(pv * fob / pf / 50000) * 50000 if (fob and pf and pv) else (round(pv) if pv else None)
        vnd_d = round(vnd - pv) if (vnd is not None and pv is not None and fob_d) else None
        out.append({"grade": tt, "fob": fob, "fob_delta": fob_d, "vnd": vnd, "vnd_delta": vnd_d})
    return out


def _narrative(settlement: list[dict], physical: list[dict]) -> dict:
    n1 = ["- Thị trường cao su kỳ hạn biến động, các sàn có sự phân hóa giữa các chủng loại."]
    by_san: dict[str, list] = {}
    for r in settlement:
        by_san.setdefault(r["san"], []).append(r)
    for san, rs in by_san.items():
        parts = []
        for r in rs:
            if r["curr"] is None:
                continue
            if r["d_abs"] is None:
                parts.append(f"{r['grade']} ở mức {vn(r['curr'])} USD/T")
            else:
                dirn = "tăng" if r["d_abs"] > 0 else ("giảm" if r["d_abs"] < 0 else "đi ngang")
                parts.append(f"{r['grade']} {dirn} {abs(r['d_abs'])} USD/T ({vn(r['curr'])}, {r['d_pct']:+}%)")
        if parts:
            n1.append(f"- {SAN_FULL[san]}: " + "; ".join(parts) + ".")
    has_phys = any(r["curr"] is not None for r in physical)
    n2 = ["- Thị trường cao su vật chất phân hóa nhu cầu giữa các chủng loại."
          if has_phys else "- Dữ liệu giá vật chất chưa cập nhật cho kỳ này (bổ sung thủ công)."]
    n2.append("- Tồn kho Tập đoàn: (cập nhật thủ công).")
    return {"n1": n1, "n2": n2}


def build(as_of: str, model: str = "v1") -> dict[str, Any]:
    """Gom toàn bộ dữ liệu 4 khối tờ trình cho 1 lần ban hành (as_of)."""
    ensure_schema()
    sug = fs.suggest(as_of, model, backtest=True)
    if sug.get("error"):
        return {"error": sug["error"], "as_of": as_of}
    year = int(as_of[:4])
    with session_scope() as db:
        lan_year = db.execute(text("SELECT count(DISTINCT as_of) FROM vrg_floor_price "
                                   "WHERE as_of >= :y0 AND as_of <= :d"),
                              {"y0": f"{year}-01-01", "d": as_of}).scalar() or 1
        dts = [r[0] for r in db.execute(text("SELECT DISTINCT as_of FROM fact_price WHERE price_type='settlement' "
                                             "AND as_of<=:d ORDER BY as_of DESC LIMIT 2"), {"d": as_of}).all()]
        t1 = dts[0] if dts else None
        t2 = dts[1] if len(dts) > 1 else t1
        settlement = _settlement(db, t2, t1) if t1 else []
        physical = _physical(db, t2, t1) if t1 else []
        proposal = _proposal(db, sug, sug.get("prev_as_of"))
    # ngày bất kỳ (chưa ban hành) ⇒ là lần KẾ TIẾP (lan_year + 1)
    lan = int(lan_year) + (0 if sug.get("is_issuance", True) else 1)
    return {"as_of": as_of, "year": year, "lan": lan, "prev_lan": lan - 1,
            "t1": str(t1) if t1 else None, "t2": str(t2) if t2 else None,
            "settlement": settlement, "physical": physical, "proposal": proposal,
            **_narrative(settlement, physical)}
