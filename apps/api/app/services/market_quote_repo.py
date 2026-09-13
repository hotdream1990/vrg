"""Repository Báo giá mủ thị trường (market_quote) — 1 phiếu/ngày (nhập tay).

Payload jsonb giữ tỷ giá VCB + Mục 1-4 (giá SVR + bao bì + vận chuyển + tình trạng + ghi chú) +
Mục 5 (đề xuất mua từ khách hàng) + Mục 6 (giá mủ tư nhân theo danh mục đơn vị tư nhân).
Mục 1-4 còn được mirror sang fact_price source=market để dùng như chuỗi thời gian cho Bản tin/dự báo.

Mục "Giá mủ khu vực" (mủ nước/mủ chén theo đơn vị thành viên, ghi thẳng kho Giá mủ nguyên liệu) đã
BỎ khỏi phiếu 13/09/2026 — số đó nay lấy trực tiếp từ đơn vị.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from app.core import request_ctx
from app.core.db import ensure_schema, session_scope
from app.core.market_meta import MARKET_QUOTE_GRADES
from app.services import audit_repo, market_private_unit_repo, price_repo

_MARKET = "market"
# section key → (price_type, currency, unit) khi mirror sang fact_price source=market
_SECTION_MODES = {
    "domestic_private": ("market_domestic_private", "VND", "đồng/tấn"),
    "domestic_export": ("market_domestic_export", "VND", "đồng/tấn"),
    "export_vrg": ("market_export_vrg", "USD", "USD/tấn"),
    "domestic_vrg": ("market_domestic_vrg", "VND", "đồng/tấn"),
}


def meta() -> dict[str, Any]:
    """Chủng loại SVR + gợi ý bao bì (Mục 1-4) + danh mục đơn vị tư nhân (Mục 6)."""
    from app.core.market_meta import MARKET_QUOTE_PACKAGING

    return {"grades": MARKET_QUOTE_GRADES, "packaging": MARKET_QUOTE_PACKAGING,
            "private_units": market_private_unit_repo.list_units()}


# price_type mirror → (section key, nhãn, đơn vị) cho biểu đồ lịch sử
_HISTORY_SECTIONS = [
    ("market_domestic_private", "domestic_private", "Giá nội địa — tư nhân", "VNĐ/tấn"),
    ("market_domestic_export", "domestic_export", "Giá xuất khẩu — hàng tư nhân", "VNĐ/tấn"),
    ("market_export_vrg", "export_vrg", "Giá xuất khẩu — VRG", "USD/tấn"),
    ("market_domestic_vrg", "domestic_vrg", "Giá nội địa — VRG", "VNĐ/tấn"),
]


def price_history(days: int = 90) -> dict[str, Any]:
    """Lịch sử giá SVR thị trường (mirror source='market') theo ngày × chủng loại cho 4 mục."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT as_of, grade, price_type, price FROM fact_price "
            "WHERE source = :s AND as_of >= CURRENT_DATE - CAST(:d AS integer) ORDER BY as_of"
        ), {"s": _MARKET, "d": days}).mappings().all()
    dates = sorted({str(r["as_of"]) for r in rows})
    idx = {d: i for i, d in enumerate(dates)}
    sections: list[dict[str, Any]] = []
    for ptype, key, label, unit in _HISTORY_SECTIONS:
        by_grade: dict[str, list[float | None]] = {}
        for r in rows:
            if r["price_type"] != ptype:
                continue
            by_grade.setdefault(r["grade"], [None] * len(dates))[idx[str(r["as_of"])]] = float(r["price"])
        sections.append({
            "key": key, "label": label, "unit": unit,
            "labels": [f"{d[8:10]}/{d[5:7]}" for d in dates],  # DD/MM (chuẩn VN)
            "series": [{"name": g, "values": v} for g, v in by_grade.items()],
        })
    return {"sections": sections, "dates": dates}


def _clean_private(prices: dict[str, Any] | None) -> dict[str, dict[str, float | None]]:
    """Mục 6: bỏ dòng trống; chỉ nhập Giá max thì coi đó là giá; Giá max = Giá thì là một giá."""
    out: dict[str, dict[str, float | None]] = {}
    for name, row in (prices or {}).items():
        lo, hi = (row or {}).get("price"), (row or {}).get("price_max")
        if lo is None:
            lo, hi = hi, None
        if lo is None:
            continue
        out[name] = {"price": lo, "price_max": hi if hi is not None and hi != lo else None}
    return out


def invalid_private_rows(prices: dict[str, Any] | None) -> list[str]:
    """Tên các dòng Mục 6 có Giá max NHỎ HƠN Giá (khoảng giá ngược)."""
    return [name for name, row in _clean_private(prices).items()
            if row["price_max"] is not None and row["price_max"] < row["price"]]


def _payload_of(mq: dict[str, Any]) -> dict[str, Any]:
    """Phần lưu trong market_quote.payload."""
    return {
        "fx": mq.get("fx") or {},
        "domestic_private": mq.get("domestic_private") or {},
        "domestic_export": mq.get("domestic_export") or {},
        "export_vrg": mq.get("export_vrg") or {},
        "domestic_vrg": mq.get("domestic_vrg") or {},
        "customer_proposal": mq.get("customer_proposal") or {},
        "private_prices": _clean_private(mq.get("private_prices")),
        "private_processing_cost": mq.get("private_processing_cost"),
        "footer": mq.get("footer") or "",
    }


def _as_payload(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else json.loads(raw)


def _count_filled(payload: dict[str, Any]) -> int:
    total = 0
    for key in _SECTION_MODES:
        for v in (payload.get(key, {}) or {}).get("prices", {}).values():
            if v is not None:
                total += 1
    return total + len(payload.get("private_prices") or {})


def list_quotes(date_from: str | None = None, date_to: str | None = None,
                limit: int = 200) -> list[dict[str, Any]]:
    """Danh sách phiếu (mới nhất trước), lọc theo ngày, TỐI ĐA `limit` phiếu.

    Mỗi ngày một phiếu nên danh sách dài thêm mãi — chặn trần ở server, xem phiếu cũ hơn thì
    lọc theo khoảng ngày.
    """
    ensure_schema()
    where, params = [], {}
    if date_from:
        where.append("as_of >= CAST(:dfrom AS date)")
        params["dfrom"] = date_from
    if date_to:
        where.append("as_of <= CAST(:dto AS date)")
        params["dto"] = date_to
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with session_scope() as db:
        rows = db.execute(text(
            f"SELECT as_of, payload, updated_at FROM market_quote {clause} "
            "ORDER BY as_of DESC LIMIT :lim"
        ), {**params, "lim": max(1, int(limit))}).mappings().all()
    return [{
        "as_of": str(r["as_of"]),
        "filled": _count_filled(_as_payload(r["payload"])),
        "updated": str(r["updated_at"]) if r["updated_at"] else None,
    } for r in rows]


def get_quote(as_of: str) -> dict[str, Any] | None:
    """1 phiếu đầy đủ theo ngày (None nếu ngày đó chưa có phiếu)."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(
            "SELECT payload FROM market_quote WHERE as_of = CAST(:d AS date)"
        ), {"d": as_of}).mappings().first()
    if not row:
        return None
    p = _as_payload(row["payload"])
    return {
        "as_of": as_of,
        "fx": p.get("fx") or {},
        "domestic_private": p.get("domestic_private") or {"prices": {}, "note": ""},
        "domestic_export": p.get("domestic_export")
        or {"prices": {}, "packaging": {}, "shipping": {}, "note": ""},
        "export_vrg": p.get("export_vrg") or {"prices": {}, "note": ""},
        "domestic_vrg": p.get("domestic_vrg") or {"prices": {}, "status": {}, "note": ""},
        "customer_proposal": p.get("customer_proposal") or {"qty": {}, "prices": {}, "note": ""},
        "private_prices": p.get("private_prices") or {},
        "private_processing_cost": p.get("private_processing_cost"),
        "footer": p.get("footer") or "",
    }


#: Giá mủ tư nhân mỗi đơn vị báo vào những ngày khác nhau → lấy giá MỚI NHẤT của từng đơn vị trong
#: cửa sổ này (mỗi dòng ghi rõ ngày giá của chính nó — không gán giá ngày này cho ngày khác).
PRIVATE_PRICE_WINDOW_DAYS = 14


def private_prices_by_unit(as_of: str | None = None,
                           days: int = PRIVATE_PRICE_WINDOW_DAYS) -> list[dict[str, Any]]:
    """Giá mủ tư nhân MỚI NHẤT của từng đơn vị trong `days` ngày tính tới `as_of` (mặc định hôm nay).

    Mỗi dòng: tên · giá · giá max · ngày giá · chi phí gia công của phiếu đó · `prev` = lần báo giá
    liền trước của CHÍNH đơn vị đó (tìm lùi thêm một cửa sổ nữa) để so tăng/giảm.
    """
    from app.core import edit_window

    end = as_of or edit_window.today().isoformat()
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT as_of, payload FROM market_quote "
            "WHERE as_of <= CAST(:d AS date) AND as_of > CAST(:d AS date) - CAST(:w AS integer) "
            "AND COALESCE(payload->'private_prices', '{}'::jsonb) <> '{}'::jsonb "
            "ORDER BY as_of DESC"), {"d": end, "w": days * 2}).mappings().all()
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    latest: dict[str, dict[str, Any]] = {}
    for r in rows:
        day, p = str(r["as_of"]), _as_payload(r["payload"])
        for name, v in (p.get("private_prices") or {}).items():
            if (v or {}).get("price") is None:
                continue
            entry = {"price": v["price"], "price_max": v.get("price_max"), "as_of": day}
            if name not in latest:
                if day > start:
                    latest[name] = {"name": name, **entry,
                                    "processing_cost": p.get("private_processing_cost"), "prev": None}
            elif latest[name]["prev"] is None:
                latest[name]["prev"] = entry
    return list(latest.values())


def save_quote(mq: dict[str, Any]) -> dict[str, Any] | None:
    """Lưu phiếu: payload jsonb + mirror Mục 1-4 (chuỗi market)."""
    ensure_schema()
    as_of = mq["as_of"]
    payload = _payload_of(mq)
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM market_quote WHERE as_of = CAST(:d AS date)"),
                         {"d": as_of}).mappings().first()
        before = dict(row["payload"]) if row else None
        db.execute(text("""
            INSERT INTO market_quote (as_of, payload)
            VALUES (CAST(:d AS date), CAST(:p AS jsonb))
            ON CONFLICT (as_of) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
        """), {"d": as_of, "p": json.dumps(payload, ensure_ascii=False)})
    # Màn này TỰ ĐỘNG LƯU sau mỗi ~0.9s → gộp các lần lưu liên tiếp của cùng người vào 1 dòng.
    audit_repo.log("market_quote", "update" if before else "create", as_of,
                   before=before, after=payload, as_of=as_of, coalesce=True)
    _mirror_market_series(as_of, mq)
    return get_quote(as_of)


def _mirror_market_series(as_of: str, mq: dict[str, Any]) -> None:
    """Mục 1-4 → fact_price source=market (xoá cũ theo ngày rồi ghi lại).

    Đây là bản SAO PHÁI SINH của payload phiếu (đã ghi nhật ký ở `save_quote`) nên tạm tắt
    nhật ký để không sinh hàng chục dòng trùng cho mỗi lần tự động lưu.
    """
    with request_ctx.paused():
        with session_scope() as db:
            db.execute(text("DELETE FROM fact_price WHERE source = :s AND as_of = CAST(:d AS date)"),
                       {"s": _MARKET, "d": as_of})
        for key, (ptype, cur, unit) in _SECTION_MODES.items():
            for grade, val in ((mq.get(key) or {}).get("prices", {}) or {}).items():
                if val is None:
                    continue
                price_repo.upsert_record({"as_of": as_of, "source": _MARKET, "grade": grade,
                                          "contract": "", "price_type": ptype, "price": float(val),
                                          "currency": cur, "unit": unit})


def delete_quote(as_of: str) -> bool:
    """Xoá phiếu + chuỗi market của ngày."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM market_quote WHERE as_of = CAST(:d AS date)"),
                         {"d": as_of}).mappings().first()
        before = dict(row["payload"]) if row else None
        db.execute(text("DELETE FROM fact_price WHERE source = :s AND as_of = CAST(:d AS date)"),
                   {"s": _MARKET, "d": as_of})
        res = db.execute(text("DELETE FROM market_quote WHERE as_of = CAST(:d AS date)"),
                         {"d": as_of})
        deleted = res.rowcount > 0
    if deleted:
        audit_repo.log("market_quote", "delete", as_of, before=before, as_of=as_of)
    return deleted
