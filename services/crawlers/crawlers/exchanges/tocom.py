"""TOCOM/OSE — cao su RSS3 & TSR20: SETTLEMENT của kỳ hạn có TRADING VALUE lớn nhất.

Cao su nằm ở sàn OSE (sau tái cơ cấu JPX 2020, không còn ở TOCOM). Nguồn: JPX OSE Daily Report ZIP
  .../daily/files/{YYYYMM}/Daily_Report_OSE_{YYYYMMDD}.zip → giải nén → cdf_dyr_{ngày}.pdf
  (Commodity Derivatives Futures) → trang RSS3 / TSR20.
Chọn kỳ hạn theo MAX TRADING VALUE (đúng spec lay-gia-cac-san.md). Đơn vị JPY/kg.
ZIP archive ~4 tháng; tự lùi ngày để lấy báo cáo mới nhất có sẵn (hôm nay có thể chưa đăng).
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date, timedelta

from ..base.fetcher import fetch_bytes
from ..base.models import CrawlResult, PriceRecord, Source, Status

_ZIP = (
    "https://www.jpx.co.jp/automation/markets/statistics-derivatives/daily/files/"
    "{ym}/Daily_Report_OSE_{ymd}.zip"
)


def _zip_url(d: date) -> str:
    return _ZIP.format(ym=d.strftime("%Y%m"), ymd=d.strftime("%Y%m%d"))


def _recent_days(today: date, n: int = 7) -> list[date]:
    """today lùi dần, bỏ T7/CN — để thử báo cáo mới nhất có sẵn."""
    days, d = [], today
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days


def _parse_row(line: str) -> dict | None:
    """1 dòng dữ liệu PDF → {contract, settle, trading_value}. Tách riêng để test offline.

    settle = số thập phân CUỐI dòng (sau OHLC + net change). trading_value = số có dấu phẩy
    lớn nhất ≥ 1 triệu (¥); dòng không giao dịch → 0.
    """
    line = line.strip()
    if not re.match(r"^\d{6}\s", line):
        return None
    toks = line.split()
    decimals = [t for t in toks if re.fullmatch(r"\d+\.\d+", t)]
    if not decimals:
        return None
    big = [
        int(t.replace(",", ""))
        for t in toks
        if re.fullmatch(r"\d{1,3}(,\d{3})+", t) and int(t.replace(",", "")) >= 1_000_000
    ]
    return {"contract": toks[0], "settle": float(decimals[-1]), "trading_value": max(big) if big else 0}


def _parse_rubber(pdf_bytes: bytes) -> dict[str, list[dict]]:
    import pdfplumber  # lazy: chỉ cần khi crawl thật

    out: dict[str, list[dict]] = {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "ゴム" not in t or ("AuctionMarket" not in t and "競争売買" not in t):
                continue
            grade = "RSS3" if "RSS" in t else ("TSR20" if "TSR" in t else None)
            if not grade or grade in out:
                continue
            rows = [r for r in (_parse_row(line) for line in t.split("\n")) if r]
            if rows:
                out[grade] = rows
    return out


def _pick(rows: list[dict]) -> dict | None:
    """Kỳ hạn có Trading Value lớn nhất; nếu không có giao dịch → kỳ hạn đầu (front)."""
    traded = [r for r in rows if r["trading_value"] > 0]
    if traded:
        return max(traded, key=lambda r: r["trading_value"])
    return rows[0] if rows else None


def _fetch_pdf(today: date) -> tuple[bytes, date] | None:
    for d in _recent_days(today):
        try:
            zbytes = fetch_bytes(_zip_url(d))
        except Exception:  # noqa: BLE001 - ngày này không có, thử ngày trước
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
                name = next((n for n in zf.namelist() if re.search(r"cdf_dyr_\d+\.pdf$", n)), None)
                if name:
                    return zf.read(name), d
        except zipfile.BadZipFile:
            continue
    return None


def crawl(as_of: date | None = None) -> CrawlResult:
    try:
        fetched = _fetch_pdf(as_of or date.today())
        if not fetched:
            return CrawlResult(
                source=Source.TOCOM, status=Status.EMPTY, note="Không tải được OSE Daily Report ZIP"
            )
        pdf_bytes, day = fetched
        records: list[PriceRecord] = []
        for grade, rows in _parse_rubber(pdf_bytes).items():
            best = _pick(rows)
            if not best:
                continue
            records.append(
                PriceRecord(
                    source=Source.TOCOM,
                    grade=grade,
                    price=best["settle"],
                    currency="JPY",
                    unit="JPY/kg",
                    price_type="settlement",
                    as_of=day,
                    contract=best["contract"],
                    extra={
                        "exchange": "OSE/TOCOM",
                        "selection": "max_trading_value",
                        "trading_value": best["trading_value"],
                        "curve": rows,
                    },
                )
            )
        if records:
            return CrawlResult(source=Source.TOCOM, status=Status.OK, records=records)
        return CrawlResult(source=Source.TOCOM, status=Status.EMPTY, note=f"Không thấy RSS3/TSR20 ({day})")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.TOCOM, status=Status.ERROR, note=str(exc))
