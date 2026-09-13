"""Ngữ cảnh THẬT cho AI viết Báo cáo tuần v2 — mọi số/sự kiện AI được dùng đều nằm ở đây.

Khối: kỳ báo cáo · bảng III.1/III.2 mọi tuần (+/-, %) · ghi chú không có giá · cao/thấp cả kỳ kèm
giá nội tệ · giá từng phiên · tỷ giá TB tuần · DXY/WTI/Brent (CNBC, dự phòng Yahoo) · mủ nước · Phần II đã
lưu của báo cáo tuần mốc + bảng tuần mốc · tài liệu đính kèm · tin vietnambiz trong kỳ · góc phân
tích gợi ý từ danh mục nguồn. Mỗi khối lấy độc lập (song song, hạn chờ tổng `BLOCKS_DEADLINE_S`), lỗi
hoặc quá hạn thì BỎ khối đó (ghi log), không hỏng lượt. Chữ nhúng từ ngoài (file, tin, hướng dẫn nguồn)
được bỏ chuỗi phân cách prompt (`strip_delimiters`) để không phá khung khối dữ liệu.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, timedelta
from typing import Any

from app.services import weekly_period, weekly_report_service
from app.services import weekly_report_tables as tables
from app.services.weekly_ai_compose import pct, signed, vn, vn_native
from app.services.weekly_ai_macro_prompts import macro_titles, source_code_map
from app.services.weekly_ai_prompts import DOCS_HEADER, strip_delimiters
from app.services.weekly_report_gaps import NO_FX, day_state

logger = logging.getLogger(__name__)

NEWS_MAX_CHARS = 16_000
DOCS_MAX_CHARS = 24_000
GUIDE_MAX_CHARS = 400
BLOCKS_DEADLINE_S = 45   # hạn chờ TỔNG cho mọi khối (mạng tin/nguồn chỉ số chậm không treo lượt AI)
_NEWS_PER_WEEK = 5
_NEWS_MAX_ARTICLES = 16
_DEFAULT_NEWS_INDEX = "https://vietnambiz.vn/gia-cao-su.html"
_FX_DEC = {"USD/JPY": 2, "USD/CNY": 4, "USD/MYR": 4, "USD/THB": 2}
_FX_CURRENCY = {"USD/JPY": "Yên", "USD/CNY": "Nhân dân tệ", "USD/MYR": "Ringgit", "USD/THB": "Baht"}
_FX_LOGIC = (
    "Cách đọc tỷ giá: USD/JPY tăng = đồng Yên yếu đi (cao su sàn OSE hấp dẫn hơn với nhà đầu tư dùng "
    "ngoại tệ); USD/THB, USD/MYR giảm = Baht/Ringgit mạnh lên (cao su xuất khẩu quy USD đắt hơn, có "
    "thể nâng đỡ SGX/MRE), tăng = Baht/Ringgit yếu đi; USD/CNY tăng = Nhân dân tệ yếu đi."
)


def _series(label: str, weeks: list[dict[str, Any]], values: list, changes: list, pcts: list,
            dec: int = 1) -> str:
    cols = " · ".join(f"{w['short']} {vn(v, dec)}" for w, v in zip(weeks, values))
    pairs = " · ".join(
        f"{weeks[i + 1]['short']}/{weeks[i]['short']}: {signed(c, dec)} ({pct(p, 2)})"
        for i, (c, p) in enumerate(zip(changes, pcts)))
    return f"- {label}: {cols}" + (f" | {pairs}" if pairs else "")


def _row_lines(rows: list[dict[str, Any]], weeks: list[dict[str, Any]]) -> list[str]:
    return [_series(" ".join(x for x in (r.get("exchange"), r["grade"]) if x), weeks, r["values"],
                    r["changes"], r["changes_pct"]) for r in rows]


def _stat_line(s: dict[str, Any], dec: int) -> str:
    unit = s.get("native_unit")

    def one(kind: str) -> str:
        nat = s.get(f"{kind}_native")
        extra = f" (~{vn_native(nat, unit)} {unit})" if unit and nat is not None else ""
        return f"{vn(s[kind], dec)} USD/tấn{extra} ngày {s[f'{kind}_date']} (Tuần {s[f'{kind}_week_no']})"

    name = " ".join(x for x in (s.get("exchange"), s["grade"]) if x)
    no_fx = s.get("no_fx_dates") or []
    note = (f" — chỉ tính ngày quy đổi được USD; ngày {', '.join(no_fx)} có giá nội tệ nhưng thiếu tỷ giá "
            "(vẫn giao dịch, KHÔNG phải nghỉ)" if no_fx else "")
    return f"- {name}: Cao nhất {one('high')}; Thấp nhất {one('low')}{note}"


# ── Các khối ──
def _period_block(rep: dict[str, Any]) -> list[str]:
    weeks = rep["weeks"]
    cols = " · ".join(f"{w['short']} = {w['label']}" + (" [tuần mốc so sánh]" if i == 0 else "")
                      for i, w in enumerate(weeks))
    return [f"KỲ BÁO CÁO: {rep['title_label']} ({rep['date_range']}) — gộp {rep['span_weeks']} tuần.",
            f"Cột tuần: {cols}.",
            f"Phần I tóm tắt {rep['prev_label']}; Phần II diễn biến {rep['movement_label']}; "
            f"Phần V dự báo {rep['next_label']}."]


def _tables_block(rep: dict[str, Any]) -> list[str]:
    w = rep["weeks"]
    out = ["III.1 GIÁ SÀN QUỐC TẾ — trung bình tuần (USD/tấn; phiên giá 0 = nghỉ giao dịch và ngày thiếu tỷ "
           "giá đều không vào TB):",
           *_row_lines(rep["exchange_rows"], w)]
    out += [f"Ghi chú dưới bảng (không có giá / thiếu tỷ giá): {g}" for g in rep.get("exchange_gaps") or []]
    out += ["Cao/thấp CẢ KỲ theo sàn (tính từ dữ liệu — dùng đúng số và ngày này):",
            *[_stat_line(s, 1) for s in rep.get("range_stats") or []]]
    out += ["III.2 GIÁ GIAO NGAY — trung bình tuần (USD/tấn):", *_row_lines(rep["physical_rows"], w)]
    out += [f"Ghi chú dưới bảng: {g}" for g in rep.get("physical_gaps") or []]
    out += ["Cao/thấp CẢ KỲ giao ngay:", *[_stat_line(s, 2) for s in rep.get("physical_range_stats") or []]]
    bands = " · ".join(f"{wk['short']}: {b or 'N/A'}" for wk, b in zip(w, rep.get("latex_bands") or []))
    chg = " · ".join(f"{w[i + 1]['short']}/{w[i]['short']}: {c or 'N/A'}"
                     for i, c in enumerate(rep.get("latex_changes") or []))
    out.append(f"III.3 MỦ NƯỚC NỘI ĐỊA (VNĐ/độ TSC) — biên độ theo tuần: {bands} | thay đổi min/max: {chg}")
    return out


def _daily_block(rep: dict[str, Any]) -> list[str]:
    per = weekly_period.period(rep["week_key"], rep["span_weeks"])
    market = tables.load_market(per)
    lo, hi = per["span_from"], per["date_to"]
    out = ["GIÁ TỪNG PHIÊN TRONG KỲ (USD/tấn; 'nghỉ' = không có giá; 'thiếu tỷ giá' = sàn VẪN giao dịch, có giá "
           "nội tệ nhưng chưa quy đổi được USD — không phải nghỉ) — để nhận diện hình thái đầu/cuối tuần:"]
    for exc, grade, key in tables.EXCHANGE_MAP:
        cells = market["exchange"].get(key, {})
        days = sorted(d for d in cells if lo <= d <= hi)
        pts = [f"{int(d[8:10])}/{int(d[5:7])} " + _session(cells[d]) for d in days]
        if pts:
            out.append(f"- {exc} {grade}: " + " · ".join(pts))
    return out if len(out) > 1 else []


def _session(cell: dict[str, Any]) -> str:
    state = day_state(cell)
    return vn(cell.get("usd")) if state is None else ("thiếu tỷ giá" if state == NO_FX else "nghỉ")


def _fx_block(rep: dict[str, Any]) -> list[str]:
    rows = rep.get("fx_rows") or []
    if not rows:
        return []
    weeks = rep["weeks"]
    moves = []
    for i in range(len(weeks) - 1):  # diễn giải sẵn chiều đồng nội tệ — AI hay đọc ngược USD/JPY
        parts = [f"{_FX_CURRENCY[r['pair']]} {'yếu đi' if p > 0 else 'mạnh lên'}" for r in rows
                 if r["pair"] in _FX_CURRENCY and i < len(r["changes_pct"])
                 and (p := r["changes_pct"][i]) is not None and p != 0]
        if parts:
            moves.append(f"{weeks[i + 1]['short']}/{weeks[i]['short']}: {', '.join(parts)}")
    return ["TỶ GIÁ HỆ THỐNG — trung bình tuần:",
            *[_series(r["pair"], weeks, r["values"], r["changes"], r["changes_pct"],
                      _FX_DEC.get(r["pair"], 2)) for r in rows], _FX_LOGIC,
            *([f"Chiều đồng nội tệ so với USD: {' · '.join(moves)}."] if moves else [])]


def _indicators_block(rep: dict[str, Any], urls: list[str]) -> list[str]:
    from app.services import weekly_market_feed

    items = weekly_market_feed.weekly_indicators(rep["weeks"])
    if not items:
        return []
    out = ["CHỈ SỐ TÀI CHÍNH & NĂNG LƯỢNG (nguồn CNBC/Yahoo Finance, giá đóng cửa ngày) — nguồn DUY NHẤT cho số DXY/dầu:"]
    for it in items:
        name = f"{it['name']} (mã {it['symbol']} — {it.get('role') or ''})"
        if it.get("error") or not any(v is not None for v in it.get("values") or []):
            out.append(f"- {name}: chưa lấy được số liệu kỳ này — KHÔNG nêu con số của chỉ số này.")
            continue
        line = _series(name, rep["weeks"], it["values"], it["changes"], it["changes_pct"], 2)
        closes = " · ".join(f"{w['short']} {vn(c, 2)}" for w, c in zip(rep["weeks"], it.get("last_closes") or []))
        hi, lo = it.get("high"), it.get("low")
        ext = (f"; cao nhất kỳ {vn(hi['value'], 2)} ({hi['date']}), thấp nhất kỳ {vn(lo['value'], 2)} ({lo['date']})"
               if hi and lo else "")
        out.append(f"{line} | giá chốt tuần: {closes}{ext}")
        urls.append(f"https://finance.yahoo.com/quote/{it['symbol']}")
    return out


def _base_week_block(rep: dict[str, Any]) -> list[str]:
    base_mon = date.fromisoformat(rep["weeks"][0]["mon"])
    out: list[str] = []
    for back in range(weekly_period.MAX_SPAN):  # báo cáo đã lưu có kỳ PHỦ tuần mốc
        key = (base_mon - timedelta(days=7 * back)).isoformat()
        saved = weekly_report_service.load_saved(key)
        if saved and weekly_period.clamp_span(saved.get("span_weeks", 1)) > back and saved.get("movement"):
            label = weekly_period.period(key, saved.get("span_weeks", 1))["movement_label"]
            out += [f"PHẦN II ĐÃ LƯU CỦA BÁO CÁO {label} (hệ quy chiếu cho Phần I):",
                    *[strip_delimiters(x) for x in saved["movement"]]]
            break
    per = weekly_period.period(base_mon.isoformat(), 1)
    market = tables.load_market(per)
    out += [f"BẢNG TUẦN MỐC {per['movement_label']} so với tuần trước nó (TB tuần USD/tấn):",
            *_row_lines(tables.exchange_rows(market, per["weeks"]), per["weeks"]),
            *_row_lines(tables.physical_rows(market, per["weeks"]), per["weeks"])]
    return out


def _docs_block(rep: dict[str, Any]) -> list[str]:
    from app.services import weekly_attachment_service

    out = []
    for d in weekly_attachment_service.context_documents(rep["week_key"], max_chars=DOCS_MAX_CHARS):
        used = "bản tóm tắt" if d["used"] == "summary" else "chữ trích từ file"
        out += [f"{DOCS_HEADER}{d['id']} — {strip_delimiters(d['filename'])} — {d['kind']} ({used}):",
                '"""', strip_delimiters(d["content"]), '"""']
    return out


def _news_block(rep: dict[str, Any], urls: list[str]) -> list[str]:
    from app.services import weekly_news, weekly_source_repo

    index = next((s["url"] for s in weekly_source_repo.list_sources(enabled_only=True)
                  if s["mode"] == "vietnambiz" and s.get("url")), _DEFAULT_NEWS_INDEX)
    weeks = rep["weeks"]
    arts = weekly_news.fetch_period_articles(
        index, date.fromisoformat(weeks[0]["mon"]), date.fromisoformat(weeks[-1]["fri"]),
        max_articles=min(_NEWS_PER_WEEK * len(weeks), _NEWS_MAX_ARTICLES))
    if not arts:
        return []
    cap = min(1800, NEWS_MAX_CHARS // len(arts))
    out = ["TIN VIETNAMBIZ 'Giá cao su hôm nay' ĐĂNG TRONG KỲ (gồm tuần mốc) — nguồn DUY NHẤT cho sự kiện:"]
    for a in arts:
        wk = next((w["short"] for w in weeks if w["mon"] <= a["published"] <= _sunday(w)), "")
        out += [f"[{a['published']} · {wk}] {strip_delimiters(a['title'])}", strip_delimiters(a["body"][:cap])]
        urls.append(a["url"])
    return out


def _sunday(week: dict[str, Any]) -> str:
    """Bài thứ Bảy/Chủ nhật (tổng kết phiên cuối tuần) thuộc tuần đó."""
    return (date.fromisoformat(week["mon"]) + timedelta(days=6)).isoformat()


def _sources_block(rep: dict[str, Any], section_keys: list[str] | None) -> list[str]:
    """Mã IV.k của nguồn (bố cục mặc định) đổi sang nhãn tiểu mục thật theo chủ đề tiêu đề của báo cáo."""
    from app.services import weekly_source_repo

    code_map = source_code_map(macro_titles(rep))
    out = []
    for s in weekly_source_repo.list_sources(enabled_only=True):
        labels = dict.fromkeys(code_map.get(k, k) for k in s.get("sections") or [])
        keys = [k for k in labels if section_keys is None or k in section_keys]
        if keys and s.get("guide") and s.get("mode") != "manual":  # link chuyên viên tự đọc → AI không có nội dung
            guide = strip_delimiters((s.get("guide") or "").replace("\n", " ")[:GUIDE_MAX_CHARS])
            out.append(f"- [{', '.join(keys)}] {strip_delimiters(s['name'])} — {strip_delimiters(s.get('role'))}: {guide}")
    return (["GÓC PHÂN TÍCH GỢI Ý theo mục (danh mục nguồn đã cấu hình — chỉ là hướng phân tích, KHÔNG phải "
             "số liệu hay tin đã xảy ra):",
             *out] if out else [])


def _safe(name: str, fn: Callable[..., list[str]], *args: Any) -> list[str]:
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 - thiếu 1 khối không làm hỏng cả lượt AI
        logger.warning("[weekly-ai] Bỏ khối ngữ cảnh %s: %s", name, exc)
        return []


def run_blocks(jobs: list[tuple], deadline_s: float) -> list[list[str]]:
    """Chạy các khối song song, chờ TỔNG tối đa `deadline_s` giây; khối quá hạn → [] (ghi log). Không dùng
    `with ThreadPoolExecutor` — thoát `with` sẽ chờ luồng treo chạy xong, mất tác dụng của hạn."""
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        futures = [pool.submit(_safe, *job) for job in jobs]
        wait(futures, timeout=deadline_s)
        blocks = []
        for job, f in zip(jobs, futures):
            if f.done():
                blocks.append(f.result())
            else:
                logger.warning("[weekly-ai] Bỏ khối ngữ cảnh %s: quá hạn %ss", job[0], deadline_s)
                blocks.append([])
        return blocks
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def build_context(week_key: str, rep: dict[str, Any] | None = None,
                  section_keys: list[str] | None = None) -> tuple[str, list[str]]:
    """(văn bản ngữ cảnh, danh sách URL nguồn). `section_keys` lọc góc phân tích gợi ý (None = mọi mục)."""
    rep = rep or weekly_report_service.build_report(week_key)
    news_urls: list[str] = []
    feed_urls: list[str] = []
    jobs = [("kỳ", _period_block, rep), ("bảng", _tables_block, rep), ("giá phiên", _daily_block, rep),
            ("tỷ giá", _fx_block, rep), ("chỉ số", _indicators_block, rep, feed_urls),
            ("tuần mốc", _base_week_block, rep), ("đính kèm", _docs_block, rep),
            ("tin", _news_block, rep, news_urls), ("nguồn", _sources_block, rep, section_keys)]
    blocks = run_blocks(jobs, BLOCKS_DEADLINE_S)
    text = "\n\n".join("\n".join(b) for b in blocks if b)
    return text, list(dict.fromkeys(news_urls + feed_urls))
