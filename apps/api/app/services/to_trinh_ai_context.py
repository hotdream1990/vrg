"""Ngữ cảnh cho AI soạn TỜ TRÌNH giá sàn — chỉ dữ liệu THẬT của bản nháp: bảng I/II (ảnh chụp lúc tạo),
phương án + CHIỀU điều chỉnh, tồn kho, bối cảnh từ Báo cáo tuần đã lưu gần nhất, tin vietnambiz quanh
ngày tờ trình. Khối nào lỗi/quá hạn thì bỏ, không làm hỏng cả lượt (như Báo cáo tuần).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.to_trinh import vn
from app.services.to_trinh_memo import dmy
from app.services.weekly_ai_context import run_blocks

DEADLINE_S = 25
_NEWS_INDEX = "https://vietnambiz.vn/gia-cao-su.html"
_NEWS_MAX, _NEWS_CHARS, _WEEKLY_CHARS = 3, 1500, 5000


def _chg(d: float | None, p: float | None) -> str:
    if d is None:
        return "không có phiên trước để so"
    pct = "" if p is None else f" ({p:+.1f}%)".replace(".", ",")
    return f"{'+' if d > 0 else ''}{vn(d) if d >= 0 else '-' + vn(abs(d))} USD/tấn{pct}"


def _px(v: float | None) -> str:
    return "nghỉ giao dịch / không có giá" if v is None else f"{vn(v)} USD/tấn"


def direction(rows: list[dict]) -> dict[str, Any]:
    """Chiều điều chỉnh của phương án so với lần ban hành trước (FOB; dòng chỉ nội địa xét nội địa)."""
    ds = [r.get("fob_delta") if r.get("unit") != "VNĐ/T" else r.get("vnd_delta") for r in rows]
    ds = [d for d in ds if d is not None]
    up, down = sum(d > 0 for d in ds), sum(d < 0 for d in ds)
    word = ("tăng" if up and not down else "giảm" if down and not up else
            "giữ nguyên" if not up and not down else "trái chiều")
    fob = sorted({r["fob_delta"] for r in rows if r.get("fob_delta") is not None})
    vnd = sorted({r["vnd_delta"] for r in rows if r.get("vnd_delta") is not None})
    return {"word": word, "up": up, "down": down, "total": len(ds), "fob": fob, "vnd": vnd}


def _signed(v: float) -> str:
    return ("+" if v > 0 else "") + (vn(v) if v >= 0 else "-" + vn(abs(v)))


def _span(vals: list[float], unit: str) -> str:
    if not vals:
        return "—"
    return f"{_signed(vals[0])} {unit}" if len(vals) == 1 else f"từ {_signed(vals[0])} đến {_signed(vals[-1])} {unit}"


def market_block(doc: dict) -> list[str]:
    out = [f"TỜ TRÌNH GIÁ SÀN LẦN {doc['lan']}/{doc['year']} — ngày {dmy(doc['as_of'])}. "
           f"So sánh hai phiên {dmy(doc.get('t2'))} và {dmy(doc.get('t1'))}.", "",
           "BẢNG I — GIÁ CAO SU KỲ HẠN (quy đổi USD/tấn):"]
    for r in doc.get("settlement") or []:
        tag = f" (giá phiên {dmy(r['curr_as_of'])})" if r.get("curr_as_of") and r["curr_as_of"] != doc.get("t1") else ""
        out.append(f"- {r['san']} {r['grade']}: {_px(r.get('prev'))} → {_px(r.get('curr'))}{tag}; "
                   f"thay đổi {_chg(r.get('d_abs'), r.get('d_pct'))}")
    out += ["", "BẢNG II — GIÁ CAO SU VẬT CHẤT (USD/tấn):"]
    for r in doc.get("physical") or []:
        out.append(f"- {r['grade']}: {_px(r.get('prev'))} → {_px(r.get('curr'))}; "
                   f"thay đổi {_chg(r.get('d_abs'), r.get('d_pct'))}")
    return out


def proposal_block(prop: dict, doc: dict, inventory: dict) -> list[str]:
    out = [f"PHƯƠNG ÁN GIÁ SÀN LẦN {doc['lan']}/{doc['year']} so với lần {doc['prev_lan']}/{doc['year']} "
           f"(ban hành {dmy(prop.get('prev_as_of'))}):"]
    for r in prop.get("rows") or []:
        parts = []
        for key, unit, name in (("fob", "USD/tấn", "FOB"), ("vnd", "đ/tấn", "nội địa")):
            if r.get(key) is not None:
                d = r.get(f"{key}_delta")
                parts.append(f"{name} {vn(r[key])} {unit} ({'chưa có lần trước' if d is None else _signed(d) + ' ' + unit})")
        out.append(f"- {r['label']}: " + "; ".join(parts))
    d = direction(prop.get("rows") or [])
    out += ["", f"CHIỀU ĐIỀU CHỈNH CỦA PHƯƠNG ÁN: {d['word'].upper()} — {d['up']} dòng tăng, {d['down']} dòng giảm "
            f"trên {d['total']} dòng; FOB {_span(d['fob'], 'USD/tấn')}; nội địa {_span(d['vnd'], 'đ/tấn')}.",
            "", "TỒN KHO TẬP ĐOÀN: " + " ".join(x for x in (inventory.get("lead"), inventory.get("text")) if x)]
    return out


def weekly_block(as_of: str) -> list[str]:
    """Phần nhận định của Báo cáo tuần ĐÃ LƯU gần nhất (tuần ≤ ngày tờ trình)."""
    from app.services import weekly_report_service as wr

    rep = next((r for r in wr.list_reports() if r["week_key"] <= as_of), None)
    if not rep:
        return []
    nar = wr.load_saved(rep["week_key"])
    lines: list[str] = []
    for key in ("movement", "exchange_notes", "physical_notes", "forecast", "conclusion"):
        lines += [s for s in nar.get(key) or [] if isinstance(s, str)]
    for sec in nar.get("macro") or []:
        lines += [f"{sec.get('title', '')}: {b}" for b in sec.get("bullets") or [] if isinstance(b, str)]
    body = "\n".join(lines)[:_WEEKLY_CHARS]
    return [f"BỐI CẢNH TỪ BÁO CÁO TUẦN ĐÃ LƯU ({rep['label']}) — chỉ dùng làm nền, ưu tiên số của bảng I/II:", body] if body else []


def news_block(doc: dict) -> list[str]:
    from app.services import weekly_news

    end = date.fromisoformat(doc["as_of"])
    start = date.fromisoformat(doc.get("t2") or doc["as_of"]) - timedelta(days=1)
    arts = weekly_news.fetch_period_articles(_NEWS_INDEX, start, end, max_articles=_NEWS_MAX)
    out = ["TIN VIETNAMBIZ 'Giá cao su hôm nay' quanh ngày tờ trình — nguồn DUY NHẤT cho sự kiện/nguyên nhân:"] if arts else []
    for a in arts:
        out += [f"[{a['published']}] {a['title']}", a["body"][:_NEWS_CHARS]]
    return out


def build(draft: dict, inventory: dict) -> str:
    doc, prop = draft["doc"], draft["proposal"]
    jobs = [("thị trường", market_block, doc), ("phương án", proposal_block, prop, doc, inventory),
            ("báo cáo tuần", weekly_block, draft["as_of"]), ("tin", news_block, doc)]
    return "\n\n".join("\n".join(b) for b in run_blocks(jobs, DEADLINE_S) if b)
