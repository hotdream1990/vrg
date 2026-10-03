"""Sinh dữ liệu TỜ TRÌNH giá sàn từ engine gợi ý + dữ liệu thị trường.

Khối 3 (đề xuất) lấy từ phương án [floor_proposal] (mặc định = mức mô hình; bản nháp = số người
dùng đã chỉnh); khối 1-2 (settlement/physical) từ fact_price quy đổi USD/T. GIỮ ĐÚNG THỨ TỰ chủng loại cố định — KHÔNG sort (xem to-trinh-gia-san-format).
"""
from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import FX_PAIRS
from app.core.paths import bulletin_dir
from app.services import floor_proposal
from app.services import floor_suggest as fs

# bulletin.convert — 1 NGUỒN quy đổi & làm tròn (nửa lên) dùng chung với bản tin/lưới giá.
_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import r0, to_usd_tonne_detail  # noqa: E402

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


def _dmy_short(iso: str | None) -> str:
    """'2026-07-22' -> '22/07'."""
    return f"{iso[8:10]}/{iso[5:7]}" if iso and len(iso) >= 10 else "—"


_PLAUSIBLE_MAX = 6000  # USD/T — chặn giá trị phi lý (vd lgm LATEX lưu Sen/kg thô chưa quy đổi)


def _usd_t(price: float | None, unit: str | None, fx: dict) -> int | None:
    """Quy đổi USD/tấn qua bulletin.convert (đủ mọi đơn vị, kể cả Sen/kg của MRE Latex).

    Trước đây hàm này tự viết lại 4 nhánh đơn vị nên bỏ sót `Sen/kg` ⇒ dòng MRE LATEX luôn
    trống, và dùng `round()` của Python (làm tròn về số chẵn) thay vì nửa-lên như quy ước.
    """
    if price is None:
        return None
    usd, _, _ = to_usd_tonne_detail(float(price), unit or "", fx)
    if usd is None:
        return None
    v = r0(usd)
    return None if v > _PLAUSIBLE_MAX else v


def _at(db, source: str, grade: str, d):
    """Bản ghi ĐÚNG NGÀY d; không có thì phiên gần nhất trước đó (ngày thật được trả về để
    hiển thị kèm) — KHÔNG bao giờ gán số của ngày khác vào ô của ngày d mà giấu ngày đi."""
    return db.execute(text("SELECT price, unit, as_of FROM fact_price WHERE source=:s AND grade=:g "
                           "AND as_of<=:d ORDER BY as_of DESC LIMIT 1"), {"s": source, "g": grade, "d": d}).first()


def _fx_at(db, d) -> dict:
    """Tỷ giá ĐÚNG NGÀY d cho mọi cặp (JPY·CNY·MYR·THB…). Thiếu → không có khoá đó ⇒ ô để
    trống, không lấy tỷ giá ngày khác quy đổi (đúng luật no-carry-forward của dự án)."""
    out = {}
    for cur in FX_PAIRS:
        r = db.execute(text("SELECT price FROM fact_price WHERE source='fx' AND grade=:g AND as_of=:d"),
                       {"g": cur, "d": d}).first()
        if r:
            out[cur] = r[0]
    return out


def _row(prev, curr) -> dict:
    d = (curr - prev) if (prev is not None and curr is not None) else None
    pct = (round(d / prev * 100, 1) if (d is not None and prev) else None)
    return {"prev": prev, "curr": curr, "d_abs": d, "d_pct": pct}


def _settlement(db, t2, t1) -> list[dict]:
    """2 cột giá của mỗi sàn, kèm NGÀY THẬT của từng ô.

    Các sàn nghỉ lễ lệch nhau nên không phải sàn nào cũng có phiên đúng ngày t1/t2. Ô nào rơi
    vào phiên khác thì trả kèm `curr_as_of`/`prev_as_of` để bản in ghi rõ ngày — thay vì im
    lặng coi số phiên cũ là số của ngày t1. Hai ô trùng ngày ⇒ bỏ cột trước (không có gì để so).
    """
    out = []
    for src, g, san, disp in SETTLE:
        r1, r2 = _at(db, src, g, t1), _at(db, src, g, t2)
        v1 = _usd_t(r1[0], r1[1], _fx_at(db, r1[2])) if r1 else None
        v2 = _usd_t(r2[0], r2[1], _fx_at(db, r2[2])) if r2 else None
        d1 = r1[2] if r1 else None
        d2 = r2[2] if r2 else None
        if d1 is not None and d2 is not None and d2 >= d1:   # cùng 1 phiên → không so sánh
            v2, d2 = None, None
        out.append({"san": san, "grade": disp, **_row(v2, v1),
                    "curr_as_of": str(d1) if d1 else None,
                    "prev_as_of": str(d2) if d2 else None})
    return out


def _physical(db, t2, t1) -> list[dict]:
    out = []
    for g in PHYS:
        def val(r, ref):
            return r0(r[0]) if (r and (ref - r[2]).days <= _STALE_DAYS) else None
        v1 = val(_at(db, "reuters", g, t1), t1)
        v2 = val(_at(db, "reuters", g, t2), t2)
        out.append({"grade": g, **_row(v2, v1)})
    return out


def default_narrative(settlement: list[dict], physical: list[dict], t1=None) -> dict:
    """Câu nhận định CHỈ nói đúng những gì số liệu có.

    Ô nào không có phiên đúng ngày t1 thì ghi rõ "(phiên dd/mm)"; ô không có phiên trước để so
    thì chỉ nêu mức giá, KHÔNG được viết "đi ngang" (trước đây so ô với chính nó ra 0% rồi kết
    luận đi ngang — nhận định không có thật trong văn bản trình Tổng Giám đốc).
    """
    ref = str(t1) if t1 else None

    def tag(r) -> str:
        d = r.get("curr_as_of")
        return f" (phiên {_dmy_short(d)})" if (d and ref and d != ref) else ""

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
                parts.append(f"{r['grade']} ở mức {vn(r['curr'])} USD/T{tag(r)}")
            else:
                dirn = "tăng" if r["d_abs"] > 0 else ("giảm" if r["d_abs"] < 0 else "đi ngang")
                parts.append(
                    f"{r['grade']} {dirn} {abs(r['d_abs'])} USD/T ({vn(r['curr'])}, "
                    f"{str(format(r['d_pct'], '+')).replace('.', ',')}%){tag(r)}")
        if parts:
            n1.append(f"- {SAN_FULL[san]}: " + "; ".join(parts) + ".")
    has_phys = any(r["curr"] is not None for r in physical)
    n2 = ["- Thị trường cao su vật chất phân hóa nhu cầu giữa các chủng loại."
          if has_phys else "- Dữ liệu giá vật chất chưa cập nhật cho kỳ này (bổ sung thủ công)."]
    n2.append("- Tồn kho Tập đoàn: (cập nhật thủ công).")
    return {"n1": n1, "n2": n2}


def build_market(as_of: str) -> dict[str, Any]:
    """Phần tờ trình KHÔNG phụ thuộc đề xuất giá: lần thứ, 2 ngày so sánh, khối 1–2 + diễn giải.

    Bản nháp tờ trình lưu ảnh chụp phần này; khối 3 (đề xuất) lấy từ phương án [floor_proposal].
    """
    ensure_schema()
    year = int(as_of[:4])
    with session_scope() as db:
        lan_year = db.execute(text("SELECT count(DISTINCT as_of) FROM vrg_floor_price "
                                   "WHERE as_of >= :y0 AND as_of <= :d"),
                              {"y0": f"{year}-01-01", "d": as_of}).scalar() or 1
        is_issuance = db.execute(text("SELECT 1 FROM vrg_floor_price WHERE as_of = CAST(:d AS date) LIMIT 1"),
                                 {"d": as_of}).first() is not None
        dts = [r[0] for r in db.execute(text("SELECT DISTINCT as_of FROM fact_price WHERE price_type='settlement' "
                                             "AND as_of<=:d ORDER BY as_of DESC LIMIT 2"), {"d": as_of}).all()]
        t1 = dts[0] if dts else None
        t2 = dts[1] if len(dts) > 1 else t1
        settlement = _settlement(db, t2, t1) if t1 else []
        physical = _physical(db, t2, t1) if t1 else []
    # ngày bất kỳ (chưa ban hành) ⇒ là lần KẾ TIẾP (lan_year + 1)
    lan = int(lan_year) + (0 if is_issuance else 1)
    return {"as_of": as_of, "year": year, "lan": lan, "prev_lan": lan - 1,
            "t1": str(t1) if t1 else None, "t2": str(t2) if t2 else None,
            "settlement": settlement, "physical": physical,
            **default_narrative(settlement, physical, t1)}


def build(as_of: str, model: str = fs.DEFAULT_MODEL) -> dict[str, Any]:
    """Gom toàn bộ dữ liệu 4 khối tờ trình cho 1 lần ban hành (as_of) — đề xuất = mức mô hình."""
    try:
        prop = floor_proposal.build(as_of, "model", model)
    except floor_proposal.ProposalError as exc:
        return {"error": str(exc), "as_of": as_of}
    return {**build_market(prop["as_of"]), "proposal": floor_proposal.to_trinh_rows(prop)}
