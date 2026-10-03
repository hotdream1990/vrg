"""PHƯƠNG ÁN GIÁ SÀN nháp — bảng số người dùng (hoặc Trợ lý AI theo lời người dùng) chỉnh tự do
trước khi ra tờ trình. KHÔNG ghi `vrg_floor_price`: phương án sống trong phiên chat (frontend giữ,
gửi kèm mỗi lượt) hoặc trong bản nháp tờ trình (`floor_draft_repo`).

Mọi phép tính (chênh lệch, nội địa theo FOB, làm tròn theo bước) nằm Ở ĐÂY — không để LLM hay
frontend tự tính: LLM đã 4 lần viết sai số khi tự tính/định dạng (xem assistant-chatbot-feature).
Phép chỉnh (tăng/giảm/đặt/hoàn tác) ở `floor_proposal_ops`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.core import edit_window
from app.core.db import ensure_schema, session_scope
from app.core.market_meta import VRG_DOMESTIC_ONLY_GRADES
from app.services import floor_recommend as fr
from app.services import floor_suggest as fs

VERSION = 1
MODELS = ("v1", "v1i", "v1f", "v2")
BASES = ("model", "current")
ORIGINS = ("model", "current", "ai", "manual")
LOG_MAX = 30

#: Thứ tự CỐ ĐỊNH của tờ trình (không sort) — (tên trên tờ trình, khoá hệ thống).
TT_GRADES: list[tuple[str, str]] = [
    ("CV50", "SVR CV 50"), ("CV60", "SVR CV60"), ("SVRL", "SVR L"), ("SVR 3L Mix", "SVR 3L Mix"),
    ("SVR 3L", "SVR 3L"), ("5S", "SVR 5S"), ("SVR5", "SVR 5"), ("SVR10 Mix", "SVR 10 Mix"),
    ("SVR10", "SVR 10 / CSR 10"), ("SVR20", "SVR 20 / CSR 20"), ("RSS3", "RSS 3"), ("RSS1", "RSS 1"),
    ("Latex", "LATEX"), ("SkimBlock", "Skim Block"),
]
LABELS = {g: tt for tt, g in TT_GRADES}

#: Chặn số phi lý — chủ yếu bắt NHẦM ĐƠN VỊ (gõ giá nội địa vào ô FOB hay ngược lại).
FOB_RANGE = (100.0, 10_000.0)            # USD/tấn
VND_RANGE = (1_000_000.0, 300_000_000.0)  # đồng/tấn
#: Lệch quá ngưỡng này so với lần ban hành trước thì cảnh báo (không chặn — người dùng quyết).
WARN_PCT = 20.0


class ProposalError(ValueError):
    """Dữ liệu/thao tác phương án không hợp lệ — thông điệp tiếng Việt đưa thẳng cho người dùng."""


def is_domestic(grade: str) -> bool:
    return grade in VRG_DOMESTIC_ONLY_GRADES


def fmt_int(n: float | None) -> str:
    """2340 → '2.340' (chấm ngăn nghìn kiểu Việt Nam)."""
    return "—" if n is None else f"{fr.r0(n):,.0f}".replace(",", ".")


def fmt_signed(n: float | None) -> str:
    return "" if n is None else ("0" if n == 0 else ("+" if n > 0 else "−") + fmt_int(abs(n)))


def _step_ok(v: float | None, unit: str) -> bool:
    return v is None or fr.to_step(v, unit) == v


def _num(v: Any) -> float | None:
    """Số từ JSON (client gửi) → float; rỗng/sai kiểu → None. Bool không phải số."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def whole(v: float | None) -> float | None:
    """Giá sàn là số nguyên (USD/tấn · đồng/tấn), làm tròn nửa lên — số lẻ làm tờ trình ghi 2.082
    mà giao diện ghi 2.083."""
    return None if v is None else float(fr.r0(v))


def _in(v: float | None, field: str) -> float | None:
    lo, hi = FOB_RANGE if field == "fob" else VND_RANGE
    return v if v is not None and lo <= v <= hi else None


def check_range(v: float, field: str, label: str) -> None:
    lo, hi = FOB_RANGE if field == "fob" else VND_RANGE
    unit = "USD/tấn" if field == "fob" else "đồng/tấn"
    if not lo <= v <= hi:
        raise ProposalError(f"{label}: {fmt_int(v)} {unit} nằm ngoài khoảng hợp lý "
                            f"({fmt_int(lo)}–{fmt_int(hi)} {unit}) — kiểm tra lại đơn vị.")


def vnd_from_fob(row: dict, fob: float | None) -> float | None:
    """Giá nội địa theo FOB: giữ tỉ lệ nội địa/FOB của lần ban hành trước, làm tròn 50.000 đ.
    Cùng công thức tờ trình dùng từ trước tới nay."""
    pf, pv = row.get("prev_fob"), row.get("prev_vnd")
    if fob is None or not pf or not pv:
        return None
    return fr.to_step(pv * fob / pf, "VNĐ/T")


def derive(row: dict) -> dict:
    """Trường tính lại được của 1 dòng (chênh lệch, cờ bước, cảnh báo) — gọi sau MỌI thay đổi."""
    out = dict(row)
    for f in ("fob", "vnd"):
        cur, prev = out.get(f), out.get(f"prev_{f}")
        d = fr.r0(cur - prev) if (cur is not None and prev is not None) else None
        out[f"{f}_delta"] = d
        out[f"{f}_delta_pct"] = fr.r1(d / prev * 100) if (d is not None and prev) else None
    out["off_step"] = not (_step_ok(out.get("fob"), "USD/T") and _step_ok(out.get("vnd"), "VNĐ/T"))
    big = [p for p in (out.get("fob_delta_pct"), out.get("vnd_delta_pct"))
           if p is not None and abs(p) > WARN_PCT]
    worst = f"{max(big, key=abs):+.1f}".replace(".", ",") if big else ""
    out["warning"] = f"Lệch {worst}% so với lần ban hành trước — kiểm tra lại." if big else None
    return out


def _prev_map(as_of: str) -> dict[str, tuple[float | None, float | None]]:
    """Giá sàn lần ban hành CÓ GIÁ gần nhất TRƯỚC as_of cho từng chủng loại: {grade: (fob, vnd)}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT DISTINCT ON (grade) grade, fob_usd, domestic_vnd FROM vrg_floor_price "
            "WHERE as_of < CAST(:d AS date) AND (fob_usd IS NOT NULL OR domestic_vnd IS NOT NULL) "
            "ORDER BY grade, as_of DESC, lan DESC"), {"d": as_of}).all()
    return {g: (_num(f), _num(v)) for g, f, v in rows}


def _prev_as_of(as_of: str) -> str | None:
    with session_scope() as db:
        d = db.execute(text("SELECT max(as_of) FROM vrg_floor_price WHERE as_of < CAST(:d AS date)"),
                       {"d": as_of}).scalar()
    return str(d) if d else None


def valid_date(value: str | None) -> str:
    """YYYY-MM-DD hợp lệ; bỏ trống → hôm nay. Sai định dạng → ProposalError (không thả xuống SQL)."""
    if not value:
        return edit_window.today().isoformat()
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise ProposalError("Ngày không hợp lệ (cần dạng YYYY-MM-DD).") from exc


def build(as_of: str | None = None, base: str = "model", model: str = fs.DEFAULT_MODEL) -> dict[str, Any]:
    """Dựng phương án mới tại `as_of`: mức mô hình (base=model) hoặc giá hiện hành (base=current).

    Chủng loại chưa đủ dữ liệu mô hình thì lấy giá hiện hành làm điểm xuất phát (origin=current) —
    phương án là để người dùng sửa, một dòng trống không giúp được gì.
    """
    as_of = valid_date(as_of)
    base = base if base in BASES else "model"
    model = model if model in MODELS else fs.DEFAULT_MODEL
    sug = fs.suggest(as_of, model, backtest=True)
    if sug.get("error"):
        raise ProposalError(sug["error"])
    model_val = {it["grade"]: it.get("suggested") for it in sug.get("items", [])}
    prev = _prev_map(as_of)
    rows = []
    for tt, g in TT_GRADES:
        pf, pv = prev.get(g, (None, None))
        dom = is_domestic(g)
        row = {"grade": g, "label": tt, "unit": "VNĐ/T" if dom else "USD/T",
               "prev_fob": None if dom else pf, "prev_vnd": pv, "vnd_manual": False}
        mv = _num(model_val.get(g))
        row["model_fob"] = None if dom else mv
        row["model_vnd"] = mv if dom else vnd_from_fob(row, mv)
        use_model = base == "model" and mv is not None
        row["fob"] = row["model_fob"] if use_model else row["prev_fob"]
        row["vnd"] = row["model_vnd"] if use_model else row["prev_vnd"]
        row["origin"] = "model" if use_model else "current"
        rows.append(derive(row))
    return {"version": VERSION, "as_of": as_of, "prev_as_of": sug.get("prev_as_of") or _prev_as_of(as_of),
            "model": model, "base": base, "rows": rows, "log": []}


def _clean_row(raw: dict, prev: tuple[float | None, float | None], g: str, tt: str) -> dict:
    dom = is_domestic(g)
    row = {"grade": g, "label": tt, "unit": "VNĐ/T" if dom else "USD/T",
           "prev_fob": None if dom else prev[0], "prev_vnd": prev[1],
           # Mức mô hình chỉ để tham chiếu nhưng "đưa về mô hình" dùng nó ⇒ số lạ thì bỏ, không nhận.
           "model_fob": None if dom else _in(_num(raw.get("model_fob")), "fob"),
           "model_vnd": _in(_num(raw.get("model_vnd")), "vnd"),
           "fob": None if dom else whole(_num(raw.get("fob"))), "vnd": whole(_num(raw.get("vnd"))),
           "vnd_manual": bool(raw.get("vnd_manual")) and not dom,
           "origin": raw.get("origin") if raw.get("origin") in ORIGINS else "manual"}
    for f in ("fob", "vnd"):
        if row[f] is not None:
            check_range(row[f], f, g)
    return derive(row)


def _in_range(v: float | None, field: str) -> bool:
    lo, hi = FOB_RANGE if field == "fob" else VND_RANGE
    return v is None or lo <= v <= hi


def _clean_before(b: Any) -> dict | None:
    """Giá trị trước-khi-đổi của 1 dòng trong nhật ký; số lạ ⇒ bỏ cả mục (hoàn tác không được đưa số
    ngoài khoảng hợp lý trở lại phương án)."""
    if not isinstance(b, dict):
        return None
    fob, vnd = _num(b.get("fob")), _num(b.get("vnd"))
    if not (_in_range(fob, "fob") and _in_range(vnd, "vnd")):
        return None
    return {"fob": fob, "vnd": vnd, "vnd_manual": bool(b.get("vnd_manual")),
            "origin": b.get("origin") if b.get("origin") in ORIGINS else "manual"}


def _clean_log(raw: Any) -> list[dict]:
    out = []
    for e in (raw if isinstance(raw, list) else [])[-LOG_MAX:]:
        if not isinstance(e, dict) or not isinstance(e.get("text"), str):
            continue
        before_raw = e.get("before") if isinstance(e.get("before"), dict) else {}
        before = {g: _clean_before(b) for g, b in before_raw.items() if g in LABELS}
        if any(v is None for v in before.values()):
            continue
        out.append({"at": str(e.get("at") or "")[:32],
                    "by": e.get("by") if e.get("by") in ("ai", "manual", "system") else "manual",
                    "text": e["text"][:500], "before": before})
    return out


def _sanitize(raw: Any) -> dict[str, Any] | None:
    """Phương án client gửi lên → bản sạch. Không tin client: chủng loại/thứ tự dựng lại theo tờ
    trình, giá lần trước NẠP LẠI TỪ DB (chênh lệch trên tờ trình phải đúng sự thật), trường tính
    toán tính lại, số ngoài khoảng hợp lý bị từ chối. None/rỗng → None."""
    if not raw:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        raise ProposalError("Phương án không đúng định dạng.")
    as_of = valid_date(raw.get("as_of"))
    by_grade = {r["grade"]: r for r in raw["rows"][:50]
                if isinstance(r, dict) and isinstance(r.get("grade"), str)}
    prev = _prev_map(as_of)
    rows = [_clean_row(by_grade.get(g, {}), prev.get(g, (None, None)), g, tt) for tt, g in TT_GRADES]
    return {"version": VERSION, "as_of": as_of,
            "prev_as_of": _prev_as_of(as_of),
            "model": raw.get("model") if raw.get("model") in MODELS else fs.DEFAULT_MODEL,
            "base": raw.get("base") if raw.get("base") in BASES else "model",
            "rows": rows, "log": _clean_log(raw.get("log"))}


def sanitize(raw: Any) -> dict[str, Any] | None:
    """Phương án client gửi lên → bản sạch (xem `_sanitize`). Dữ liệu sai kiểu ở bất kỳ chỗ nào →
    ProposalError (400 gọn), không để lọt TypeError thành lỗi 500."""
    try:
        return _sanitize(raw)
    except ProposalError:
        raise
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        raise ProposalError("Phương án không đúng định dạng.") from exc


def now_iso() -> str:
    """Giờ Việt Nam kèm múi giờ — máy chủ prod chạy UTC, giờ trơn làm nhật ký lệch 7 tiếng."""
    return edit_window.now().isoformat(timespec="seconds")


def row_line(row: dict, with_model: bool = True) -> str:
    """Câu tóm tắt 1 dòng, số đã định dạng sẵn — LLM chép nguyên, không tự định dạng lại."""
    parts = []
    if row["unit"] == "USD/T":
        parts.append(f"FOB {fmt_int(row['fob'])} USD/tấn"
                     + (f" ({fmt_signed(row['fob_delta'])} so lần trước {fmt_int(row['prev_fob'])})"
                        if row.get("fob_delta") is not None else ""))
    parts.append(f"nội địa {fmt_int(row['vnd'])} đồng/tấn"
                 + (f" ({fmt_signed(row['vnd_delta'])} so lần trước {fmt_int(row['prev_vnd'])})"
                    if row.get("vnd_delta") is not None else ""))
    if with_model and (row.get("model_fob") if row["unit"] == "USD/T" else row.get("model_vnd")) is not None:
        mv = row["model_fob"] if row["unit"] == "USD/T" else row["model_vnd"]
        parts.append(f"mức mô hình {fmt_int(mv)} {'USD/tấn' if row['unit'] == 'USD/T' else 'đồng/tấn'}")
    origin = {"model": "theo mô hình", "current": "giữ giá hiện hành", "ai": "Trợ lý chỉnh theo yêu cầu",
              "manual": "người dùng sửa tay"}[row["origin"]]
    return f"{row['grade']}: " + " · ".join(parts) + f" · {origin}"


def to_trinh_rows(prop: dict) -> list[dict]:
    """Dòng khối 3 tờ trình (Giá dự kiến + (+/-) so lần trước) từ phương án."""
    return [{"key": r["grade"], "grade": r["label"], "fob": r.get("fob"), "fob_delta": r.get("fob_delta"),
             "vnd": r.get("vnd"), "vnd_delta": r.get("vnd_delta")} for r in prop["rows"]]


def headline(prop: dict) -> str:
    """Tóm tắt 1 dòng cho danh sách bản nháp: dòng SVR 10 (mặt hàng chính)."""
    r = next((x for x in prop["rows"] if x["grade"] == "SVR 10 / CSR 10"), None)
    if not r or r.get("fob") is None:
        return ""
    d = r.get("fob_delta")
    return f"SVR10 {fmt_int(r['fob'])} USD/T" + (f" ({fmt_signed(d)})" if d is not None else "")
