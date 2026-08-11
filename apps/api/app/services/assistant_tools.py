"""Bộ công cụ (tool) cho Trợ lý AI — bọc các hàm lấy SỐ LIỆU THẬT trong DB.

Mỗi tool: {name, description, parameters (JSON schema), run(args)->{summary, artifact?, source?}}.
`summary` = dữ liệu gọn cho LLM đọc (không bịa); `artifact` = bảng/biểu đồ cho frontend hiển thị.
LLM gọi tool qua OpenAI function-calling; xem `assistant_service`.
"""
from __future__ import annotations

import sys
from typing import Any, Callable

from app.core import edit_window
from app.core.paths import bulletin_dir
from app.services import (
    floor_repo, floor_suggest, inventory_repo, market_quote_repo, price_repo,
)

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import NO_TRADING, is_no_trading  # noqa: E402 - quy ước giá 0 dùng chung

# ── Helpers dựng artifact ──
def _table(title: str, columns: list[dict], rows: list[dict]) -> dict:
    return {"type": "table", "title": title, "columns": columns, "rows": rows}


def _line(title: str, labels: list[str], series: list[dict], y_label: str = "") -> dict:
    return {"type": "line", "title": title, "labels": labels, "series": series, "y_label": y_label}


def _dm(iso: str) -> str:
    p = str(iso)[:10].split("-")
    return f"{p[2]}/{p[1]}" if len(p) == 3 else str(iso)


def _today() -> str:
    return edit_window.today().isoformat()


# ── Danh mục nguồn sàn quốc tế (để mô tả cho LLM + lọc) ──
EXCH = {"ose": "OSE (Nhật)", "shfe": "SHFE (Thượng Hải)", "sgx": "SGX (Singapore)",
        "tocom": "TOCOM (Nhật)", "lgm": "MRB/LGM (Malaysia)"}


# ── Các tool ──
def _exchange_prices(_: dict) -> dict:
    rows = [r for r in price_repo.latest() if r["source"] in EXCH]
    rows.sort(key=lambda r: (r["source"], r["grade"]))
    # Giá 0 = phiên đó sàn không giao dịch → nói rõ "No Trading", đừng đưa số 0 cho LLM đọc
    # thành "giá 0" rồi kết luận thị trường sụp.
    out = [{"san": EXCH.get(r["source"], r["source"]), "grade": r["grade"],
            "gia": NO_TRADING if is_no_trading(r["price"]) else r["price"],
            "don_vi": "" if is_no_trading(r["price"]) else r["unit"],
            "ngay": _dm(r["as_of"])} for r in rows]
    art = _table("Giá các sàn quốc tế (mới nhất)", [
        {"key": "san", "label": "Sàn"}, {"key": "grade", "label": "Chủng loại"},
        {"key": "gia", "label": "Giá"}, {"key": "don_vi", "label": "Đơn vị"},
        {"key": "ngay", "label": "Ngày"}], out) if out else None
    return {"summary": {"count": len(out), "prices": out}, "artifact": art, "source": "fact_price · giá sàn quốc tế mới nhất"}


def _price_trend(args: dict) -> dict:
    source = str(args.get("source", "")).lower().strip()
    grade = str(args.get("grade", "")).strip()
    days = int(args.get("days", 30) or 30)
    hist = price_repo.history(source, grade, days=days)
    if not hist:
        return {"summary": {"error": f"Không có dữ liệu cho {source}/{grade} trong {days} ngày."}}
    labels = [_dm(h["as_of"]) for h in hist]
    values = [round(float(h["price"]), 2) for h in hist]
    first, last = values[0], values[-1]
    art = _line(f"Diễn biến {grade} · {EXCH.get(source, source)} ({days} ngày)",
                labels, [{"name": f"{grade}", "values": values}])
    return {"summary": {"source": source, "grade": grade, "n": len(values), "first": first,
                        "last": last, "change": round(last - first, 2),
                        "change_pct": round((last - first) / first * 100, 2) if first else None},
            "artifact": art, "source": f"fact_price · {source}/{grade} · {len(values)} phiên"}


def _floor_prices(_: dict) -> dict:
    sched = floor_repo.list_schedules()
    if not sched:
        return {"summary": {"error": "Chưa có biểu giá sàn nào."}}
    latest = sched[0]
    full = floor_repo.get_schedule(int(latest["lan"])) or {}
    items = full.get("items", [])
    out = [{"grade": it["grade"], "fob_usd": it.get("fob_usd"), "domestic_vnd": it.get("domestic_vnd")}
           for it in items]
    art = _table(f"Giá sàn hiện hành · {full.get('title', '')} ({_dm(full.get('as_of', ''))})", [
        {"key": "grade", "label": "Chủng loại"}, {"key": "fob_usd", "label": "FOB (USD/tấn)"},
        {"key": "domestic_vnd", "label": "Nội địa (VNĐ/tấn)"}], out) if out else None
    return {"summary": {"title": full.get("title"), "as_of": full.get("as_of"),
                        "dispatch_no": full.get("dispatch_no"), "items": out},
            "artifact": art, "source": f"vrg_floor_price · {full.get('title', '')}"}


_ACTION = {"raise": "NÂNG", "lower": "HẠ", "hold": "GIỮ"}


def _suggest_floor(args: dict) -> dict:
    as_of = str(args.get("as_of") or _today())
    try:
        s = floor_suggest.suggest(as_of)
    except Exception as exc:  # noqa: BLE001
        return {"summary": {"error": f"Không tính được gợi ý: {exc}"}}
    if s.get("error"):
        return {"summary": {"error": s["error"]}}
    items = s.get("items", [])
    out = [{"grade": it["grade"], "hien_tai": it.get("prev"), "de_xuat": it.get("suggested"),
            "hanh_dong": _ACTION.get(it.get("action"), it.get("action")), "delta": it.get("delta"),
            "delta_pct": it.get("delta_pct"), "do_tin_cay": it.get("confidence")}
           for it in items if it.get("suggested") is not None]
    art = _table(f"Gợi ý điều chỉnh giá sàn ({_dm(as_of)})", [
        {"key": "grade", "label": "Chủng loại"}, {"key": "hien_tai", "label": "Giá hiện tại"},
        {"key": "de_xuat", "label": "Đề xuất"}, {"key": "hanh_dong", "label": "Hành động"},
        {"key": "delta", "label": "Δ"}, {"key": "delta_pct", "label": "Δ%"},
        {"key": "do_tin_cay", "label": "Độ tin cậy"}], out) if out else None
    drivers = [{"chi_so": d["index"], "thay_doi_pct": d["change_pct"]} for d in s.get("drivers", [])]
    return {"summary": {"as_of": as_of, "basket_change_pct": s.get("basket_change_pct"),
                        "drivers": drivers, "items": out, "note": "Đề xuất từ mô hình hồi quy giá sàn theo rổ chỉ số; dead-band = MAE backtest (|Δ| nhỏ ⇒ GIỮ)."},
            "artifact": art, "source": f"engine gợi ý giá sàn · {_dm(as_of)}"}


def _inventory_trend(args: dict) -> dict:
    weeks = int(args.get("weeks", 26) or 26)
    ser = list(reversed(inventory_repo.series(limit=weeks)))
    if not ser:
        return {"summary": {"error": "Chưa có dữ liệu tồn kho."}}
    labels = [_dm(r["as_of"]) for r in ser]
    tk = [r.get("ton_kho") for r in ser]
    hd = [r.get("ton_kho_hd") for r in ser]
    art = _line(f"Tồn kho thành phẩm theo tuần ({len(ser)} tuần)", labels,
                [{"name": "Tồn kho", "values": tk}, {"name": "Đã có HĐ", "values": hd}], "tấn")
    last = ser[-1]
    return {"summary": {"latest_week": last["as_of"], "ton_kho": last.get("ton_kho"),
                        "ton_kho_da_co_hd": last.get("ton_kho_hd"), "n_weeks": len(ser)},
            "artifact": art, "source": f"fact_inventory · {len(ser)} tuần"}


def _market_quote(_: dict) -> dict:
    lst = market_quote_repo.list_quotes()
    if not lst:
        return {"summary": {"error": "Chưa có phiếu báo giá mủ thị trường nào."}}
    q = market_quote_repo.get_quote(lst[0]["as_of"]) or {}
    prices = (q.get("export_vrg") or {}).get("prices") or {}
    out = [{"grade": g, "gia": v} for g, v in prices.items()]
    art = _table(f"Báo giá mủ xuất khẩu (VRG) · {_dm(lst[0]['as_of'])}", [
        {"key": "grade", "label": "Chủng loại"}, {"key": "gia", "label": "Đơn giá (USD/tấn)"}], out) if out else None
    return {"summary": {"as_of": lst[0]["as_of"], "export_vrg_prices": prices},
            "artifact": art, "source": f"market_quote · {_dm(lst[0]['as_of'])}"}


# ── Registry ──
_S = {"type": "object", "properties": {}}
TOOLS: dict[str, dict[str, Any]] = {
    "get_exchange_prices": {
        "run": _exchange_prices,
        "schema": {"name": "get_exchange_prices",
                   "description": "Giá MỚI NHẤT các sàn cao su quốc tế (OSE, SHFE, SGX, TOCOM, MRB/LGM) — trả bảng snapshot theo đơn vị gốc của từng sàn.",
                   "parameters": _S}},
    "get_price_trend": {
        "run": _price_trend,
        "schema": {"name": "get_price_trend",
                   "description": "Diễn biến giá 1 sàn + 1 chủng loại theo N ngày (biểu đồ đường). source ∈ {ose, shfe, sgx, tocom, lgm}; grade ví dụ 'RSS3','TSR20','SMR20','LATEX'.",
                   "parameters": {"type": "object", "properties": {
                       "source": {"type": "string", "description": "mã sàn: ose/shfe/sgx/tocom/lgm"},
                       "grade": {"type": "string", "description": "chủng loại, vd RSS3, TSR20"},
                       "days": {"type": "integer", "description": "số ngày (mặc định 30)"}},
                       "required": ["source", "grade"]}}},
    "get_floor_prices": {
        "run": _floor_prices,
        "schema": {"name": "get_floor_prices",
                   "description": "Giá sàn Tập đoàn HIỆN HÀNH (lần ban hành mới nhất) theo từng chủng loại — FOB USD/tấn và giá nội địa VNĐ/tấn.",
                   "parameters": _S}},
    "suggest_floor_adjustment": {
        "run": _suggest_floor,
        "schema": {"name": "suggest_floor_adjustment",
                   "description": "TƯ VẤN nên NÂNG/GIỮ/HẠ giá sàn cho từng chủng loại, kèm mức đề xuất, Δ so lần trước, độ tin cậy và các chỉ số dẫn hướng (drivers). Dùng khi người dùng hỏi về điều chỉnh/khuyến nghị giá sàn. as_of tùy chọn (mặc định hôm nay).",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"}}}}},
    "get_inventory_trend": {
        "run": _inventory_trend,
        "schema": {"name": "get_inventory_trend",
                   "description": "Tồn kho thành phẩm theo tuần (biểu đồ đường: tồn kho & đã có hợp đồng). weeks = số tuần gần nhất (mặc định 26).",
                   "parameters": {"type": "object", "properties": {
                       "weeks": {"type": "integer", "description": "số tuần (mặc định 26)"}}}}},
    "get_market_quote": {
        "run": _market_quote,
        "schema": {"name": "get_market_quote",
                   "description": "Báo giá mủ thị trường MỚI NHẤT (giá xuất khẩu SVR của VRG theo chủng loại).",
                   "parameters": _S}},
}


def openai_tools() -> list[dict]:
    """Danh sách schema tool cho OpenAI function-calling."""
    return [{"type": "function", "function": t["schema"]} for t in TOOLS.values()]


def run_tool(name: str, args: dict) -> dict:
    """Thực thi 1 tool theo tên; trả {summary, artifact?, source?}. Tên lạ → báo lỗi gọn."""
    tool = TOOLS.get(name)
    if not tool:
        return {"summary": {"error": f"Không có công cụ '{name}'."}}
    fn: Callable = tool["run"]
    try:
        return fn(args or {})
    except Exception as exc:  # noqa: BLE001
        return {"summary": {"error": f"Lỗi khi chạy '{name}': {exc}"}}
