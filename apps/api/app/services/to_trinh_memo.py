"""Nội dung TỜ TRÌNH giá sàn theo mẫu mới (Tờ trình 54/TTr-TTKD, lần 22 ngày 24/9/2026).

`defaults(doc)` dựng nội dung mặc định CHỈ từ số liệu (không bịa nhận định): đoạn theo từng sàn,
đoạn vật chất, dòng tồn kho, câu kính trình, người ký. Chuyên viên sửa tay hoặc nhờ AI soạn
([to_trinh_ai]); `clean(raw, base)` làm sạch nội dung gửi lên, thiếu khoá nào lấy từ `base`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services.to_trinh import default_narrative, vn

SAN_LEAD = {"OSE": "OSE (Osaka Exchange)", "SHANGHAI": "SHANGHAI (SHFE)",
            "SGX": "SGX (Singapore Exchange/SICOM)", "MRE": "MRE (Malaysia Rubber Exchange)"}
SIGNERS = {"left_role": "PHÓ TỔNG GIÁM ĐỐC PHỤ TRÁCH", "left_name": "Trần Như Hùng",
           "right_role": "TRƯỞNG BAN TTKD", "right_name": "Đồng Văn Tuấn Đạt",
           "approver_role": "TỔNG GIÁM ĐỐC DUYỆT", "approver_name": "Lê Thanh Hưng"}
TEXT_KEYS = ("so", "sign_date", "futures_note", "physical_title", "physical_note", "intro")
PARA_KEYS = ("futures", "physical", "outlook")
_LEN = {"so": 40, "sign_date": 10, "futures_note": 1500, "physical_title": 300, "physical_note": 1500,
        "intro": 1500}
_PARA_MAX, _LEAD_LEN, _TEXT_LEN = 20, 200, 4000


def dmy(iso: str | None) -> str:
    """'2026-09-22' → '22/9/2026' (kiểu mẫu tờ trình)."""
    if not iso:
        return "—"
    y, m, d = iso[:10].split("-")
    return f"{int(d)}/{int(m)}/{y}"


def dm(iso: str | None) -> str:
    return dmy(iso).rsplit("/", 1)[0] if iso else "—"


def _pct(p: float | None) -> str:
    return "" if p is None else f"{p:+.1f}%".replace(".", ",")


def _grade_text(r: dict, t1: str | None) -> str:
    g, prev, curr, d = r["grade"], r.get("prev"), r.get("curr"), r.get("d_abs")
    if curr is None:
        return f"{g} không có phiên giao dịch ngày {dm(t1)}"
    tag = f" (phiên {dm(r['curr_as_of'])})" if r.get("curr_as_of") and t1 and r["curr_as_of"] != t1 else ""
    if d is None:
        return f"{g} ở mức {vn(curr)} USD/tấn{tag}"
    if d == 0:
        return f"{g} đi ngang ở mức {vn(curr)} USD/tấn{tag}"
    way = "tăng từ {} lên {}" if d > 0 else "giảm từ {} xuống {}"
    sign = "+" if d > 0 else "-"
    return (f"{g} {way.format(vn(prev), vn(curr))} USD/tấn{tag} "
            f"({sign}{vn(abs(d))} USD/tấn, {_pct(r.get('d_pct'))})")


def futures_paras(settlement: list[dict], t1: str | None) -> list[dict]:
    """Một đoạn mỗi sàn, lead kiểu mẫu: 'SGX (Singapore Exchange/SICOM) – RSS3 & TSR20:'."""
    by_san: dict[str, list[dict]] = {}
    for r in settlement:
        by_san.setdefault(r["san"], []).append(r)
    out = []
    for san, rs in by_san.items():
        grades = [r["grade"] for r in rs]
        joined = " & ".join(grades) if len(grades) == 2 else ", ".join(grades)
        lead = f"{SAN_LEAD.get(san, san)} – {joined}:"
        if all(r.get("curr") is None for r in rs):
            text = f"Sàn {san} nghỉ giao dịch, không phát sinh giá tham chiếu mới."
        else:
            text = "; ".join(_grade_text(r, t1) for r in rs) + "."
        out.append({"lead": lead, "text": text[0].upper() + text[1:]})
    return out


def futures_note(settlement: list[dict], t1: str | None, t2: str | None) -> str:
    closed = sorted({r["san"] for r in settlement if r.get("curr") is None})
    note = ("Nguồn: Tổng hợp dữ liệu giao dịch OSE, SHFE, SGX (SICOM), MRE (Malaysia Rubber Exchange), "
            f"khảo sát ngày {dmy(t2)} và {dmy(t1)}.")
    return note + (f" {', '.join(closed)} không có phiên giao dịch ngày {dm(t1)}." if closed else "")


def physical_paras(physical: list[dict]) -> list[dict]:
    parts = []
    for r in physical:
        if r.get("curr") is None:
            continue
        d = r.get("d_abs")
        if d is None or d == 0:
            parts.append(f"{r['grade']} ở mức {vn(r['curr'])} USD/tấn")
        else:
            way = "tăng" if d > 0 else "giảm"
            parts.append(f"{r['grade']} {way} {vn(abs(d))} USD/tấn ({_pct(r.get('d_pct'))}) "
                         f"{'lên' if d > 0 else 'còn'} {vn(r['curr'])} USD/tấn")
    if not parts:
        return [{"lead": "", "text": "Dữ liệu giá vật chất chưa cập nhật cho kỳ này (bổ sung thủ công)."}]
    return [{"lead": "", "text": "Giá trên sàn Physical: " + "; ".join(parts) + "."}]


def inventory_para(rows: list[dict]) -> dict:
    """Dòng tồn kho kiểu mẫu từ 2 tuần gần nhất của fact_inventory (mới trước)."""
    rows = [r for r in rows if r.get("ton_kho") is not None]
    if not rows:
        return {"lead": "Tồn kho Tập đoàn:", "text": "chưa có số liệu tuần — cập nhật trước khi trình."}
    cur = rows[0]
    wk = date.fromisoformat(cur["as_of"]).isocalendar()[1]
    y, m, d = cur["as_of"][:10].split("-")
    lead = f"Tồn kho Tập đoàn lũy kế tuần {wk}: {d}/{m}/{y}: {vn(cur['ton_kho'])} tấn"
    if len(rows) < 2:
        return {"lead": lead, "text": ""}
    diff = cur["ton_kho"] - rows[1]["ton_kho"]
    if round(diff) == 0:
        return {"lead": lead, "text": f"không đổi so với tuần trước đó ({vn(rows[1]['ton_kho'])} tấn)."}
    lead += f" {'tăng' if diff > 0 else 'giảm'} {vn(abs(diff))} tấn"
    return {"lead": lead, "text": f"so với tuần trước đó là {vn(rows[1]['ton_kho'])} tấn."}


def intro(lan: int, year: int) -> str:
    return (f"Ban TTKD kính trình Tổng giám đốc phê duyệt điều chỉnh giá sàn lần thứ {lan} năm {year} như sau: "
            "Giá xuất khẩu FOB cảng TP Hồ Chí Minh hàng có palét cho các chủng loại SVR (USD/T) và Giá hàng "
            "rời, bán nội địa (giao hàng tại kho):")


def _legacy(lines: list[str] | None, auto: list[str]) -> list[dict] | None:
    """Diễn giải đã sửa tay ở bản nháp cũ (n1/n2) → đoạn văn; chưa sửa (= mặc định cũ) → None."""
    if not lines or lines == auto:
        return None
    return [{"lead": "", "text": s.lstrip("-–• ").strip()} for s in lines if s.strip()]


def defaults(doc: dict, inventory_rows: list[dict] | None = None) -> dict[str, Any]:
    """Nội dung tờ trình mặc định từ ảnh chụp thị trường `doc` (+ 2 tuần tồn kho gần nhất)."""
    sett, phys, t1, t2 = doc.get("settlement") or [], doc.get("physical") or [], doc.get("t1"), doc.get("t2")
    auto = default_narrative(sett, phys, t1)
    return {
        "so": "", "sign_date": doc["as_of"],
        "futures_note": futures_note(sett, t1, t2),
        "futures": _legacy(doc.get("n1"), auto["n1"]) or futures_paras(sett, t1),
        "physical_title": f"tham chiếu giá nguồn từ ANRPC các ngày {dm(t2)} và {dm(t1)}",
        "physical_note": "",
        "physical": _legacy(doc.get("n2"), auto["n2"]) or physical_paras(phys),
        "outlook": [],
        "inventory": inventory_para(inventory_rows or []),
        "intro": intro(doc["lan"], doc["year"]),
        "signers": dict(SIGNERS), "ai": None,
    }


def _s(v: Any, n: int) -> str:
    return v.strip()[:n] if isinstance(v, str) else ""


def _para(p: Any) -> dict:
    p = p if isinstance(p, dict) else {"text": p}
    return {"lead": _s(p.get("lead"), _LEAD_LEN), "text": _s(p.get("text"), _TEXT_LEN)}


def clean(raw: Any, base: dict) -> dict[str, Any]:
    """Làm sạch nội dung gửi lên; khoá thiếu lấy từ `base`. Bỏ đoạn rỗng (cả lead lẫn text)."""
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {k: (_s(raw[k], _LEN[k]) if k in raw else base[k]) for k in TEXT_KEYS}
    for k in PARA_KEYS:
        items = raw[k] if isinstance(raw.get(k), list) else base[k]
        out[k] = [p for p in map(_para, items[:_PARA_MAX]) if p["lead"] or p["text"]]
    out["inventory"] = _para(raw["inventory"]) if "inventory" in raw else base["inventory"]
    sig = raw.get("signers") if isinstance(raw.get("signers"), dict) else {}
    out["signers"] = {k: (_s(sig[k], 120) if k in sig else base["signers"][k]) for k in SIGNERS}
    ai = raw.get("ai") if "ai" in raw else base.get("ai")
    out["ai"] = ({"at": _s(ai.get("at"), 40), "by": _s(ai.get("by"), 80) or None, "sig": _s(ai.get("sig"), 40),
                  "warnings": [_s(w, 300) for w in (ai.get("warnings") or [])[:20] if isinstance(w, str)]}
                 if isinstance(ai, dict) else None)
    if not out["sign_date"] or len(out["sign_date"]) != 10:
        out["sign_date"] = base["sign_date"]
    return out
