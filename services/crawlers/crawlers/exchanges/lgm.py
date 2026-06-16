"""LGM (Malaysian Rubber Board) — giá physical FOB: SMR CV/L/5/GP/10/20 + Latex.

Nguồn: API mà trang Angular của LGM gọi — webv2api/api/rubberprice/currentprice (JSON).
Dùng Basic token CÔNG KHAI nhúng sẵn trong frontend LGM (FOB:…) — không phải secret riêng;
override bằng env LGM_AUTH nếu cần. SMR* yết US cents/kg (field sellersUs). Latex: API trả
sellersUs CHƯA quy đổi (= sellers Sen/kg) → tự quy đổi US cents/kg = Sen/kg ÷ tỷ giá MYR/USD
nội tại (suy từ SMR cùng phiên). Spec: lay-gia-cac-san.md.
"""

from __future__ import annotations

import os
from datetime import datetime

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status

URL = "https://www.lgm.gov.my/webv2api/api/rubberprice/currentprice"
# Token Basic công khai nhúng trong frontend LGM (ai mở web cũng thấy) — không phải bí mật.
_AUTH = os.getenv("LGM_AUTH", "Basic Rk9COkxnTUYwYiQyMDI1")


def _norm(grade: str) -> str:
    g = grade.upper().strip()
    if "LATEX" in g:
        return "LATEX"
    return g.replace(" ", "")  # "SMR 20" -> "SMR20", "SMR CV" -> "SMRCV"


def _implied_rate(rows: list[dict]) -> float | None:
    """Tỷ giá MYR/USD nội tại của LGM = sellers(sen/kg) ÷ sellersUs(US cents/kg) của SMR.

    Dùng để quy đổi Latex sang US cents/kg (API LGM trả sellersUs của Latex CHƯA quy đổi,
    bằng đúng sellers). Lấy theo dữ liệu cùng phiên → tự nhất quán, không phụ thuộc FX ngoài.
    """
    for r in rows:
        if _norm(str(r.get("grade", ""))) == "LATEX":
            continue
        sen, usd = r.get("sellers"), r.get("sellersUs")
        try:
            if sen and usd and float(usd) > 0:
                return float(sen) / float(usd)
        except (TypeError, ValueError):
            continue
    return None


def _parse(rows: list[dict]) -> list[PriceRecord]:
    rate = _implied_rate(rows)
    out: list[PriceRecord] = []
    for r in rows:
        grade = _norm(str(r.get("grade", "")))
        if not grade:
            continue
        is_latex = grade == "LATEX"
        sen = r.get("sellers")
        if is_latex:
            # Tự quy đổi: US cents/kg = Sen/kg ÷ tỷ giá (spec lay-gia-cac-san.md).
            if sen is None or rate is None:
                continue
            price: float = round(float(sen) / rate, 2)
        else:
            us = r.get("sellersUs")
            if us is None:
                continue
            price = float(us)
        try:
            as_of = datetime.fromisoformat(str(r.get("tarikh"))).date()
        except (TypeError, ValueError):
            as_of = datetime.now().date()
        out.append(
            PriceRecord(
                source=Source.LGM,
                grade=grade,
                price=price,
                currency="USD",
                unit="US cents/kg",
                price_type="physical",
                as_of=as_of,
                extra={
                    "local_sen_kg": sen,
                    "implied_myr_usd": round(rate, 4) if rate else None,
                    "tone": r.get("tone"),
                    "session": r.get("masa"),
                },
            )
        )
    return out


def crawl() -> CrawlResult:
    try:
        rows = fetch_json(URL, headers={"Authorization": _AUTH, "Accept": "application/json"})
        records = _parse(rows if isinstance(rows, list) else [])
        if records:
            return CrawlResult(source=Source.LGM, status=Status.OK, records=records)
        return CrawlResult(source=Source.LGM, status=Status.EMPTY, note="LGM không trả dữ liệu giá")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.LGM, status=Status.ERROR, note=str(exc))
