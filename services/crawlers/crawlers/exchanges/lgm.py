"""LGM (Malaysian Rubber Board) — giá physical FOB: SMR CV/L/5/GP/10/20 + Latex.

Nguồn: API mà trang Angular của LGM gọi — webv2api/api/rubberprice/currentprice (JSON).
Dùng Basic token CÔNG KHAI nhúng sẵn trong frontend LGM (FOB:…) — không phải secret riêng;
override bằng env LGM_AUTH nếu cần. SMR* yết US cents/kg (field sellersUs). Latex: API trả
sellersUs CHƯA quy đổi (= sellers Sen/kg) → LƯU GỐC Sen/kg; lớp hiển thị/bản tin quy đổi
USD/T bằng tỷ giá USD/MYR ngoài (Sen ÷ USD/MYR × 10), đúng cách chuyên viên. Spec: lay-gia-cac-san.md.
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


def _parse(rows: list[dict]) -> list[PriceRecord]:
    out: list[PriceRecord] = []
    for r in rows:
        grade = _norm(str(r.get("grade", "")))
        if not grade:
            continue
        if grade == "LATEX":
            # Latex: API trả Sen/kg (sellersUs = sellers, chưa quy đổi). Lưu GỐC Sen/kg —
            # USD/T được quy đổi sau bằng tỷ giá USD/MYR (Sen ÷ USD/MYR × 10).
            sen = r.get("sellers")
            if sen is None:
                continue
            price, currency, unit = float(sen), "MYR", "Sen/kg"
        else:
            us = r.get("sellersUs")  # SMR* đã yết sẵn US cents/kg
            if us is None:
                continue
            price, currency, unit = float(us), "USc", "US cents/kg"
        try:
            as_of = datetime.fromisoformat(str(r.get("tarikh"))).date()
        except (TypeError, ValueError):
            as_of = datetime.now().date()
        out.append(
            PriceRecord(
                source=Source.LGM, grade=grade, price=price,
                currency=currency, unit=unit, price_type="physical", as_of=as_of,
                extra={"tone": r.get("tone"), "session": r.get("masa")},
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
