"""Nguồn giá đóng cửa NGÀY cho chỉ số Báo cáo tuần: CNBC (chính) → Yahoo Finance (dự phòng).

Vì sao CNBC đứng trước: Yahoo trả HTTP 429 cho IP máy chủ prod (datacenter) và cả máy dev khi gọi dày;
API biểu đồ CNBC truy cập được từ prod. Đối chiếu 13/09/2026: TB tuần 34–36 DXY/WTI/Brent của CNBC
TRÙNG TUYỆT ĐỐI Yahoo (vd Brent 92,34 · 89,52 · 94,51), Brent từng ngày 24–28/8 khớp tới 0,01.
Nguồn trong danh mục vẫn khai mã kiểu Yahoo (DX-Y.NYB, CL=F, BZ=F) → đổi sang mã CNBC ở đây; mã bắt
đầu bằng '.' hoặc '@' là mã CNBC gốc (không có dự phòng Yahoo).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")
_TIMEOUT_S = 15

# ── CNBC ──
_CNBC_URL = "https://ts-api.cnbc.com/harmony/app/charts/{range}.json"
# Tên khung của CNBC lệch nghĩa: "1M" trả ~1 năm nến NGÀY, "3M" trả ~2 năm nến ngày.
_CNBC_RANGES = (("1M", 330), ("3M", 700))
YAHOO_TO_CNBC = {"DX-Y.NYB": ".DXY", "CL=F": "@CL.1", "BZ=F": "@LCO.1"}

# ── Yahoo ──
_YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


def cnbc_symbol(symbol: str) -> str | None:
    if symbol.startswith((".", "@")):
        return symbol
    return YAHOO_TO_CNBC.get(symbol)


def parse_cnbc(payload: dict[str, Any]) -> list[tuple[str, float]]:
    """JSON biểu đồ CNBC → [(YYYY-MM-DD, giá đóng cửa)] tăng dần. `tradeTime` = ngày giao dịch của sàn."""
    bars = ((payload or {}).get("barData") or {}).get("priceBars") or []
    if not bars:
        raise ValueError("CNBC không có dữ liệu cho mã này")
    by_day: dict[str, float] = {}
    for bar in bars:
        stamp, close = str(bar.get("tradeTime") or ""), bar.get("close")
        if len(stamp) < 8 or close in (None, ""):
            continue
        by_day[f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"] = float(close)
    return sorted(by_day.items())


def fetch_cnbc(symbol: str, date_from: date, today: date | None = None) -> list[tuple[str, float]]:
    age = ((today or date.today()) - date_from).days
    rng = next((name for name, days in _CNBC_RANGES if age <= days), None)
    if rng is None:
        raise ValueError("Kỳ quá xa — CNBC chỉ có khoảng 2 năm gần nhất")
    resp = httpx.get(_CNBC_URL.format(range=rng), params={"symbol": symbol},
                     headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=_TIMEOUT_S)
    resp.raise_for_status()
    return parse_cnbc(resp.json())


def parse_chart(payload: dict[str, Any]) -> list[tuple[str, float]]:
    """JSON chart của Yahoo → [(YYYY-MM-DD ngày giao dịch, giá đóng cửa)] tăng dần, bỏ phiên thiếu giá.

    ValueError nếu Yahoo báo lỗi (mã sai…) hoặc JSON không đúng khuôn.
    """
    chart = (payload or {}).get("chart") or {}
    if chart.get("error"):
        err = chart["error"]
        raise ValueError(str(err.get("description") or err) if isinstance(err, dict) else str(err))
    results = chart.get("result") or []
    if not results:
        raise ValueError("Không có dữ liệu")
    res = results[0]
    offset = int((res.get("meta") or {}).get("gmtoffset") or 0)
    quotes = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    by_day: dict[str, float] = {}
    for ts, close in zip(res.get("timestamp") or [], quotes.get("close") or []):
        if close is None:
            continue
        day = datetime.fromtimestamp(int(ts) + offset, tz=timezone.utc).date().isoformat()
        by_day[day] = float(close)  # trùng ngày (phiên đang chạy) → lấy bản sau cùng
    return sorted(by_day.items())


def _epoch(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def fetch_yahoo(symbol: str, date_from: date, date_to: date) -> list[tuple[str, float]]:
    # Nới 1 ngày 2 đầu vì giờ sàn lệch UTC; nơi gọi lọc lại theo ngày giao dịch.
    params = {"period1": _epoch(date_from - timedelta(days=1)),
              "period2": _epoch(date_to + timedelta(days=2)), "interval": "1d"}
    last_exc: Exception | None = None
    for host in _YAHOO_HOSTS:
        try:
            resp = httpx.get(f"https://{host}/v8/finance/chart/{symbol}", params=params,
                             headers={"User-Agent": _UA, "Accept": "application/json"},
                             timeout=_TIMEOUT_S, follow_redirects=True)
            if resp.status_code in (400, 404):  # mã sai — Yahoo trả JSON kèm mô tả lỗi
                try:
                    parse_chart(resp.json())
                except ValueError:
                    raise
                except Exception:  # noqa: BLE001 - thân không phải JSON
                    pass
            resp.raise_for_status()
            return parse_chart(resp.json())
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - thử host dự phòng (hay gặp 429)
            last_exc = exc
    raise last_exc or RuntimeError("Yahoo không trả dữ liệu")


def fetch_any(symbol: str, date_from: date, date_to: date) -> list[tuple[str, float]]:
    """CNBC trước, lỗi thì Yahoo (nếu mã có dạng Yahoo). Ném lỗi gộp khi cả hai hỏng."""
    errors: list[str] = []
    cnbc = cnbc_symbol(symbol)
    if cnbc:
        try:
            return fetch_cnbc(cnbc, date_from)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"CNBC: {str(exc)[:100]}")
    if not symbol.startswith((".", "@")):
        try:
            return fetch_yahoo(symbol, date_from, date_to)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Yahoo: {str(exc)[:100]}")
    raise RuntimeError("; ".join(errors) or "Mã không có nguồn hỗ trợ")
