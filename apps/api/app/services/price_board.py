"""Bảng giá 'thành phần' cho dashboard: mỗi sàn = giá nội tệ · tỷ giá · USD/T,
kèm danh sách tỷ giá (Exchange Rate). Tái dùng convert (1 nguồn quy đổi) + latest() DB.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.core.market_meta import EXCHANGE_ORDER, FX_PAIRS, WORLD_GRADE_MAP
from app.services import price_repo

# bulletin.convert (services/bulletin) — 1 nguồn quy đổi đơn vị, dùng chung với bản tin.
_BULLETIN = Path(__file__).resolve().parents[4] / "services" / "bulletin"
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import to_usd_tonne_detail  # noqa: E402


def build_board() -> dict[str, Any]:
    """Dựng board từ giá mới nhất trong DB → {exchanges, fx, ingested_at}."""
    rows = price_repo.latest()

    fx_rates = {r["grade"]: float(r["price"]) for r in rows if r["source"] == "fx"}
    fx_asof = {r["grade"]: str(r["as_of"]) for r in rows if r["source"] == "fx"}

    exchanges: list[dict[str, Any]] = []
    for r in rows:
        mapping = WORLD_GRADE_MAP.get((r["source"], r["grade"]))
        if not mapping:
            continue
        exchange, blt_grade = mapping
        usd, fx_pair, fx_rate = to_usd_tonne_detail(float(r["price"]), r["unit"], fx_rates)
        exchanges.append({
            "exchange": exchange,
            "grade": blt_grade,
            "native_price": float(r["price"]),
            "native_unit": r["unit"],
            "fx_pair": fx_pair,
            "fx_rate": fx_rate,
            "usd_tonne": usd,
            "as_of": str(r["as_of"]),
        })

    order = {e: i for i, e in enumerate(EXCHANGE_ORDER)}
    exchanges.sort(key=lambda x: (order.get(x["exchange"], 9), x["grade"]))

    fx = [
        {"pair": p, "rate": fx_rates[p], "as_of": fx_asof.get(p)}
        for p in FX_PAIRS
        if p in fx_rates
    ]

    ingested = [r.get("ingested_at") for r in rows if r.get("ingested_at")]
    ingested_at = str(max(ingested)) if ingested else None
    return {"exchanges": exchanges, "fx": fx, "ingested_at": ingested_at}
