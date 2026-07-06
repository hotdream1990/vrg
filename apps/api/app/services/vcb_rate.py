"""Lấy tỷ giá Vietcombank (USD) realtime từ API công khai của VCB.

Trả 3 giá đúng như phiếu báo giá: mua tiền mặt (cash) · mua chuyển khoản (transfer) · bán (sell).
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date as _date
from typing import Any

_URL = "https://www.vietcombank.com.vn/api/exchangerates?date={d}"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _num(v: Any) -> float | None:
    s = str(v).replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_usd(day: str | None = None) -> dict[str, Any]:
    """Tỷ giá USD của VCB theo ngày (mặc định hôm nay). Ném lỗi nếu không lấy được."""
    d = day if day and _DATE_RE.match(day) else _date.today().isoformat()
    req = urllib.request.Request(
        _URL.format(d=d),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - URL cố định của VCB
        data = json.load(resp)
    usd = next((x for x in data.get("Data", []) if x.get("currencyCode") == "USD"), None)
    if not usd:
        raise ValueError("Không tìm thấy USD trong dữ liệu VCB")
    src_date = str(data.get("Date") or d)[:10]
    return {
        "mua_tm": _num(usd.get("cash")),
        "mua_ck": _num(usd.get("transfer")),
        "ban": _num(usd.get("sell")),
        "date": src_date,
    }
