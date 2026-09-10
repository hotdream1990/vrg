"""Gói "Thị trường thế giới" — sàn quốc tế · giá physical · tỷ giá · diễn biến.

Đây là nhóm dữ liệu dẫn dắt điều chỉnh giá sàn mạnh nhất (đo trên 80 lần ban hành 2024→2026:
MRB SMR20 r=0,63 · SGX TSR20 r=0,58 · Physical SMR20 r=0,50 trên biến động giữa 2 lần) —
xem `docs/project/tro-ly-ai-kha-nang.md`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.core.market_meta import FX_PAIRS
from app.services import price_repo
from app.services.assistant_tools._common import (
    EXCH, NO_ARGS, NO_TRADING, clamp_days, cols, days_ago, dm, dmy, err, is_no_trading, line,
    pct, source_key, table, today,
)


def _exchange_prices(_: dict) -> dict:
    """Ảnh chụp giá mới nhất của 5 sàn quốc tế, theo đơn vị gốc của từng sàn."""
    rows = sorted((r for r in price_repo.latest() if r["source"] in EXCH),
                  key=lambda r: (r["source"], r["grade"]))
    # Giá 0 = phiên sàn không giao dịch. Đưa số 0 cho LLM đọc là nó kết luận "giá sụp về 0".
    out = [{"san": EXCH.get(r["source"], r["source"]), "grade": r["grade"],
            "gia": NO_TRADING if is_no_trading(r["price"]) else r["price"],
            "don_vi": "" if is_no_trading(r["price"]) else r["unit"],
            "ngay": dm(r["as_of"])} for r in rows]
    if not out:
        return err("Chưa có dữ liệu giá sàn quốc tế.")
    art = table("Giá các sàn quốc tế (mới nhất)",
                cols(("san", "Sàn"), ("grade", "Chủng loại"), ("gia", "Giá"),
                     ("don_vi", "Đơn vị"), ("ngay", "Ngày")), out)
    return {"summary": {"count": len(out), "prices": out}, "artifact": art,
            "source": "fact_price · giá sàn quốc tế mới nhất"}


def _price_trend(args: dict) -> dict:
    """Diễn biến 1 sàn + 1 chủng loại theo N ngày."""
    source = source_key(args.get("source", ""))   # "ose"/"jpx" → "tocom" …
    grade = str(args.get("grade", "")).strip()
    days = clamp_days(args.get("days"), 30)
    # Hỏi ĐÚNG một ngày trong quá khứ: tự nới cửa sổ cho phủ ngày đó, nếu không sẽ trả "chưa có
    # số liệu" chỉ vì cửa sổ mặc định 30 ngày không chạm tới nó.
    on_date = str(args.get("on_date") or "").strip()[:10]
    if on_date:
        try:
            gap = (date.fromisoformat(today()) - date.fromisoformat(on_date)).days
            days = max(days, gap + 3)
        except ValueError:
            return err(f"Ngày '{on_date}' không hợp lệ (định dạng YYYY-MM-DD).")
    hist = price_repo.history(source, grade, days=days)
    # `history` cố ý bỏ phiên giá 0 (No Trading) để biểu đồ không có cú rơi thẳng đứng. Nhưng bỏ
    # hẳn thì hỏi đúng ngày sàn nghỉ lại bị trả lời "chưa có số liệu" — sai bản chất. Nên lấy
    # riêng danh sách phiên nghỉ để nói rõ ra.
    closed = [dmy(r["as_of"]) for r in price_repo.prices_since([source], days=days)
              if r["grade"] == grade and is_no_trading(r["price"])]
    if not hist:
        if closed:
            return err(f"Trong {days} ngày qua, {grade} trên {EXCH.get(source, source)} KHÔNG GIAO "
                       f"DỊCH ở các phiên: {', '.join(closed)} — không có mức giá nào để vẽ.")
        return err(f"Không có dữ liệu cho {source}/{grade} trong {days} ngày.")
    labels = [dm(h["as_of"]) for h in hist]
    values = [round(float(h["price"]), 2) for h in hist]
    first, last = values[0], values[-1]
    art = line(f"Diễn biến {grade} · {EXCH.get(source, source)} ({days} ngày)",
               labels, [{"name": grade, "values": values}])
    return {"summary": {"source": source, "grade": grade, "n": len(values), "first": first,
                        "last": last, "change": round(last - first, 2),
                        "change_pct": pct(last, first),
                        "tu_ngay": dmy(hist[0]["as_of"]), "den_ngay": dmy(hist[-1]["as_of"]),
                        # Nói rõ phiên sàn nghỉ thay vì im lặng bỏ qua — người hỏi đúng ngày đó
                        # phải nhận được câu "hôm ấy không giao dịch", không phải "chưa có số liệu".
                        "phien_khong_giao_dich": closed or None,
                        **({"gia_ngay_hoi": _on_date_answer(hist, closed, on_date)} if on_date else {})},
            "artifact": art, "source": f"fact_price · {source}/{grade} · {len(values)} phiên"}


def _on_date_answer(hist: list[dict], closed: list[str], on_date: str) -> str | float:
    """Trả lời cho câu hỏi về ĐÚNG một ngày: mức giá · 'No Trading' · hay không có bản ghi."""
    for h in hist:
        if str(h["as_of"])[:10] == on_date:
            return round(float(h["price"]), 2)
    if dmy(on_date) in closed:
        return f"{NO_TRADING} — phiên {dmy(on_date)} sàn không giao dịch"
    return f"Không có bản ghi nào cho ngày {dmy(on_date)}"


def _fx_rates(args: dict) -> dict:
    """Tỷ giá mới nhất 6 cặp + (tuỳ chọn) diễn biến 1 cặp.

    Bắt buộc có khi nói về giá sàn NỘI ĐỊA: giá nội địa quy đổi trực tiếp từ FOB qua USD/VND,
    nên trả lời giá nội địa mà không kèm tỷ giá là trả lời thiếu.
    """
    pair = str(args.get("pair", "")).strip()
    days = clamp_days(args.get("days"), 30)
    if pair:
        hist = price_repo.history("fx", pair, days=days)
        if not hist:
            return err(f"Không có dữ liệu tỷ giá {pair} trong {days} ngày.")
        values = [round(float(h["price"]), 4) for h in hist]
        art = line(f"Diễn biến tỷ giá {pair} ({days} ngày)", [dm(h["as_of"]) for h in hist],
                   [{"name": pair, "values": values}])
        return {"summary": {"pair": pair, "n": len(values), "first": values[0], "last": values[-1],
                            "change_pct": pct(values[-1], values[0]),
                            "den_ngay": dmy(hist[-1]["as_of"])},
                "artifact": art, "source": f"fact_price · tỷ giá {pair} · {len(values)} phiên"}

    latest = {r["grade"]: r for r in price_repo.latest() if r["source"] == "fx"}
    out = [{"cap": g, "ty_gia": round(float(latest[g]["price"]), 4), "ngay": dm(latest[g]["as_of"])}
           for g in FX_PAIRS if g in latest]
    out += [{"cap": g, "ty_gia": round(float(r["price"]), 4), "ngay": dm(r["as_of"])}
            for g, r in sorted(latest.items()) if g not in FX_PAIRS]
    if not out:
        return err("Chưa có dữ liệu tỷ giá.")
    art = table("Tỷ giá mới nhất", cols(("cap", "Cặp tiền"), ("ty_gia", "Tỷ giá"), ("ngay", "Ngày")), out)
    return {"summary": {"rates": out}, "artifact": art, "source": "fact_price · tỷ giá mới nhất"}


def _physical_prices(args: dict) -> dict:
    """Giá physical (giao ngay) châu Á đã quy USD/tấn — nền so sánh của giá sàn FOB."""
    days = clamp_days(args.get("days"), 14)
    # Giới hạn khoảng lấy: `physical_sheet()` không tham số sẽ quét TOÀN BỘ lịch sử (hàng nghìn
    # dòng) chỉ để lấy vài phiên gần nhất. Nới rộng gấp 3 vì có ngày nghỉ/không có bản ghi.
    sheet = price_repo.physical_sheet(date_from=days_ago(days * 3))
    dates: list[str] = (sheet.get("dates") or [])[:days]   # đã sort giảm dần
    grades: list[str] = sheet.get("grades") or []
    if not dates or not grades:
        return err("Chưa có dữ liệu giá physical.")
    values = sheet["values"]
    newest = dates[0]
    prev = dates[1] if len(dates) > 1 else None
    out: list[dict[str, Any]] = []
    for g in grades:
        cur = values.get(g, {}).get(newest)
        old = values.get(g, {}).get(prev) if prev else None
        out.append({"grade": g, "gia_usd_tan": cur, "phien_truoc": old,
                    "thay_doi_pct": pct(cur, old)})
    art = table(f"Giá physical châu Á · USD/tấn ({dmy(newest)})",
                cols(("grade", "Chủng loại"), ("gia_usd_tan", "Giá (USD/tấn)"),
                     ("phien_truoc", "Phiên trước"), ("thay_doi_pct", "Thay đổi %")), out)
    return {"summary": {"as_of": newest, "prev": prev, "don_vi": "USD/tấn", "items": out},
            "artifact": art, "source": f"fact_price · physical (Reuters) · {dmy(newest)}"}


TOOLS: dict[str, dict[str, Any]] = {
    "get_exchange_prices": {
        "run": _exchange_prices,
        "schema": {"name": "get_exchange_prices",
                   "description": "Giá MỚI NHẤT các sàn cao su quốc tế (OSE, SHFE, SGX, TOCOM, MRB/LGM) — bảng ảnh chụp theo đơn vị gốc của từng sàn (JPY/kg, CNY/tấn, US cents/kg, Sen/kg). Giá ghi 'No Trading' nghĩa là phiên đó sàn không giao dịch, KHÔNG phải giá bằng 0.",
                   "parameters": NO_ARGS}},
    "get_price_trend": {
        "run": _price_trend,
        "schema": {"name": "get_price_trend",
                   "description": "Diễn biến giá 1 sàn + 1 chủng loại theo N ngày (biểu đồ đường) kèm % thay đổi và danh sách phiên KHÔNG GIAO DỊCH (No Trading) nếu có. source ∈ {ose, shfe, sgx, tocom, lgm}; grade ví dụ 'RSS3','TSR20','SMR20','SMRCV','LATEX','RU'.",
                   "parameters": {"type": "object", "properties": {
                       "source": {"type": "string", "description": "mã sàn: ose/shfe/sgx/tocom/lgm"},
                       "grade": {"type": "string", "description": "chủng loại, vd RSS3, TSR20, SMR20"},
                       "days": {"type": "integer", "description": "số ngày (mặc định 30)"},
                       "on_date": {"type": "string", "description": "hỏi ĐÚNG một ngày quá khứ (YYYY-MM-DD) — tool tự nới cửa sổ và trả mức giá ngày đó, hoặc báo phiên đó sàn không giao dịch"}},
                       "required": ["source", "grade"]}}},
    "get_fx_rates": {
        "run": _fx_rates,
        "schema": {"name": "get_fx_rates",
                   "description": "Tỷ giá mới nhất (USD/VND mua-bán, USD/JPY, USD/CNY, USD/MYR, USD/THB); truyền `pair` để xem diễn biến N ngày của 1 cặp. BẮT BUỘC gọi khi nói về giá sàn NỘI ĐỊA (VNĐ/tấn) vì giá nội địa quy đổi từ FOB qua tỷ giá.",
                   "parameters": {"type": "object", "properties": {
                       "pair": {"type": "string", "description": "cặp tiền, vd 'USD/VND (Bán)', 'USD/JPY' — bỏ trống để lấy bảng tất cả"},
                       "days": {"type": "integer", "description": "số ngày khi xem diễn biến (mặc định 30)"}}}}},
    "get_physical_prices": {
        "run": _physical_prices,
        "schema": {"name": "get_physical_prices",
                   "description": "Giá PHYSICAL (giao ngay, nguồn Reuters) châu Á quy USD/tấn: RSS3, STR20, SMR20, SIR20, Thai Latex 60% Bulk/Drums — kèm phiên trước và % thay đổi. Đây là nền so sánh trực tiếp với giá sàn FOB của Tập đoàn.",
                   "parameters": {"type": "object", "properties": {
                       "days": {"type": "integer", "description": "số phiên gần nhất lấy về (mặc định 14)"}}}}},
}
