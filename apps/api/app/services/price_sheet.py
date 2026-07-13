"""Lưới "Bảng tính giá" (giống sheet mẫu VRG): hàng = ngày, cột nhóm theo sàn,
mỗi sàn có Native · Tỷ giá · USD/T + khối tỷ giá. Đọc DB, USD quy đổi 1 nguồn (convert).
"""

from __future__ import annotations

import sys
from typing import Any

from app.core.market_meta import FX_PAIRS, SHEET_GROUPS
from app.core.paths import bulletin_dir
from app.services import price_repo

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import to_usd_tonne_detail  # noqa: E402


def build_sheet(
    days: int = 30, date_from: str | None = None, date_to: str | None = None,
) -> dict[str, Any]:
    """Dựng lưới giá theo ngày → {groups, fx_pairs, rows}. Chỉ lấy ngày có giá sàn (trading days)."""
    cols = [c for g in SHEET_GROUPS for c in g["cols"]]
    sources = sorted({c["edit"]["source"] for c in cols} | {"fx"})
    raw = price_repo.prices_since(sources, days, date_from, date_to)

    by_key: dict[tuple[str, str, str], tuple[float, str]] = {}
    fx_series: dict[str, dict[str, float]] = {}
    trading_dates: set[str] = set()
    for r in raw:
        d = str(r["as_of"])
        if r["source"] == "fx":
            fx_series.setdefault(r["grade"], {})[d] = float(r["price"])
        else:
            by_key[(r["source"], r["grade"], d)] = (float(r["price"]), r["unit"])
            trading_dates.add(d)

    def fx_at(pair: str, d: str) -> float | None:
        """Tỷ giá ĐÚNG NGÀY d — KHÔNG carry-forward (không đắp tỷ giá ngày khác để dựng số cho ngày
        này). Thiếu tỷ giá đúng ngày → None → ô tỷ giá để trống + USD/tấn ngày đó không quy đổi."""
        return fx_series.get(pair, {}).get(d)

    rows: list[dict[str, Any]] = []
    for d in sorted(trading_dates, reverse=True):
        fx_map = {p: r for p in FX_PAIRS if (r := fx_at(p, d)) is not None}
        cells: dict[str, Any] = {}
        for c in cols:
            e = c["edit"]
            entry = by_key.get((e["source"], e["grade"], d))
            usd = native = None
            if entry:
                native, unit = entry
                usd, _, _ = to_usd_tonne_detail(native, unit, fx_map)
            cell: dict[str, Any] = {"usd": usd}
            if c.get("show_native"):
                cell["native"] = native
            if c.get("show_fx") and c.get("fx_pair"):
                cell["fx_rate"] = fx_at(c["fx_pair"], d)
            cells[c["key"]] = cell
        rows.append({
            "as_of": d,
            "cells": cells,
            "fx": {p: fx_at(p, d) for p in FX_PAIRS},
        })

    return {"groups": SHEET_GROUPS, "fx_pairs": FX_PAIRS, "rows": rows}
