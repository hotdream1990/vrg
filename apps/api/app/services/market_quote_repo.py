"""Repository Báo giá mủ thị trường (market_quote) — 1 phiếu/ngày (nhập tay).

Payload jsonb giữ tỷ giá VCB + Mục 1-3 (giá SVR + ghi chú). Mục 4 (giá mủ nước theo
đơn vị) KHÔNG lưu trong payload mà đồng bộ thẳng kho Giá mủ nguyên liệu
(fact_price source=vrg, purchase). Mục 1-3 còn được mirror sang fact_price source=market
để dùng như chuỗi thời gian cho Bản tin/dự báo.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import MARKET_QUOTE_GRADES
from app.services import member_unit_repo, price_repo

_MARKET = "market"
# section key → (price_type, currency, unit) khi mirror sang fact_price source=market
_SECTION_MODES = {
    "domestic_private": ("market_domestic_private", "VND", "đồng/tấn"),
    "export_vrg": ("market_export_vrg", "USD", "USD/tấn"),
    "domestic_vrg": ("market_domestic_vrg", "VND", "đồng/tấn"),
}
_PURCHASE = {"source": "vrg", "price_type": "purchase", "currency": "VND", "unit": "đồng/độ TSC"}


def meta() -> dict[str, Any]:
    """Chủng loại SVR cố định + đơn vị thành viên active (cột Mục 4)."""
    return {"grades": MARKET_QUOTE_GRADES, "units": member_unit_repo.active_names()}


def _payload_of(mq: dict[str, Any]) -> dict[str, Any]:
    """Phần lưu trong market_quote.payload (bỏ regions — regions đi vào fact_price)."""
    return {
        "fx": mq.get("fx") or {},
        "domestic_private": mq.get("domestic_private") or {},
        "export_vrg": mq.get("export_vrg") or {},
        "domestic_vrg": mq.get("domestic_vrg") or {},
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
    return total


def list_quotes(date_from: str | None = None, date_to: str | None = None) -> list[dict[str, Any]]:
    """Danh sách phiếu (mới nhất trước), lọc theo ngày."""
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
            f"SELECT as_of, payload, updated_at FROM market_quote {clause} ORDER BY as_of DESC"
        ), params).mappings().all()
    return [{
        "as_of": str(r["as_of"]),
        "filled": _count_filled(_as_payload(r["payload"])),
        "updated": str(r["updated_at"]) if r["updated_at"] else None,
    } for r in rows]


def get_quote(as_of: str) -> dict[str, Any] | None:
    """1 phiếu đầy đủ. regions (Mục 4) đọc live từ kho Giá mủ nguyên liệu theo ngày."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(
            "SELECT payload FROM market_quote WHERE as_of = CAST(:d AS date)"
        ), {"d": as_of}).mappings().first()
    regions = price_repo.purchase_by_company_on_date(as_of)
    if not row and not regions:
        return None
    p = _as_payload(row["payload"]) if row else {}
    return {
        "as_of": as_of,
        "fx": p.get("fx") or {},
        "domestic_private": p.get("domestic_private") or {"prices": {}, "note": ""},
        "export_vrg": p.get("export_vrg") or {"prices": {}, "note": ""},
        "domestic_vrg": p.get("domestic_vrg") or {"prices": {}, "status": {}, "note": ""},
        "regions": regions,
        "footer": p.get("footer") or "",
    }


def save_quote(mq: dict[str, Any]) -> dict[str, Any] | None:
    """Lưu phiếu: payload jsonb + sync Mục 4 (kho mủ nước) + mirror Mục 1-3 (chuỗi market)."""
    ensure_schema()
    as_of = mq["as_of"]
    with session_scope() as db:
        db.execute(text("""
            INSERT INTO market_quote (as_of, payload)
            VALUES (CAST(:d AS date), CAST(:p AS jsonb))
            ON CONFLICT (as_of) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
        """), {"d": as_of, "p": json.dumps(_payload_of(mq), ensure_ascii=False)})
    _sync_regions(as_of, mq.get("regions") or {})
    _mirror_market_series(as_of, mq)
    return get_quote(as_of)


def _sync_regions(as_of: str, regions: dict[str, Any]) -> None:
    """Mục 4 → kho Giá mủ nguyên liệu (đảm bảo đơn vị tồn tại, upsert giá đồng/độ TSC)."""
    for unit, price in regions.items():
        if price is None:
            continue
        member_unit_repo.add_unit(unit)  # idempotent (ON CONFLICT DO NOTHING)
        price_repo.upsert_record({"as_of": as_of, "grade": unit, "contract": "",
                                  "price": float(price), **_PURCHASE})


def _mirror_market_series(as_of: str, mq: dict[str, Any]) -> None:
    """Mục 1-3 → fact_price source=market (xoá cũ theo ngày rồi ghi lại)."""
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
    """Xoá phiếu + chuỗi market của ngày (GIỮ nguyên giá mủ nước đã đồng bộ sang kho chung)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(text("DELETE FROM fact_price WHERE source = :s AND as_of = CAST(:d AS date)"),
                   {"s": _MARKET, "d": as_of})
        res = db.execute(text("DELETE FROM market_quote WHERE as_of = CAST(:d AS date)"),
                         {"d": as_of})
        return res.rowcount > 0
